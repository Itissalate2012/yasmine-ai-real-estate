"""
main.py - Serveur FastAPI Yasmine AI (Sécurisé par Mot de Passe Admin sur Vercel)
"""
import os
import ssl
import json
import time
import secrets
import logging
import urllib.request
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from agent_reasoning import process_real_estate_query
from properties_db import get_all_projects, get_all_apartments, save_custom_catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YasmineServer")

SSL_CTX = ssl._create_unverified_context()

# Sécurité Administrateur
security = HTTPBasic()
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Yasmine@2026")

def check_admin_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_ok = secrets.compare_digest(credentials.username, ADMIN_USER)
    is_pass_ok = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Accès refusé : identifiants administrateur incorrects.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

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
# 1. Routes Publiques (Clients)
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Agent Yasmine en ligne</h1>"

@app.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    full_path = os.path.join(STATIC_DIR, file_path)
    if os.path.exists(full_path):
        media_type = "text/css" if file_path.endswith(".css") else "application/javascript" if file_path.endswith(".js") else "text/plain"
        with open(full_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), media_type=media_type)
    raise HTTPException(status_code=404)

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
# 2. Routes Sécurisées (ADMIN SEULEMENT 🔒)
# -------------------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def serve_admin(admin_user: str = Depends(check_admin_credentials)):
    """Seul un admin authentifié peut voir cette page."""
    admin_file = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(admin_file):
        with open(admin_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Admin introuvable</h1>"

@app.get("/api/admin/data")
async def get_admin_data(admin_user: str = Depends(check_admin_credentials)):
    """Données réservées à l'administrateur."""
    return {"projects": get_all_projects(), "apartments": get_all_apartments()}

class AdminSaveRequest(BaseModel):
    projects: List[Dict[str, Any]]
    apartments: List[Dict[str, Any]]

@app.post("/api/admin/save")
async def save_admin_data(req: AdminSaveRequest, admin_user: str = Depends(check_admin_credentials)):
    """Seul un admin peut enregistrer les modifications de prix."""
    save_custom_catalog(req.projects, req.apartments)
    return {"status": "success", "message": "Catalogue mis à jour avec succès !"}

# -------------------------------------------------------------
# 3. Webhook WhatsApp 24h/24 (Green-API)
# -------------------------------------------------------------
def send_wa_text(chat_id: str, message: str):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = json.dumps({"chatId": chat_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Erreur texte WA: {e}")
        return None

def send_wa_image(chat_id: str, image_url: str, caption: str = ""):
    try:
        req_img = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_img, context=SSL_CTX, timeout=10) as r:
            img_bytes = r.read()
    except Exception as e:
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
    except Exception:
        return None

@app.post("/api/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    try:
        body = await request.json()
        if body.get("typeWebhook") != "incomingMessageReceived":
            return {"status": "ignored"}

        sender_data = body.get("senderData", {})
        chat_id = sender_data.get("chatId")
        message_data = body.get("messageData", {})
        type_msg = message_data.get("typeMessage")

        if not chat_id:
            return {"status": "no_chat"}

        if type_msg in ["textMessage", "extendedTextMessage"]:
            text = message_data.get("textMessageData", {}).get("textMessage") or message_data.get("extendedTextMessageData", {}).get("text", "")
            if text:
                agent_output = process_real_estate_query(user_message=text, input_modality="text")
                send_wa_text(chat_id, agent_output.get("response_text", ""))

                apts = agent_output.get("apartment_cards", [])
                photo_url = apts[0]["photos"][0] if apts and apts[0].get("photos") else get_all_apartments()[0]["photos"][0]
                caption = f"🛋️ {apts[0].get('title_fr', 'Appartement')} - {apts[0].get('price_mad', 0):,} MAD" if apts else "Nos offres d'appartements"
                send_wa_image(chat_id, photo_url, caption)

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur Webhook WA: {e}")
        return {"status": "error"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)