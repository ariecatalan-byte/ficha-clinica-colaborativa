import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request, Query, HTTPException, BackgroundTasks
import whatsapp as wa

app = FastAPI(title="Ficha Clínica Colaborativa")
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "cambia-este-token")

SESIONES: dict[str, dict] = {}   # teléfono -> estado (reemplazar por PostgreSQL)
CASOS: list[dict] = []           # bandeja de enfermería

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
    CASOS.append({"telefono": tel, "urgencia": urgencia, "respuestas": resp, "nota": nota, "validado": False})

async def avanzar(tel: str):
    s = SESIONES[tel]
    if s["paso"] < len(PASOS):
        _, pregunta, botones = PASOS[s["paso"]]
        await wa.enviar_botones(tel, pregunta, botones)
    else:
        u = triage(s["resp"])
        crear_caso(tel, u, s["resp"])
        s["paso"] = -1
        await wa.enviar_texto(tel, "¡Gracias! Enfermería recibió tus respuestas. Escribe *hola* cuando quieras responder de nuevo.")

async def procesar(tel: str, tipo: str, contenido: str):
    s = SESIONES.setdefault(tel, {"paso": -1, "consiente": False, "resp": {}})
    if tipo == "texto" and any(k in contenido.lower() for k in PALABRAS_CRISIS):
        crear_caso(tel, "alto", s["resp"], "Posible riesgo vital: contactar de inmediato")
        return await wa.enviar_texto(tel, MSG_CRISIS)
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

@app.get("/bandeja")
def bandeja():
    return sorted(CASOS, key=lambda c: {"alto": 0, "medio": 1, "bajo": 2}[c["urgencia"]])

@app.post("/bandeja/{i}/validar")
def validar(i: int):
    CASOS[i]["validado"] = True
    return CASOS[i]
