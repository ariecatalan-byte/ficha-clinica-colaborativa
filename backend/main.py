import os
import ipaddress
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")
from fastapi import FastAPI, Request, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import whatsapp as wa

app = FastAPI(title="Ficha Clínica Colaborativa")
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "cambia-este-token")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv(
    "DASHBOARD_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

SESIONES: dict[str, dict] = {}   # teléfono -> estado (reemplazar por PostgreSQL)
CASOS: list[dict] = []           # bandeja de enfermería
SIGUIENTE_ID_CASO = 1

PALABRAS_CRISIS = ["suicid", "matarme", "quitarme la vida", "no quiero vivir", "hacerme daño"]
MSG_CRISIS = ("Lamento que estés pasando por esto. No estás solo/a. Un profesional de enfermería "
              "fue avisado y te contactará. Si estás en peligro ahora, llama al *4141 (línea de "
              "prevención del suicidio, Chile) o al 131 (SAMU).")

PASOS = [
    ("animo", "¿Cómo te sientes hoy?", [("animo_bien", "😄 Bien"), ("animo_medio", "😐 Más o menos"), ("animo_mal", "😟 Mal")]),
    ("med", "¿Tomaste tu medicación?", [("med_si", "Sí"), ("med_no", "No"), ("med_aveces", "A veces")]),
    ("cita", "¿Asistirás a tu próxima cita?", [("cita_si", "Sí"), ("cita_no", "No puedo asistir")]),
    ("enf", "¿Quieres hablar con enfermería?", [("enf_si", "Sí, por favor"), ("enf_no", "No, gracias")]),
]

def triage(r: dict) -> str:
    """Reglas simples y auditables. Sugiere; un profesional decide."""
    p = (2 if r.get("animo") == "animo_mal" else 0) + (1 if r.get("med") == "med_no" else 0) \
      + (1 if r.get("cita") == "cita_no" else 0) + (1 if r.get("enf") == "enf_si" else 0)
    return "alto" if p >= 3 else "medio" if p >= 1 else "bajo"

def crear_caso(tel: str, urgencia: str, resp: dict, nota: str = ""):
    global SIGUIENTE_ID_CASO
    CASOS.append({
        "id": SIGUIENTE_ID_CASO,
        "telefono": tel,
        "urgencia": urgencia,
        "respuestas": resp.copy(),
        "nota": nota,
        "validado": False,
    })
    SIGUIENTE_ID_CASO += 1

def exigir_acceso_local(req: Request):
    """La bandeja clínica de esta versión solo está disponible en el equipo local."""
    host = req.client.host if req.client else ""
    try:
        es_local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        es_local = False
    if not es_local:
        raise HTTPException(403, "La bandeja solo está disponible localmente.")

@app.get("/")
def inicio():
    return FileResponse(Path(__file__).resolve().parent.parent / "index.html")

@app.get("/acompanamiento")
def pagina_acompanamiento():
    return FileResponse(Path(__file__).resolve().parent.parent / "acompanamiento.html")

@app.get("/inicio-acompanamiento")
def formulario_acompanamiento():
    return FileResponse(Path(__file__).resolve().parent.parent / "formulario-acompanamiento.html")

def enlace_acompanamiento(motivo: str) -> str | None:
    partes = urlsplit(PUBLIC_BASE_URL)
    if partes.scheme != "https" or not partes.netloc or partes.path not in ("", "/") or partes.query or partes.fragment:
        return None
    hostname = partes.hostname or ""
    try:
        if not ipaddress.ip_address(hostname).is_global:
            return None
    except ValueError:
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return None
    return f"{PUBLIC_BASE_URL}/inicio-acompanamiento?{urlencode({'motivo': motivo})}"

async def avanzar(tel: str):
    s = SESIONES[tel]
    if s["paso"] < len(PASOS):
        _, pregunta, botones = PASOS[s["paso"]]
        await wa.enviar_botones(tel, pregunta, botones)
    else:
        u = triage(s["resp"])
        crear_caso(tel, u, s["resp"])
        s["paso"] = -1
        mensaje = "¡Gracias! Enfermería recibió tus respuestas. Escribe *hola* cuando quieras responder de nuevo."
        if u == "alto" or s["resp"].get("enf") == "enf_si":
            motivo = "urgencia-alta" if u == "alto" else "enfermeria"
            enlace = enlace_acompanamiento(motivo)
            if enlace:
                mensaje += f"\n\nInformación y próximos pasos: {enlace}"
            else:
                print("PUBLIC_BASE_URL no es una URL HTTPS pública; no se envió el enlace de acompañamiento.")
        await wa.enviar_texto(tel, mensaje)

async def procesar(tel: str, tipo: str, contenido: str):
    s = SESIONES.setdefault(tel, {"paso": -1, "consiente": False, "resp": {}})
    if tipo == "texto" and any(k in contenido.lower() for k in PALABRAS_CRISIS):
        crear_caso(tel, "alto", s["resp"], "Posible riesgo vital: contactar de inmediato")
        enlace = enlace_acompanamiento("urgencia-alta")
        mensaje = MSG_CRISIS
        if enlace:
            mensaje += f"\n\nInformación y próximos pasos: {enlace}"
        else:
            print("PUBLIC_BASE_URL no es una URL HTTPS pública; no se envió el enlace de acompañamiento.")
        return await wa.enviar_texto(tel, mensaje)
    if tipo == "boton" and contenido == "consent_si":
        s.update(consiente=True, paso=0, resp={})
        return await avanzar(tel)
    if tipo == "boton" and contenido == "consent_no":
        s["consiente"] = False
        return await wa.enviar_texto(tel, "Entendido. No guardaremos tus respuestas. Puedes escribir *hola* si cambias de opinión.")
    if tipo == "boton" and s["paso"] >= 0:
        clave = PASOS[s["paso"]][0]
        s["resp"][clave] = contenido
        s["paso"] += 1
        return await avanzar(tel)
    if tipo == "audio" and s["consiente"]:
        crear_caso(tel, "medio", s["resp"], f"Audio recibido (media_id={contenido}); pendiente de revisión")
        return await wa.enviar_texto(tel, "Recibimos tu audio. Enfermería lo revisará.")
    if not s["consiente"]:
        return await wa.enviar_botones(tel,
            "Hola 👋 Soy el bot de acompañamiento de tu equipo de salud. Tus respuestas serán vistas por enfermería y tu equipo tratante. ¿Aceptas participar?",
            [("consent_si", "Acepto"), ("consent_no", "No acepto")])
    s.update(paso=0, resp={})
    await avanzar(tel)

@app.get("/webhook")
def verificar(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"),
              challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(403)

@app.post("/webhook")
async def entrante(req: Request, bg: BackgroundTasks):
    raw = await req.body()
    if not wa.firma_valida(raw, req.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "Firma inválida")
    msg = wa.extraer(await req.json())
    if msg:
        bg.add_task(procesar, *msg)   # responder 200 rápido a Meta
    return {"ok": True}

def casos_ordenados():
    return sorted(CASOS, key=lambda c: ({"alto": 0, "medio": 1, "bajo": 2}.get(c["urgencia"], 3), c["id"]))

@app.get("/api/casos")
def listar_casos(req: Request):
    exigir_acceso_local(req)
    return casos_ordenados()

@app.get("/bandeja")
def bandeja(req: Request):
    exigir_acceso_local(req)
    return casos_ordenados()

@app.post("/api/casos/{caso_id}/validar")
def validar_caso(caso_id: int, req: Request):
    exigir_acceso_local(req)
    caso = next((c for c in CASOS if c["id"] == caso_id), None)
    if caso is None:
        raise HTTPException(404, "Caso no encontrado")
    caso["validado"] = True
    return caso

@app.post("/bandeja/{i}/validar")
def validar_indice(i: int, req: Request):
    exigir_acceso_local(req)
    if i < 0 or i >= len(CASOS):
        raise HTTPException(404, "Caso no encontrado")
    CASOS[i]["validado"] = True
    return CASOS[i]
