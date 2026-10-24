"""
agent_reasoning.py - Moteur de réflexion cognitive et de dialogue naturel structuré pour Yasmine
Gère les différentes étapes du dialogue commercial :
1. Accueil & Qualification lors des salutations (bonjour, salam) SANS envoyer de photos ni de prix au hasard.
2. Détection avancée de la langue (y compris l'arabe en caractères latins / Arabizi comme 'salam', 'chhal', 'bghit').
3. Réponses ultra-ciblées et directes avec prix exacts et photos UNIQUEMENT lorsqu'une question précise est posée.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from google import genai
from properties_db import get_properties_summary_for_agent, find_apartment_by_id, find_project_by_id, APARTMENTS, PROJECTS

logger = logging.getLogger("agent_reasoning")
logger.setLevel(logging.INFO)

_client = None

def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        try:
            _client = genai.Client(http_options={"timeout": 3000})
        except Exception:
            _client = genai.Client()
    return _client


ARABIC_LATIN_KEYWORDS = [
    "salam", "slm", "salamo", "salem", "alaykom", "alaykoum", "aleikoum", "alikom",
    "ahlan", "marhaba", "marhaban", "labas", "sbah", "sbah lkhir", "msa", "massa",
    "bghit", "chhal", "taman", "chka", "chqa", "dar", "fin", "kayn", "kaynin",
    "choukrane", "chokran", "afak", "3afak", "kidayr", "kidayra", "mezyan", "mzyan"
]

GREETING_PATTERNS = [
    r"^(bonjour|bonsoir|salut|hello|coucou|bienvenue)(\s+(yasmine|madame|monsieur|ca va|cava))?[!?. ]*$",
    r"^(salam|slm|salamo|salam\s+alaykoum|salam\s+alikoum|ahlan|marhaba|marhaban|labas)(\s+(khti|yasmine|kidayra|alikom))?[!?. ]*$",
    r"^(\u0633\u0644\u0627\u0645|\u0627\u0644\u0633\u0644\u0627\u0645|\u0627\u0644\u0633\u0644\u0627\u0645\s+\u0639\u0644\u064a\u0643\u0645|\u0645\u0631\u062d\u0628\u0627|\u0623\u0647\u0644\u0627|\u0635\u0628\u0627\u062d\s+\u0627\u0644\u062e\u064a\u0631|\u0645\u0633\u0627\u0621\s+\u0627\u0644\u062e\u064a\u0631)(\s+\u064a\u0627\u0633\u0645\u064a\u0646)?[!?. ]*$"
]

THANKS_PATTERNS = [
    r"^(merci|merci\s+beaucoup|parfait|super|tres\s+bien|d\'accord|ok)(\s+(yasmine|madame))?[!?. ]*$",
    r"^(chokran|choukrane|barak\s+allaho\s+fik|choukran|jazak\s+allah)[!?. ]*$",
    r"^(\u0634\u0643\u0631\u0627|\u0628\u0627\u0631\u0643\s+\u0627\u0644\u0644\u0647\s+\u0641\u064a\u0643|\u062c\u0632\u0627\u0643\s+\u0627\u0644\u0644\u0647\s+\u062e\u064a\u0631\u0627)[!?. ]*$"
]


def detect_client_language(user_message: str, preferred_language: str = "auto") -> str:
    """
    Détecte avec précision si le client s'exprime en arabe (caractères arabes ou Arabizi) ou en français.
    """
    if preferred_language == "ar":
        return "ar"
    if preferred_language == "fr":
        return "fr"

    q = user_message.lower().strip()
    # 1. Caractères arabes Unicode
    if any(ord(char) >= 0x0600 and ord(char) <= 0x06FF for char in user_message):
        return "ar"
    
    # 2. Mots-clés arabes en graphie latine (Arabizi / Darija)
    for word in ARABIC_LATIN_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", q):
            return "ar"
            
    return "fr"


def extract_context_project_id(history: Optional[List[Dict[str, str]]]) -> str:
    """Parcourt l'historique récent pour retrouver le projet en cours de discussion."""
    if not history:
        return "proj-atlas"
    for item in reversed(history):
        txt = (item.get("text") or item.get("content") or "").lower()
        if "atlas" in txt or "terrasse" in txt:
            return "proj-atlas"
        if "carthage" in txt or "marina" in txt:
            return "proj-carthage"
        if "emerald" in txt or "green" in txt:
            return "proj-emerald"
    return "proj-atlas"


def build_structured_local_response(
    user_message: str,
    preferred_language: str = "auto",
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Moteur de dialogue et de raisonnement immobilier local instantané (< 10ms).
    Organise le dialogue en étapes cohérentes et naturelles.
    """
    q = user_message.lower().strip()
    lang = detect_client_language(user_message, preferred_language)
    is_ar = (lang == "ar")

    # -------------------------------------------------------------------------
    # 1. CAS D'UNE SIMPLE SALUTATION (Bonjour, Salam, etc.)
    # -------------------------------------------------------------------------
    is_greeting_only = any(bool(re.search(pat, q)) for pat in GREETING_PATTERNS)
    if is_greeting_only:
        if is_ar:
            thinking = "الزبون يلقي التحية. الرد بتحية مهنية موجزة ودافئة على طريقة المساعد العقاري الذكي وطرح سؤال مفتوح."
            resp_text = (
                "وعليكم السلام ورحمة الله وبركاته، أهلاً بك ! أنا **ياسمين**، مستشارتك العقارية لجميع استفساراتك حول مشاريعنا السكنية الفاخرة. "
                "كيف يمكنني مساعدتك اليوم ؟"
            )
            audio = "وعليكم السلام ورحمة الله وبركاته وأهلاً بك! أنا ياسمين مستشارتك العقارية لجميع استفساراتك حول مشاريعنا السكنية. كيف يمكنني مساعدتك اليوم؟"
        else:
            thinking = "Le client salue l'agent. Accueil court, chaleureux et professionnel (style Alia), sans noyer le client sous des détails de projets ou des prix prématurés."
            resp_text = (
                "Bonjour, je suis **Yasmine**, votre conseillère du Groupe Immobilier pour toutes vos questions sur nos projets de standing. "
                "Comment puis-je vous aider aujourd'hui ?"
            )
            audio = "Bonjour, je suis Yasmine, votre conseillère immobilière pour toutes vos questions sur nos projets. Comment puis-je vous aider aujourd'hui ?"

        return {
            "thinking": thinking,
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [],  # AUCUNE CARTE AU HASARD
            "recommended_project_ids": []
        }

    # -------------------------------------------------------------------------
    # 2. CAS DE REMERCIEMENT OU CLÔTURE (Merci, Chokran, etc.)
    # -------------------------------------------------------------------------
    is_thanks_only = any(bool(re.search(pat, q)) for pat in THANKS_PATTERNS)
    if is_thanks_only:
        if is_ar:
            thinking = "الزبون يقدم شكره. الإجابة بلطف واستعداد دائم لتقديم المساعدة."
            resp_text = (
                "العفو، بكل سرور ! أنا دائماً رهن إشارتك لأي سؤال أو لمساعدتك في حجز موعد زيارة لأحد مشاريعنا.\n\n"
                "هل لديك أي استفسار آخر ترغب في معرفته ؟"
            )
            audio = "العفو، بكل سرور! أنا دائماً في خدمتك لمساعدتك في أي وقت."
        else:
            thinking = "Le client remercie l'agent. Formule de politesse chaleureuse et disponibilité pour la suite."
            resp_text = (
                "Je vous en prie, c'est un plaisir de vous accompagner !\n\n"
                "Je reste à votre entière disposition pour toute information complémentaire, pour vous transmettre des plans ou organiser une visite privée.\n\n"
                "Avez-vous d'autres questions sur nos projets ?"
            )
            audio = "Je vous en prie ! N'hésitez surtout pas si vous avez la moindre question, je reste à votre écoute."

        return {
            "thinking": thinking,
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [],
            "recommended_project_ids": []
        }

    # -------------------------------------------------------------------------
    # 3. IDENTIFICATION DU PROJET
    # -------------------------------------------------------------------------
    is_carthage = bool(re.search(r"\b(carthage|marina|mer|vue\s*mer|front\s*de\s*mer|قرطاج|مارينا|بحر)\b", q))
    is_atlas = bool(re.search(r"\b(atlas|terrasse|terrasses|marrakech|palmeraie|أطلس|شرفات|مراكش)\b", q))
    is_emerald = bool(re.search(r"\b(emerald|green|rabat|parc|tunis\s*centre|إيميرالد|جرين|الرباط)\b", q))

    target_project_id = None
    if is_atlas:
        target_project_id = "proj-atlas"
    elif is_carthage:
        target_project_id = "proj-carthage"
    elif is_emerald:
        target_project_id = "proj-emerald"
    else:
        target_project_id = extract_context_project_id(conversation_history)

    target_project = find_project_by_id(target_project_id) or PROJECTS[1]

    # -------------------------------------------------------------------------
    # 4. DEMANDE D'IMAGES / PHOTOS DU PROJET
    # (ex: "vs avez des images des terrasses de l'atlas", "vs avez des images du projet", "non du projet et non de l'appartement")
    # -------------------------------------------------------------------------
    is_image_q = bool(re.search(r"\b(image|images|photo|photos|visuel|visuels|vue|vues|tasawir|tsawer|tousawar|tousawir|صور|صورة)\b", q))
    is_non_du_projet = bool(re.search(r"\b(non\s+du\s+projet|du\s+projet\s+et\s+non|pas\s+l\'appartement|pas\s+l'appartement|مشروع\s+وليس|ديال\s+المشروع)\b", q))

    if is_image_q or is_non_du_projet:
        p_name = target_project["name"]
        if is_ar:
            thinking = f"الزبون يطلب صور وتصاميم المشروع ({p_name}) وليس شقة منفردة. عرض صور المجمع المعماري والمرافق."
            resp_text = f"بالتأكيد، تفضل صور وتصاميم مشروع **{p_name}** :"
            audio = f"بالتأكيد، تفضل صور وتصاميم مشروع {p_name}."
        else:
            thinking = f"Le client demande expressément les images/photos du PROJET ({p_name}) et non une fiche d'appartement. Affichage de la galerie photos du programme."
            if is_non_du_projet:
                resp_text = f"Toutes mes excuses pour la confusion ! Voici bien les photos d'ensemble du projet **{p_name}** :"
            else:
                resp_text = f"Bien sûr, voici les photos du projet **{p_name}** :"
            audio = f"Bien sûr, voici les photos et visuels du projet {p_name}."

        return {
            "thinking": thinking,
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [],  # AUCUNE FICHE D'APPARTEMENT
            "recommended_project_ids": [target_project_id]  # GALERIE DU PROJET
        }

    # -------------------------------------------------------------------------
    # 5. DEMANDE DE LA LISTE DES PROJETS DISPONIBLES
    # (ex: "quel sont les projets dont vos disposer", "quels sont vos projets", "présentez vos projets")
    # -------------------------------------------------------------------------
    is_project_list_q = bool(re.search(r"\b(projet|projets|disposer|disposer\s+de|disponible|disponibles|programme|programmes|vos\s+projets|المشاريع|المشروع|مشاريع|machari3)\b", q))
    is_specific_typology = bool(re.search(r"\b(studio|studios|t2|t3|t4|duplex|penthouse|ستوديو|شقة|بيوت|غرف)\b", q))

    if is_project_list_q and not is_specific_typology and not is_image_q:
        if is_ar:
            thinking = "الزبون يسأل عن المشاريع المتاحة لدى المجموعة. تقديم قائمة واضحة وموجزة بالمشاريع الثلاثة ومواقعها على غرار أسلوب علياء الاحترافي."
            resp_text = (
                "لدينا عدة مشاريع عقارية استثنائية متاحة :\n\n"
                "1. ***حدائق قرطاج والمارينا*** (Les Jardins de Carthage & Marina) في تونس / قمرت : شقق فاخرة بواجهة بحرية مباشرة ومارينا خاصة.\n"
                "2. ***شرفات الأطلس*** (Les Terrasses de l'Atlas) في مراكش / الدار البيضاء : شقق دوبلكس وبنتهاوس بمسبح خاص وتشطيبات ملكية.\n"
                "3. ***إقامة إيميرالد جرين*** (Résidence Emerald Green) في تونس العاصمة / حي السفارات : استوديوهات وشقق عائلية جاهزة للتسليم الفوري.\n\n"
                "إذا كانت لديك أي رغبة خاصة أو استفسار محدد، يسعدني جداً إرشادك !"
            )
            audio = "لدينا 3 مشاريع متميزة: حدائق قرطاج على البحر، شرفات الأطلس بمراكش، وإقامة إيميرالد جرين الجاهزة للسكن فوراً. هل تفضل موقعاً أو نوعاً معيناً؟"
        else:
            thinking = "Le client demande la liste des projets disponibles (style exact d'Alia). Présentation claire, numérotée et aérée des 3 programmes avec localisation."
            resp_text = (
                "Nous avons plusieurs projets immobiliers disponibles :\n\n"
                "1. ***Les Jardins de Carthage & Marina*** à Gammarth / Tunis (Résidence haut standing en front de mer)\n"
                "2. ***Les Terrasses de l'Atlas*** à Marrakech / Casablanca (Duplex et Penthouses de prestige avec piscine privée)\n"
                "3. ***Résidence Emerald Green*** à Tunis Centre / Ambassades (Studios et appartements familiaux prêts à habiter immédiatement)\n\n"
                "Si vous avez des préférences ou des questions spécifiques, n'hésitez pas à me le faire savoir !"
            )
            audio = "Nous avons plusieurs projets disponibles : Les Jardins de Carthage en front de mer, Les Terrasses de l'Atlas avec piscine privée, et la Résidence Emerald Green prête à habiter. Avez-vous une préférence ?"

        return {
            "thinking": thinking,
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [],
            "recommended_project_ids": []
        }

    # -------------------------------------------------------------------------
    # 6. DEMANDE DE DISPONIBILITÉ D'UNE TYPOLOGIE DANS UN PROJET
    # (ex: "vos avez des studio a tangerine", "vous avez des studios à carthage", "vous avez des duplex à l'atlas")
    # -------------------------------------------------------------------------
    is_studio = bool(re.search(r"\b(studio|studios|stydio|ستوديو)\b", q))
    is_t2 = bool(re.search(r"\b(t2|f2|2\s*pi[eè]ces|1\s*chambre|غرفتين|بيتين)\b", q))
    is_t3 = bool(re.search(r"\b(t3|f3|3\s*pi[eè]ces|3\s*chambres|3\s*بيوت|3\s*غرف|ثلاث\s*غرف)\b", q))
    is_t4 = bool(re.search(r"\b(t4|f4|4\s*pi[eè]ces|3\s*chambres|4\s*بيوت|4\s*غرف|أربع\s*غرف)\b", q))
    is_duplex_penthouse = bool(re.search(r"\b(penthouse|duplex|benthous|بنتهاوس|دوبلكس)\b", q))

    if is_studio:
        if is_carthage:
            if is_ar:
                resp_text = (
                    "في مشروع **حدائق قرطاج والمارينا**، نوفر شققاً تبدأ من **غرفتين وصالون (T2)** بمساحة من 68 م² (ابتداءً من 1,450,000 درهم).\n\n"
                    "في المقابل، لدينا **استوديوهات ممتازة جاهزة للسكن والتسليم فوراً** في مشروع **إقامة إيميرالد جرين** بمساحة من 42 م² وسعر يبدأ من **780,000 درهم مغربي**.\n\n"
                    "هل تود تفاصيل أكثر عن أحد هذين الخيارين أو حجز موعد للزيارة ؟"
                )
                audio = "في قرطاج لدينا شقق T2 من 68 متر مربع، ولدينا استوديوهات جاهزة للسكن فوراً في إقامة إيميرالد جرين ابتداءً من 780 ألف درهم."
            else:
                resp_text = (
                    "Au projet **Les Jardins de Carthage & Marina**, nous n'avons pas de studios mais des **T2** à partir de 68 m² (à partir de 1,450,000 MAD).\n\n"
                    "En revanche, nous disposons de superbes **studios prêts à habiter immédiatement** au sein du projet **Résidence Emerald Green** à partir de 42 m² avec un prix forfaitaire à partir de **780,000 MAD**.\n\n"
                    "Souhaitez-vous plus d'informations ou organiser une visite ?"
                )
                audio = "À Carthage nous proposons des T2 à partir de 68 mètres carrés, et nous avons des studios prêts à habiter à la Résidence Emerald Green dès 780 000 dirhams."
            apt = find_apartment_by_id("apt-e103")
            return {
                "thinking": "Le client demande un studio sur Carthage. Redirection courtoise vers les studios disponibles à Emerald Green et mention du T2 à Carthage.",
                "language": lang,
                "response_text": resp_text,
                "audio_script": audio,
                "recommended_apartment_ids": [apt["id"]] if apt else [],
                "recommended_project_ids": []
            }
        else:
            apt = find_apartment_by_id("apt-e103")
            p_price = f"{apt['price_mad']:,} MAD"
            p_surf = f"{apt['surface_m2']} m²"
            if is_ar:
                resp_text = (
                    f"نعم، لدينا **استوديوهات** متوفرة بمشروع **إقامة إيميرالد جرين** (Résidence Emerald Green).\n\n"
                    f"الاستوديوهات تبدأ من مساحة **{p_surf}** بسعر يبدأ من **{p_price}** (جاهزة للسكن والتسليم الفوري).\n\n"
                    f"هل ترغب في مزيد من المعلومات أو تنظيم موعد للزيارة ؟"
                )
                audio = f"نعم، لدينا استوديوهات متوفرة في إقامة إيميرالد جرين ابتداءً من مساحة {p_surf} وسعر {p_price}. هل ترغب في زيارة الشقة؟"
            else:
                resp_text = (
                    f"Oui, nous avons des **studios** disponibles au projet **Résidence Emerald Green**.\n\n"
                    f"Les studios sont à partir de **{p_surf}** avec un prix forfaitaire à partir de **{p_price}** (livraison immédiate, clés en main).\n\n"
                    f"Souhaitez-vous plus d'informations ou organiser une visite ?"
                )
                audio = f"Oui, nous avons des studios disponibles au projet Emerald Green dès {p_surf} à partir de {p_price}. Souhaitez-vous organiser une visite ?"

            return {
                "thinking": "Le client interroge sur la disponibilité des studios. Réponse directe et concise (style Alia) avec surface et prix de départ.",
                "language": lang,
                "response_text": resp_text,
                "audio_script": audio,
                "recommended_apartment_ids": [apt["id"]],
                "recommended_project_ids": []
            }

    if is_duplex_penthouse:
        apt = find_apartment_by_id("apt-a102") if is_atlas else find_apartment_by_id("apt-c401")
        p_name = apt["project_name"]
        p_price = f"{apt['price_mad']:,} MAD"
        p_surf = f"{apt['surface_m2']} m²"
        if is_ar:
            resp_text = (
                f"نعم، لدينا **دوبلكس وبنتهاوس فاخر** متوفر بمشروع **{p_name}**.\n\n"
                f"المساحات تبدأ من **{p_surf}** مع مسبح خاص وتشطيبات ملكية، بسعر يبدأ من **{p_price}**.\n\n"
                f"هل تود الاطلاع على التصميم الهندسي أو تنظيم زيارة للمشروع ؟"
            )
            audio = f"نعم، لدينا دوبلكس وبنتهاوس بمشروع {p_name} بمساحات تبدأ من {p_surf} وسعر يبدأ من {p_price}."
        else:
            resp_text = (
                f"Oui, nous avons des **Duplex et Penthouses de prestige** disponibles au projet **{p_name}**.\n\n"
                f"Les surfaces sont à partir de **{p_surf}** avec piscine privée et vue panoramique, à partir de **{p_price}**.\n\n"
                f"Souhaitez-vous recevoir les plans d'architecte ou organiser une visite privée ?"
            )
            audio = f"Oui, nous avons des duplex et penthouses disponibles au projet {p_name} dès {p_surf} à partir de {p_price}. Souhaitez-vous planifier une visite ?"

        return {
            "thinking": f"Réponse ciblée sur la disponibilité des duplex/penthouses à {p_name}.",
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [apt["id"]],
            "recommended_project_ids": []
        }

    if is_t3:
        apt = find_apartment_by_id("apt-c204") if (is_carthage or not is_atlas) else find_apartment_by_id("apt-a102")
        p_name = apt["project_name"]
        p_price = f"{apt['price_mad']:,} MAD"
        p_surf = f"{apt['surface_m2']} m²"
        if is_ar:
            resp_text = (
                f"نعم، لدينا **شقق 3 غرف وصالون (T3)** متوفرة بمشروع **{p_name}**.\n\n"
                f"تبدأ المساحات من **{p_surf}** (مع تراس واسع وإطلالة مفتوحة) بسعر يبدأ من **{p_price}**.\n\n"
                f"هل تود الحصول على تفاصيل إضافية أو حجز موعد للزيارة ؟"
            )
            audio = f"نعم، لدينا شقق T3 متوفرة في {p_name} بمساحة تبدأ من {p_surf} وسعر يبدأ من {p_price}."
        else:
            resp_text = (
                f"Oui, nous avons des **appartements T3 (3 pièces)** disponibles au projet **{p_name}**.\n\n"
                f"Les surfaces sont à partir de **{p_surf}** (avec grande terrasse) avec un prix à partir de **{p_price}**.\n\n"
                f"Souhaitez-vous plus d'informations ou organiser une visite ?"
            )
            audio = f"Oui, nous avons des T3 disponibles au projet {p_name} dès {p_surf} à partir de {p_price}. Souhaitez-vous organiser une visite ?"

        return {
            "thinking": f"Réponse directe sur la disponibilité du T3 à {p_name} (style Alia).",
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [apt["id"]],
            "recommended_project_ids": []
        }

    # -------------------------------------------------------------------------
    # 7. DEMANDE DE LOCALISATION / EMPLACEMENT DES PROJETS
    # (ex: "اين توجد مشاريعكم", "فين كاينين المشاريع", "où se trouvent vos projets", "adresses")
    # -------------------------------------------------------------------------
    is_location_q = bool(re.search(
        r"(اين|أين|فين|موقع|مواقع|مكان|فين\s+كاين|فين\s+كاينين|fin\s+kayn|fin\s+kaynin|ou\s+se\s+trouv|o[uù]\s+sont|adresse|adresses|localisation|localis|emplacement)",
        q
    ))

    if is_location_q:
        if is_ar:
            thinking = "الزبون يسأل عن موقع ومكان تواجد المشاريع العقارية. تقديم إجابة مباشرة ودقيقة لمواقع المشاريع الثلاثة."
            resp_text = (
                "تتوزع مشاريعنا العقارية الفاخرة في 3 مواقع استراتيجية مميزة :\n\n"
                "1. ***حدائق قرطاج والمارينا*** (Les Jardins de Carthage & Marina) : في **قمرت / تونس** (موقع استثنائي على الواجهة البحرية مباشرة مع مارينا خاصة).\n"
                "2. ***شرفات الأطلس*** (Les Terrasses de l'Atlas) : في **مراكش / الدار البيضاء** (منطقة راقية وهادئة، شقق دوبلكس وبنتهاوس بمسبح خاص).\n"
                "3. ***إقامة إيميرالد جرين*** (Résidence Emerald Green) : في **تونس العاصمة / حي السفارات** (وسط منتزه طبيعي ومساحات خضراء، تسليم فوري).\n\n"
                "هل تفضل موقعاً ساحلياً على البحر مباشرة أم في قلب المدينة ؟"
            )
            audio = "تتوزع مشاريعنا في 3 مواقع مميزة: حدائق قرطاج على البحر في قمرت، شرفات الأطلس بمراكش، وإقامة إيميرالد جرين وسط العاصمة. أي موقع تفضل؟"
        else:
            thinking = "Le client s'informe sur l'emplacement géographique des projets. Réponse claire et structurée avec les villes et quartiers."
            resp_text = (
                "Nos projets immobiliers sont idéalement situés dans des emplacements d'exception :\n\n"
                "1. ***Les Jardins de Carthage & Marina*** : à **Gammarth / Tunis** (en front de mer direct avec marina privée).\n"
                "2. ***Les Terrasses de l'Atlas*** : à **Marrakech / Palmeraie & Casablanca** (quartier résidentiel de prestige, vue panoramique).\n"
                "3. ***Résidence Emerald Green*** : à **Tunis Centre / Quartier des Ambassades** (face au parc boisé, prêt à emménager immédiatement).\n\n"
                "Quel cadre de vie privilégiez-vous (front de mer ou cœur de ville) ?"
            )
            audio = "Nos projets sont situés à Gammarth en front de mer, à Marrakech Palmeraie, et à Tunis Centre face au parc. Quel cadre préférez-vous ?"

        return {
            "thinking": thinking,
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [],
            "recommended_project_ids": []
        }

    # -------------------------------------------------------------------------
    # 8. QUESTIONS FINANCIÈRES (Facilités de paiement, prix, remises, disponibilités)
    # -------------------------------------------------------------------------
    is_price_q = bool(re.search(r"\b(prix|tarif|combien|co[uû]te|coute|budget|ثمن|أثمنة|شحال|بشحال|بكام|كم\s*السعر)\b", q))
    is_payment_q = bool(re.search(r"\b(facilit[eé]|paiement|payer|cr[eé]dit|traite|mensualit|sans\s*int[eé]r[eê]t|تقسيط|دفع|دفعات|تسهيلات|فوائد|تمويل)\b", q))
    is_promo_q = bool(re.search(r"\b(offre|promo|remise|r[eé]duction|notaire|gratuit|تخفيض|عروض|عرض|خصم|مجاني)\b", q))
    is_avail_q = bool(re.search(r"\b(dispo|disponibilit|livraison|pr[eê]t|habiter|quand|واجد|متوفر|متاح|جاهز|موعد\s*التسليم)\b", q))
    is_visit_q = bool(re.search(r"\b(visit|visiter|rdv|rendez-vous|contact|appeler|num[eé]ro|زيارة|موعد|اتصال|رقم)\b", q))

    if is_payment_q or is_promo_q:
        if is_ar:
            thinking = "سؤال حول تسهيلات الأداء وعروض التخفيض. تفصيل التسهيلات بوضوح."
            resp_text = (
                "**تسهيلات الأداء والعروض الحالية :**\n\n"
                "• **تقسيط بدون فوائد على 24 إلى 30 شهراً** : 20% عند الحجز والباقي على دفعات ميسرة حتى الاستلام.\n"
                "• **مصاريف التوثيق والتسجيل مجانية 100%** على مشاريعنا الرئيسية.\n"
                "• **تخفيض خاص 5%** في حال الأداء نقداً.\n\n"
                "ما هي الميزانية أو الدفعة الأولى التي تناسبكم لنقترح عليكم جدول سداد مخصصاً ؟"
            )
            audio = "نوفر تقسيطاً بدون فوائد على 24 إلى 30 شهراً، ومصاريف توثيق مهداة وخصم 5 بالمئة عند الأداء نقداً."
        else:
            thinking = "Le client interroge sur les modalités de paiement et remises. Explication claire et attractive des facilités."
            resp_text = (
                "**Nos facilités de paiement & offres actuelles :**\n\n"
                "• **Échéancier sans intérêt sur 24 à 30 mois** : 20% à la réservation, puis versements échelonnés jusqu'à la remise des clés.\n"
                "• **Frais de notaire 100% offerts** sur nos résidences phares.\n"
                "• **Remise de 5%** pour tout règlement au comptant.\n\n"
                "Quel est l'apport initial que vous envisagez afin d'adapter une simulation financière sur-mesure ?"
            )
            audio = "Nous proposons un échéancier sans intérêt sur 24 à 30 mois, les frais de notaire offerts et 5 pour cent de remise pour paiement comptant."

        return {
            "thinking": thinking,
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [],
            "recommended_project_ids": []
        }

    if is_avail_q:
        if is_ar:
            thinking = "سؤال عن جاهزية المشاريع ومواعيد التسليم."
            resp_text = (
                "**جاهزية الشقق ومواعيد التسليم :**\n\n"
                "• **تسليم فوري (جاهز للسكن الآن) :** *إقامة إيميرالد جرين* (استوديوهات وشقق جاهزة بمفتاحك).\n"
                "• **تسليم أواخر 2026 :** *حدائق قرطاج والمارينا* (شقق فاخرة على البحر في طور التشطيبات الأخيرة).\n"
                "• **تسليم 2027 :** *شرفات الأطلس* (دوبلكس وبنتهاوس بمسبح خاص).\n\n"
                "هل تبحث عن شقة للسكن الفوري أم مشروع في طور الإنجاز للاستفادة من أسعار الإطلاق ؟"
            )
            audio = "شقق إيميرالد جرين جاهزة للسكن فوراً، ومشاريع قرطاج والأطلس تسلم أواخر 2026. هل تبحث عن سكن فوري أم استثمار؟"
        else:
            thinking = "Le client s'informe sur le calendrier de livraison des projets."
            resp_text = (
                "**Disponibilités & Calendrier de livraison :**\n\n"
                "• **Livraison Immédiate (Prêt à emménager) :** *Résidence Emerald Green* (Studios & appartements familiaux clés en main).\n"
                "• **Livraison 4ème Trimestre 2026 :** *Les Jardins de Carthage & Marina* (Phase finale de finitions).\n"
                "• **Livraison 2027 :** *Les Terrasses de l'Atlas* (Duplex et Penthouses de prestige).\n\n"
                "Recherchez-vous une entrée dans les lieux immédiate ou un achat sur plan avec facilités ?"
            )
            audio = "La Résidence Emerald Green est prête à habiter immédiatement, tandis que nos programmes de Carthage et de l'Atlas sont livrables fin 2026."

        return {
            "thinking": thinking,
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [],
            "recommended_project_ids": []
        }

    # -------------------------------------------------------------------------
    # 9. CAS DE PRIX PRÉCIS POUR UN APPARTEMENT
    # -------------------------------------------------------------------------
    matched_apts = []
    for apt in APARTMENTS:
        score = 0
        if is_t3 and apt["typology"] == "T3": score += 5
        if is_t2 and apt["typology"] == "T2": score += 5
        if is_t4 and apt["typology"] == "T4": score += 5
        if is_studio and apt["typology"] == "Studio": score += 5
        if is_duplex_penthouse and ("Penthouse" in apt["typology"] or "Duplex" in apt["typology"]): score += 5
        
        if is_carthage and apt["project_id"] == "proj-carthage": score += 4
        if is_atlas and apt["project_id"] == "proj-atlas": score += 4
        if is_emerald and apt["project_id"] == "proj-emerald": score += 4
        
        if score > 0:
            matched_apts.append((score, apt))

    matched_apts.sort(key=lambda x: x[0], reverse=True)
    selected_apts = [x[1] for x in matched_apts[:1]] if matched_apts else []

    if is_price_q and selected_apts:
        primary_apt = selected_apts[0]
        if is_ar:
            p_name = primary_apt["project_name"]
            p_title = primary_apt["title_ar"]
            p_price = f"{primary_apt['price_mad']:,} درهم مغربي (~{primary_apt['price_eur']:,} يورو)"
            p_surf = f"{primary_apt['surface_m2']} م²"
            p_disc = primary_apt["special_discount_ar"]
            resp_text = (
                f"**السعر المباشر والمواصفات :**\n"
                f"سعر **{p_title}** ({p_name}) هو **{p_price}** لمساحة **{p_surf}**.\n\n"
                f"• **العرض الخاص :** {p_disc}.\n"
                f"• **تسهيلات الأداء :** إمكانية التقسيط حتى موعد التسليم.\n\n"
                f"هل تود معاينة التصميم الهندسي أو تنظيم زيارة للمشروع ؟"
            )
            audio = f"سعر {p_title} هو {p_price} بمساحة {p_surf}. هل تود زيارة المشروع؟"
        else:
            p_name = primary_apt["project_name"]
            p_title = primary_apt["title_fr"]
            p_price = f"{primary_apt['price_mad']:,} MAD (~{primary_apt['price_eur']:,} EUR)"
            p_surf = f"{primary_apt['surface_m2']} m²"
            p_disc = primary_apt["special_discount_fr"]
            resp_text = (
                f"**Prix direct & Disponibilité :**\n"
                f"Pour un **{p_title}** ({p_name}), le prix exact est de **{p_price}** pour **{p_surf}**.\n\n"
                f"• **Offre spéciale :** {p_disc}.\n"
                f"• **Facilités :** Échéancier sans intérêt jusqu'à la remise des clés.\n\n"
                f"Souhaitez-vous recevoir les plans d'architecte ou planifier une visite ?"
            )
            audio = f"Pour un {p_title} à {p_name}, le prix est de {p_price} pour {p_surf}. Souhaitez-vous organiser une visite ?"

        return {
            "thinking": f"Réponse chiffrée directe pour {primary_apt['id']}.",
            "language": lang,
            "response_text": resp_text,
            "audio_script": audio,
            "recommended_apartment_ids": [primary_apt["id"]],
            "recommended_project_ids": []
        }

    # -------------------------------------------------------------------------
    # 10. CAS PAR DÉFAUT : ORIENTATION COMMERCIALE NATURELLE (sans forcer d'appartement)
    # -------------------------------------------------------------------------
    if is_ar:
        thinking = "سؤال عام أو غير محدد بدقة. التوجيه بلطف لمعرفة تفضيلات الزبون."
        resp_text = (
            "يسعدني جداً إرشادك ! لدينا 3 مشاريع عقارية استثنائية :\n\n"
            "• **حدائق قرطاج والمارينا** : شقق فاخرة على البحر مباشرة.\n"
            "• **شرفات الأطلس** : بنتهاوس ودوبلكس مع مسبح خاص بمراكش والدار البيضاء.\n"
            "• **إقامة إيميرالد جرين** : استوديوهات وشقق جاهزة للسكن والتسليم فوراً.\n\n"
            "هل ترغب في معرفة مواقع المشاريع، الأسعار المتاحة، أو مشاهدة صور التصاميم ؟"
        )
        audio = "يسعدني إرشادك! هل ترغب في معرفة مواقع المشاريع، الأسعار، أو مشاهدة صور التصاميم؟"
    else:
        thinking = "Demande générale d'orientation. Invitation claire à préciser un projet, un budget ou une ville."
        resp_text = (
            "Avec grand plaisir ! Nous développons 3 programmes d'exception :\n\n"
            "• ***Les Jardins de Carthage & Marina*** : Résidence balnéaire haut standing face à la mer.\n"
            "• ***Les Terrasses de l'Atlas*** : Duplex et Penthouses de prestige avec piscine privée.\n"
            "• ***Résidence Emerald Green*** : Studios et appartements familiaux prêts à habiter immédiatement.\n\n"
            "Souhaitez-vous voir les photos d'un projet, connaître nos emplacements ou les prix par typologie ?"
        )
        audio = "Avec grand plaisir ! Souhaitez-vous voir les photos d'un projet, connaître nos emplacements ou les prix disponibles ?"

    return {
        "thinking": thinking,
        "language": lang,
        "response_text": resp_text,
        "audio_script": audio,
        "recommended_apartment_ids": [],
        "recommended_project_ids": []
    }


def process_real_estate_query(
    user_message: str,
    input_modality: str = "text",
    conversation_history: Optional[List[Dict[str, str]]] = None,
    preferred_language: str = "auto"
) -> Dict[str, Any]:
    """
    Point d'entrée principal. Gère le dialogue naturel structuré et la rapidité d'exécution.
    """
    data = build_structured_local_response(
        user_message=user_message,
        preferred_language=preferred_language,
        conversation_history=conversation_history
    )

    # Enrichissement avec les fiches complètes des appartements
    apt_cards = []
    for apt_id in data.get("recommended_apartment_ids", []):
        apt = find_apartment_by_id(apt_id)
        if apt:
            apt_cards.append(apt)

    proj_cards = []
    for proj_id in data.get("recommended_project_ids", []):
        proj = find_project_by_id(proj_id)
        if proj:
            proj_cards.append(proj)

    data["apartment_cards"] = apt_cards
    data["project_cards"] = proj_cards
    return data
