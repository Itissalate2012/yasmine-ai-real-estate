"""
main.py - Serveur FastAPI Yasmine AI (Compatible Vercel Serverless & 24/7 WhatsApp)
"""
import os
import ssl
import json
import time
import logging
import urllib.request
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent_reasoning import process_real_estate_query
from properties_db import get_all_projects, get_all_apartments, find_apartment_by_id, find_project_by_id, save_custom_catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YasmineServer")

SSL_CTX = ssl._create_unverified_context()

# Configuration Green-API WhatsApp
API_HOST = os.environ.get("GREEN_API_HOST", "https://7107.api.greenapi.com")
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE", "710722779599")
API_TOKEN = os.environ.get("GREEN_API_TOKEN", "f673c7ee4d784c87beb7d9c9a900eb66eaa3c143c507451787")
BASE_URL = f"{API_HOST}/waInstance{ID_INSTANCE}"

app = FastAPI(title="Yasmine - Real Estate AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# -------------------------------------------------------------
# Fonctions Utilitaires WhatsApp
# -------------------------------------------------------------
def send_wa_text(chat_id: str, message: str):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = json.dumps({"chatId": chat_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Erreur envoi texte WA: {e}")
        return None

def send_wa_image(chat_id: str, image_url: str, caption: str = ""):
    try:
        req_img = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_img, context=SSL_CTX, timeout=10) as r:
            img_bytes = r.read()
    except Exception as e:
        logger.error(f"Erreur téléch image: {e}")
        return None

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
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Erreur envoi image WA: {e}")
        return None

# -------------------------------------------------------------
# 1. Routes Web (Client & Admin)
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Agent Yasmine en ligne</h1>"

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    admin_file = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(admin_file):
        with open(admin_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Admin introuvable</h1>"

@app.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    full_path = os.path.join(STATIC_DIR, file_path)
    if os.path.exists(full_path):
        media_type = "text/css" if file_path.endswith(".css") else "application/javascript" if file_path.endswith(".js") else "text/plain"
        with open(full_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), media_type=media_type)
    raise HTTPException(status_code=404)

# -------------------------------------------------------------
# 2. Routes Données & Catalogue
# -------------------------------------------------------------
@app.get("/api/admin/data")
async def get_admin_data():
    return {"projects": get_all_projects(), "apartments": get_all_apartments()}

class AdminSaveRequest(BaseModel):
    projects: List[Dict[str, Any]]
    apartments: List[Dict[str, Any]]

@app.post("/api/admin/save")
async def save_admin_data(req: AdminSaveRequest):
    save_custom_catalog(req.projects, req.apartments)
    return {"status": "success", "message": "Catalogue mis à jour avec succès !"}

# -------------------------------------------------------------
# 3. Route Chat Web
# -------------------------------------------------------------
class TextChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []
    language: Optional[str] = "auto"

@app.post("/api/chat/text")
async def chat_text(req: TextChatRequest):
    agent_output = process_real_estate_query(
        user_message=req.message,
        input_modality="text",
        conversation_history=req.conversation_history,
        preferred_language=req.language or "auto"
    )
    return {
        "modality": "text",
        "response_text": agent_output.get("response_text", ""),
        "apartment_cards": agent_output.get("apartment_cards", []),
        "project_cards": agent_output.get("project_cards", [])
    }

# -------------------------------------------------------------
# 4. Webhook WhatsApp 24h/24 (Green-API)
# -------------------------------------------------------------
@app.post("/api/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    """Reçoit automatiquement les messages WhatsApp 24h/24."""
    try:
        body = await request.json()
        if body.get("typeWebhook") != "incomingMessageReceived":
            return {"status": "ignored"}

        sender_data = body.get("senderData", {})
        chat_id = sender_data.get("chatId")
        message_data = body.get("messageData", {})
        type_msg = message_data.get("typeMessage")

        if not chat_id:
            return {"status": "no_chat_id"}

        # Traitement message texte
        if type_msg in ["textMessage", "extendedTextMessage"]:
            text = message_data.get("textMessageData", {}).get("textMessage") or message_data.get("extendedTextMessageData", {}).get("text", "")
            if text:
                logger.info(f"📩 WhatsApp entrant: {text}")
                agent_output = process_real_estate_query(user_message=text, input_modality="text")
                response_text = agent_output.get("response_text", "")
                
                # Envoi réponse texte
                send_wa_text(chat_id, response_text)

                # Envoi photo
                apts = agent_output.get("apartment_cards", [])
                photo_url = apts[0]["photos"][0] if apts and apts[0].get("photos") else get_all_apartments()[0]["photos"][0]
                caption = f"🛋️ {apts[0].get('title_fr', 'Appartement')} - {apts[0].get('price_mad', 0):,} MAD" if apts else "Nos offres d'appartements"
                send_wa_image(chat_id, photo_url, caption)

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur Webhook WA: {e}")
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)