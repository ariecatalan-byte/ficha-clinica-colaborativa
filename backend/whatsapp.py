import hashlib, hmac, os
import httpx

TOKEN = os.getenv("WA_ACCESS_TOKEN", "")
PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID", "")
APP_SECRET = os.getenv("WA_APP_SECRET", "")
API = f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages"

def firma_valida(raw: bytes, header: str | None) -> bool:
    """Verifica que el POST venga de Meta (X-Hub-Signature-256)."""
    if not APP_SECRET:
        return False
    esperado = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, header or "")

async def _post(payload: dict):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(API, json=payload, headers={"Authorization": f"Bearer {TOKEN}"})
        if r.status_code >= 400:
            print("WhatsApp error:", r.status_code, r.text)

async def enviar_texto(to: str, texto: str):
    await _post({"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": texto}})

async def enviar_botones(to: str, texto: str, botones: list[tuple[str, str]]):
    """Máximo 3 botones; título de hasta 20 caracteres."""
    await _post({"messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {"type": "button", "body": {"text": texto},
            "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": t[:20]}} for i, t in botones]}}})

def extraer(payload: dict):
    """Devuelve (telefono, tipo, contenido) del primer mensaje, o None."""
    try:
        m = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    except (KeyError, IndexError):
        return None
    tipo = m["type"]
    if tipo == "text":
        return m["from"], "texto", m["text"]["body"]
    if tipo == "interactive":
        return m["from"], "boton", m["interactive"]["button_reply"]["id"]
    if tipo == "audio":
        return m["from"], "audio", m["audio"]["id"]
    return m["from"], tipo, ""
