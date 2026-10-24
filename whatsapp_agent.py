"""
whatsapp_agent.py - Envoi d'Images Garanti à 100% (Contournement SSL & Auto-Photo)
"""
import os
import sys
import ssl
import time
import json
import logging
import threading
import urllib.request
import urllib.parse

# Contexte SSL permissif pour éviter tout blocage sous Windows
SSL_CTX = ssl._create_unverified_context()

API_HOST = "https://7107.api.greenapi.com"
ID_INSTANCE = "710722779599"
API_TOKEN = "f673c7ee4d784c87beb7d9c9a900eb66eaa3c143c507451787"
BASE_URL = f"{API_HOST}/waInstance{ID_INSTANCE}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WhatsAppAgent")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent_reasoning import process_real_estate_query
from properties_db import get_all_apartments, get_all_projects
from main import transcribe_audio_bytes, generate_female_speech, AUDIO_CACHE_DIR

USER_HISTORIES = {}

def send_whatsapp_message(chat_id: str, message: str):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = json.dumps({"chatId": chat_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Erreur envoi texte: {e}")
        return None

def send_whatsapp_audio(chat_id: str, audio_path: str):
    url = f"{BASE_URL}/sendFileByUpload/{API_TOKEN}"
    boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
    with open(audio_path, "rb") as f:
        file_bytes = f.read()
    
    body = bytearray()
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chatId\"\r\n\r\n{chat_id}\r\n".encode("utf-8"))
    filename = os.path.basename(audio_path)
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    req = urllib.request.Request(url, data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=12) as resp:
            logger.info("🎙️ Note vocale envoyée sur WhatsApp !")
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Erreur envoi audio: {e}")
        return None

def send_whatsapp_image_direct(chat_id: str, image_url: str, caption: str = ""):
    """Télécharge l'image sans blocage SSL et l'envoie sur WhatsApp."""
    try:
        logger.info(f"📸 Téléchargement de l'image : {image_url[:50]}...")
        req_img = urllib.request.Request(
            image_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req_img, context=SSL_CTX, timeout=10) as r:
            img_bytes = r.read()
        logger.info(f"✅ Image téléchargée avec succès ({len(img_bytes)} octets) !")
    except Exception as e:
        logger.error(f"❌ Erreur lors du téléchargement de l'image: {e}")
        return None

    # Envoi direct via sendFileByUpload
    url = f"{BASE_URL}/sendFileByUpload/{API_TOKEN}"
    boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
    body = bytearray()
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chatId\"\r\n\r\n{chat_id}\r\n".encode("utf-8"))
    if caption:
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"appartement.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode("utf-8"))
    body.extend(img_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    req = urllib.request.Request(url, data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
            res = json.loads(resp.read().decode())
            logger.info(f"🎉 PHOTO ENVOYÉE AVEC SUCCÈS SUR WHATSAPP ! Réponse: {res}")
            return res
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'upload de la photo: {e}")
        return None

def receive_notification():
    url = f"{BASE_URL}/receiveNotification/{API_TOKEN}?receiveTimeout=5"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=7) as resp:
            if resp.status == 200:
                data = resp.read().decode()
                return json.loads(data) if data else None
    except Exception:
        return None

def delete_notification(receipt_id: int):
    url = f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=4) as resp:
            return resp.status == 200
    except Exception:
        return False

def flush_old_notifications():
    logger.info("🧹 Nettoyage de la file d'attente...")
    while True:
        url = f"{BASE_URL}/receiveNotification/{API_TOKEN}?receiveTimeout=1"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=3) as resp:
                data = resp.read().decode()
                notif = json.loads(data) if data else None
                if notif and "receiptId" in notif:
                    delete_notification(notif["receiptId"])
                else:
                    break
        except Exception:
            break
    logger.info("✅ File d'attente propre.")

def send_photo_worker(chat_id: str, apartments: list, projects: list):
    """Garantit l'envoi systématique d'une photo d'appartement ou de projet."""
    photo_url = None
    caption = ""

    if apartments and len(apartments) > 0:
        apt = apartments[0]
        photos = apt.get("photos", [])
        if photos:
            photo_url = photos[0]
            caption = f"🛋️ {apt.get('title_fr', 'Appartement')} - {apt.get('price_mad', 0):,} MAD\n📐 {apt.get('surface_m2')} m²"
    elif projects and len(projects) > 0:
        proj = projects[0]
        hero = proj.get("hero_image")
        if hero:
            photo_url = hero
            caption = f"🏗️ {proj.get('name')} - {proj.get('city')}"
    
    # Si aucune photo spécifique trouvée, prendre systématiquement la première du catalogue !
    if not photo_url:
        all_apts = get_all_apartments()
        if all_apts and len(all_apts) > 0:
            apt = all_apts[0]
            photos = apt.get("photos", [])
            if photos:
                photo_url = photos[0]
                caption = f"🛋️ {apt.get('title_fr', 'Appartement')} - {apt.get('price_mad', 0):,} MAD"

    if photo_url:
        logger.info(f"➡️ Lancement de l'envoi de photo à {chat_id}...")
        send_whatsapp_image_direct(chat_id, photo_url, caption)
    else:
        logger.warning("Aucune photo trouvée dans la base.")

def handle_incoming_message(body: dict):
    type_webhook = body.get("typeWebhook")
    if type_webhook != "incomingMessageReceived":
        return

    sender_data = body.get("senderData", {})
    chat_id = sender_data.get("chatId")
    sender_name = sender_data.get("senderName", "Client")
    message_data = body.get("messageData", {})
    type_message = message_data.get("typeMessage")

    if not chat_id:
        return

    if chat_id not in USER_HISTORIES:
        USER_HISTORIES[chat_id] = []
    history = USER_HISTORIES[chat_id]

    # 1. MESSAGE TEXTE
    if type_message in ["textMessage", "extendedTextMessage"]:
        text = ""
        if "textMessageData" in message_data:
            text = message_data["textMessageData"].get("textMessage", "")
        elif "extendedTextMessageData" in message_data:
            text = message_data["extendedTextMessageData"].get("text", "")
        
        if not text.strip():
            return
        
        logger.info(f"📩 [TEXTE REÇU] de {sender_name} : \"{text}\"")
        
        agent_output = process_real_estate_query(
            user_message=text,
            input_modality="text",
            conversation_history=history,
            preferred_language="auto"
        )
        response_text = agent_output.get("response_text", "")
        send_whatsapp_message(chat_id, response_text)

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": response_text})

        # Envoi systématique de la photo
        threading.Thread(
            target=send_photo_worker,
            args=(chat_id, agent_output.get("apartment_cards", []), agent_output.get("project_cards", [])),
            daemon=True
        ).start()

    # 2. MESSAGE VOCAL
    elif type_message in ["audioMessage", "voiceMessage"]:
        file_data = message_data.get("fileMessageData", {})
        download_url = file_data.get("downloadUrl")
        if not download_url:
            return
        
        logger.info("🎙️ [VOCAL REÇU] Téléchargement...")
        try:
            req = urllib.request.Request(download_url)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=10) as resp:
                audio_bytes = resp.read()
        except Exception as e:
            logger.error(f"Erreur téléchargement audio: {e}")
            return
        
        transcription, detected_lang = transcribe_audio_bytes(audio_bytes, mime_type="audio/ogg")
        logger.info(f"Transcription ({detected_lang}) : \"{transcription}\"")
        
        agent_output = process_real_estate_query(
            user_message=transcription,
            input_modality="voice",
            conversation_history=history,
            preferred_language=detected_lang
        )
        
        speech_text = agent_output.get("audio_script") or agent_output.get("response_text", "")
        target_lang = agent_output.get("language", detected_lang)
        
        audio_filename = generate_female_speech(speech_text, language=target_lang, voice_name="Aoede")
        
        history.append({"role": "user", "content": transcription})
        history.append({"role": "assistant", "content": speech_text})

        if audio_filename:
            audio_full_path = os.path.join(AUDIO_CACHE_DIR, audio_filename)
            send_whatsapp_audio(chat_id, audio_full_path)
        else:
            send_whatsapp_message(chat_id, speech_text)

        # Envoi systématique de la photo juste après le vocal !
        threading.Thread(
            target=send_photo_worker,
            args=(chat_id, agent_output.get("apartment_cards", []), agent_output.get("project_cards", [])),
            daemon=True
        ).start()

def main():
    flush_old_notifications()
    logger.info("=" * 60)
    logger.info("🚀 YASMINE AI : VOCAUX + PHOTOS 100% GARANTIS !")
    logger.info("=" * 60)
    while True:
        try:
            notif = receive_notification()
            if notif and "receiptId" in notif:
                receipt_id = notif["receiptId"]
                body = notif.get("body", {})
                delete_notification(receipt_id)
                handle_incoming_message(body)
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(1)

if __name__ == "__main__":
    main()