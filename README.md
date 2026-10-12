# Ficha Clínica Colaborativa (prototipo)

## Abrir en Visual Studio Code
1. Descomprime la carpeta.
2. VS Code > Archivo > Abrir carpeta... > selecciona `ficha-clinica-colaborativa`.
3. Instala la extensión **Live Server** (Ritwick Dey).
4. Clic derecho en `index.html` > **Open with Live Server**.

## Backend (esqueleto, opcional)
```
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows  (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn main:app --reload
```
Docs automáticas en http://127.0.0.1:8000/docs

## Estructura
- `index.html`: prototipo front (paciente, enfermería, equipo tratante)
- `backend/main.py`: webhook de WhatsApp y triage de ejemplo
- Siguiente paso: reemplazar los datos de ejemplo por base de datos PostgreSQL y login por rol.

Aviso: son datos de ejemplo. Antes de usar datos reales, revisar consentimiento y normativa de datos de salud.

## Conectar WhatsApp real (Cloud API de Meta)
1. Entra a developers.facebook.com > Crear app > tipo **Business** > agrega el producto **WhatsApp**.
2. En *WhatsApp > API Setup* verás un **número de prueba**, su **Phone number ID** y un **token temporal**. Agrega tu celular como destinatario de prueba.
3. En `backend/` copia `.env.example` a `.env` y completa los 4 valores (el App Secret está en *Configuración de la app > Básica*).
4. Levanta el servidor: `uvicorn main:app --reload --port 8000`
5. Expónlo con un túnel: `ngrok http 8000` (copia la URL https).
6. En *WhatsApp > Configuration > Webhook*: URL `https://TU-URL/webhook`, token = tu `WA_VERIFY_TOKEN`; suscribe el campo **messages**.
7. Escribe "hola" al número de prueba desde tu celular. Revisa los casos en http://127.0.0.1:8000/bandeja

Para producción necesitas: número propio verificado, Business verificado en Meta, token permanente (usuario de sistema), HTTPS real y base de datos en vez de memoria.
Los textos de crisis (*4141, 131) deben ser revisados por tu equipo clínico antes de usarse con pacientes.
