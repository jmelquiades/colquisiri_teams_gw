# teams_gw

Gateway entre tu **bot de Microsoft Teams** (mismo AppId/AppPassword) y el servicio **N2SQL** (`colquisiri_n2sql_service`).
Recibe mensajes en Teams, arma el **JSON { dataset, intent, params }**, llama a **/v1/query**, y devuelve resultados en **tabla Markdown** (con paginado y opcionalmente la sentencia SQL).

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

## Requisitos previos

- Python 3.11
- Credenciales de un Bot de Microsoft Teams (AppId/AppPassword/Tenant/Scope)
- Endpoint del servicio N2SQL (`/v1/query`)

## Uso local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # completa valores
uvicorn src.teams_gw.app:app --reload --port 8000
Health: GET http://localhost:8000/__ready

Emulator: apuntar a http://localhost:8000/api/messages

## Tests

```bash
pytest
```

Ejemplo desde Teams
css
Copiar código
dt[odoo]: facturas pendientes de pago (cliente,monto,total)
Genera el POST:

json
Copiar código
{ "dataset":"odoo", "intent":"facturas pendientes de pago (cliente,monto,total)", "params":{} }
## Despliegue en Render

1. Haz fork/clone del repo en tu cuenta.
2. Crea un servicio **Web** en Render usando `render.yaml`.
3. Configura las variables de entorno listadas abajo.
4. En Azure Bot (Channels Registration) apunta el *Messaging endpoint* a  
   `https://<tu-servicio>.onrender.com/api/messages`.
5. Valida `GET /__ready` y prueba desde Teams.

## Variables de entorno

| Categoría | Variable | Descripción |
|-----------|----------|-------------|
| Bot | `MICROSOFT_APP_ID` | AppId del bot de Teams |
| | `MICROSOFT_APP_PASSWORD` | Client secret del AppId |
| | `MICROSOFT_APP_TENANT_ID` | Tenant del bot (SingleTenant) |
| | `MICROSOFT_APP_OAUTH_SCOPE` | Scope para obtener el token (ej. `https://api.botframework.com/.default`) |
| | `MicrosoftAppType` | Render la inyecta como `SingleTenant` mediante `settings` |
| N2SQL | `N2SQL_URL` | URL base del servicio N2SQL |
| | `N2SQL_QUERY_PATH` | Path del endpoint (`/v1/query`) |
| | `N2SQL_DATASET` | Dataset por defecto (ej. `odoo`) |
| | `N2SQL_API_KEY` | Token opcional para N2SQL |
| | `N2SQL_TIMEOUT_S` | Timeout en segundos (30 por defecto) |
| Gateway | `N2SQL_TRIGGERS` | Triggers válidos (`dt:,consulta ,n2sql:`) |
| | `N2SQL_MAX_ROWS` | Filas máximas a renderizar en la respuesta inicial (20) |
| | `N2SQL_MAX_ROWS_EXPANDED` | Filas al pulsar “Ver más filas” (60) |
| | `N2SQL_MAX_ROWS_FINAL` | Si es >0, número final de filas tras una segunda ampliación |
| | `N2SQL_SHOW_SQL` | `true/false` para mostrar la sentencia SQL en la respuesta |
| | `LOG_LEVEL` | Nivel de logging (`INFO`) |

## Uso desde Teams

- Envía mensajes con los triggers configurados, por ejemplo:
  - `dt: facturas pendientes de pago (cliente,fecha,monto,total)`
  - `dt[odoo]: ventas por cliente`
- El bot validará el trigger, enviará la consulta a N2SQL y devolverá una tabla Markdown (hasta `N2SQL_MAX_ROWS` filas) y, si `N2SQL_SHOW_SQL=true`, el bloque SQL.
- Cuando haya más datos, aparecerá el botón **Ver más filas** (usa `messageBack`) que vuelve a renderizar la consulta con `N2SQL_MAX_ROWS_EXPANDED`.
- Si no incluyes el trigger, responderá con las instrucciones de uso.
