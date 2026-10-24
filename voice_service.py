"""
voice_service.py - Moteur vocal pour l'Agent Immobilier Yasmine
G?re la transcription de la voix client (STT) et la synth?se vocale f?minine bilingue (TTS)
en Fran?ais et en Arabe avec Gemini 3.8 Flash TTS.
"""

import os
import uuid
import base64
import logging
from typing import Optional, Tuple
from google import genai
from google.genai import types

logger = logging.getLogger("voice_service")
logger.setLevel(logging.INFO)

# Dossier de cache pour les fichiers audio g?n?r?s
AUDIO_CACHE_DIR = os.path.join(os.path.dirname(__file__), "static", "audio_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

# Client Gemini
_client = None

def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/webm") -> Tuple[str, str]:
    """
    Transcrit l'audio du client (WebM, WAV, MP3, OGG) en texte.
    D?tecte ?galement la langue pr?dominante (fran?ais ou arabe/darija).
    Retourne (texte_transcrit, langue_detectee: 'fr' | 'ar').
    """
    try:
        client = get_gemini_client()
        
        prompt = (
            "Tu es un expert transcripteur audio bilingue fran?ais/arabe pour une agence immobili?re de luxe.\n"
            "1. Transcris fid?lement les paroles du client.\n"
            "2. Identifie s'il s'agit de fran?ais ('fr') ou d'arabe/darija ('ar').\n"
            "Format de ta r?ponse STRICTEMENT :\n"
            "LANGUE: fr ou ar\n"
            "TEXTE: [transcription int?grale sans commentaire]"
        )
        
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[audio_part, prompt]
        )
        
        raw_output = response.text.strip() if response and response.text else ""
        
        lang = "fr"
        transcript = raw_output
        
        for line in raw_output.splitlines():
            line_str = line.strip()
            if line_str.startswith("LANGUE:"):
                val = line_str.replace("LANGUE:", "").strip().lower()
                if "ar" in val:
                    lang = "ar"
                elif "fr" in val:
                    lang = "fr"
            elif line_str.startswith("TEXTE:"):
                transcript = line_str.replace("TEXTE:", "").strip()
        
        if not transcript or transcript == raw_output:
            # Fallback nettoyage si le mod?le n'a pas mis les pr?fixes
            transcript = raw_output.replace("LANGUE: fr", "").replace("LANGUE: ar", "").strip()
            
        return transcript, lang
        
    except Exception as e:
        logger.error(f"Erreur transcription audio: {e}")
        return "Demande d'information immobili?re par message vocal.", "fr"


def generate_female_speech(
    text: str,
    language: str = "fr",
    voice_name: str = "Aoede"
) -> Optional[str]:
    """
    Synth?tise une r?ponse audio avec une voix f?minine douce et professionnelle.
    Utilise gemini-3.8-flash-tts avec la voix f?minine 'Aoede' (ou 'Kore').
    Sauvegarde le fichier WAV et retourne son nom de fichier (ex: 'vocal_12345.wav').
    """
    try:
        client = get_gemini_client()
        
        # Nettoyer le texte pour qu'il soit fluide ? l'oral (retirer les puces ou balises)
        clean_text = text.replace("**", "").replace("#", "").replace("- ", "").strip()
        if len(clean_text) > 800:
            clean_text = clean_text[:800] + "..."
            
        style_instruction = (
            "Voix f?minine ?l?gante, chaleureuse et professionnelle, ?locution fluide et accueillante."
            if language == "fr" else
            "??? ????? ???? ????? ?????? ??? ???? ???? ????? ?????? ????."
        )
        
        interaction = client.interactions.create(
            model="gemini-3.8-flash-tts",
            input=[{
                "type": "user_input",
                "content": [{
                    "type": "text",
                    "text": clean_text,
                    "annotations": [{
                        "type": "speech_metadata",
                        "style": style_instruction,
                    }],
                }],
            }],
            response_format={"type": "audio"},
            generation_config={
                "speech_config": [
                    {"voice": voice_name},  # Voix f?minine Aoede
                ]
            },
        )
        
        if hasattr(interaction, "output_audio") and interaction.output_audio:
            audio_bytes = base64.b64decode(interaction.output_audio.data)
            filename = f"yasmine_{uuid.uuid4().hex[:10]}.wav"
            filepath = os.path.join(AUDIO_CACHE_DIR, filename)
            
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
                
            logger.info(f"Fichier audio g?n?r? avec succ?s: {filename} ({len(audio_bytes)} bytes)")
            return filename
        else:
            logger.warning("Aucun flux audio retourn? par Gemini TTS.")
            return None
            
    except Exception as e:
        logger.error(f"Erreur synth?se vocale TTS: {e}")
        return None
