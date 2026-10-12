# Ficha Clínica Colaborativa (prototipo)

## Interfaz conectada al backend

1. Instala Python y las dependencias: `pip install -r backend/requirements.txt`.
2. Inicia el servicio desde la carpeta `backend`: `uvicorn main:app --reload --port 8000`.
3. Abre `http://127.0.0.1:8000/`. La interfaz y la bandeja usan el mismo backend.
4. La pestaña de enfermería consulta los casos de WhatsApp cada 5 segundos y permite marcarlos como revisados. Si el backend no está disponible, solo muestra la demostración local.

La bandeja de esta versión está restringida al equipo local y guarda los casos en memoria; se vacían al reiniciar. No publiques ni expongas la bandeja a Internet: antes de usarla en una clínica hacen falta autenticación por roles, base de datos, controles de privacidad y revisión clínica.

## Enlace de acompañamiento por WhatsApp
Al completar la encuesta, el bot adjunta `/inicio-acompanamiento` cuando la persona solicita hablar con enfermería o el triage resulta alto. El formulario pide tipo de ayuda y ánimo; esas selecciones solo se muestran en el resumen siguiente y no se notifican ni se guardan en la ficha clínica. Los teléfonos de ayuda inmediata permanecen disponibles desde la primera pantalla.

Configura `PUBLIC_BASE_URL` en `backend/.env` con el origen HTTPS público que sirve esta aplicación, por ejemplo `https://mi-dominio.example`. No uses `127.0.0.1`: el teléfono no puede abrir una dirección local. Sin una URL HTTPS válida, el bot no envía el enlace. Esta versión de demostración no está lista para exponer la bandeja clínica públicamente; usa solo datos sintéticos hasta implementar autenticación y controles de acceso adecuados.

## Filtro CIE-10
El panel Equipo tratante permite filtrar el catálogo por grupo, categoría o código específico y muestra los recuentos de ejemplo compartidos. No hay un `solicitudes_medicas_2025.csv` en este proyecto, por lo que no consulta solicitudes reales ni ejecuta las consultas SQL/Pandas proporcionadas. Para conectar esos filtros a expedientes, agrega el dataset y valida previamente su acceso y clasificación clínica.

## Abrir la demostración en Visual Studio Code
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
Documentación de la API en http://127.0.0.1:8000/docs

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
7. Escribe "hola" al número de prueba desde tu celular. Revisa los casos en http://127.0.0.1:8000/ o http://127.0.0.1:8000/bandeja

Para producción necesitas: número propio verificado, Business verificado en Meta, token permanente (usuario de sistema), HTTPS real y base de datos en vez de memoria.
Los textos de crisis (*4141, 131) deben ser revisados por tu equipo clínico antes de usarse con pacientes.
