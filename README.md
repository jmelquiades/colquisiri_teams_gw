# teams_gw

Gateway entre tu **bot de Microsoft Teams** (mismo AppId/AppPassword) y el servicio **N2SQL** (`colquisiri_n2sql_service`).
Recibe mensajes en Teams, arma el **JSON { dataset, intent, params }**, llama a **/v1/query**, y devuelve resultados en **tabla Markdown**.

## Estructura
teams_gw/
├─ README.md
├─ .env.example
├─ requirements.txt
├─ render.yaml
├─ Dockerfile
├─ src/
│ └─ teams_gw/
│ ├─ init.py
│ ├─ app.py
│ ├─ settings.py
│ ├─ n2sql_client.py
│ ├─ bot.py
│ ├─ formatters.py
│ └─ health.py
└─ tests/
└─ test_formatters.py

bash
Copiar código

## Uso local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # completa valores
uvicorn src.teams_gw.app:app --reload --port 8000
Health: GET http://localhost:8000/__ready

Emulator: apuntar a http://localhost:8000/api/messages

Ejemplo desde Teams
css
Copiar código
dt[odoo]: facturas pendientes de pago (cliente,monto,total)
Genera el POST:

json
Copiar código
{ "dataset":"odoo", "intent":"facturas pendientes de pago (cliente,monto,total)", "params":{} }
Despliegue (Render)
Deploy este repo con render.yaml.

En Azure Bot (Channels Registration) cambia el Messaging endpoint a:

arduino
Copiar código
https://<tu-servicio>.onrender.com/api/messages
Valida GET /__ready y prueba en Teams.

Variables principales
Bot: MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD, MICROSOFT_APP_TENANT_ID?, MICROSOFT_APP_OAUTH_SCOPE?

N2SQL: N2SQL_URL, N2SQL_QUERY_PATH(=/v1/query), N2SQL_DATASET(=odoo), N2SQL_API_KEY?

Gateway: N2SQL_TRIGGERS (por defecto dt:,consulta ,n2sql:), N2SQL_MAX_ROWS
