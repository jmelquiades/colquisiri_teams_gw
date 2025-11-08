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
| | `N2SQL_SHOW_SQL` | `true/false` para mostrar la sentencia SQL en la respuesta |
| | `LOG_LEVEL` | Nivel de logging (`INFO`) |

## Uso desde Teams

- Envía mensajes con los triggers configurados, por ejemplo:
  - `dt: facturas pendientes de pago (cliente,fecha,monto,total)`
  - `dt[odoo]: ventas por cliente`
- El bot validará el trigger, enviará la consulta a N2SQL y devolverá una tabla Markdown (hasta `N2SQL_MAX_ROWS` filas) y, si `N2SQL_SHOW_SQL=true`, el bloque SQL.
- Cuando haya más datos, aparecerá el botón **Ver más filas** (usa `messageBack`) que vuelve a renderizar la consulta con `N2SQL_MAX_ROWS_EXPANDED`.
- Puedes escribir `faq` o `preguntas frecuentes` para ver una tarjeta con consultas rápidas y ejecutarlas con un clic.
- Si no incluyes el trigger, responderá con las instrucciones de uso.

## Arquitectura y flujo

1. **Teams → FastAPI**: el Channel Service de Teams envía cada actividad al endpoint `/api/messages`. FastAPI (`src/teams_gw/app.py`) valida encabezados, confía en el `serviceUrl` y canaliza la petición al Bot Framework Adapter.
2. **Adapter → Bot**: el `BotFrameworkAdapter` inicializa el `TurnContext` y entrega el evento a `TeamsGatewayBot` (`src/teams_gw/bot.py`), que mantiene estado en memoria para paginar respuestas.
3. **Bot → N2SQL**: cuando detecta un trigger válido, arma `{dataset,intent,params}` mediante `N2SQLClient` (`src/teams_gw/n2sql_client.py`) y hace un `POST` contra `/v1/query`.
4. **Respuesta → Markdown**: los datos recibidos se convierten en tabla Markdown con `format_n2sql_payload` (`src/teams_gw/formatters.py`). Si hay más filas, se guarda contexto para que el botón “Ver más” solicite la siguiente vista.
5. **FAQ/Acciones**: las tarjetas AdaptiveCard permiten disparar consultas frecuentes o expandir resultados mediante eventos `invoke/messageBack`, que el bot procesa sin requerir texto adicional del usuario.

## Archivos Python principales

| Archivo | Descripción |
|---------|-------------|
| `src/teams_gw/app.py` | Inicializa FastAPI, parchea `MicrosoftAppCredentials` para usar MSAL, confía en `serviceUrl`, registra rutas de salud y procesa actividades entrantes. |
| `src/teams_gw/bot.py` | `ActivityHandler` que valida triggers (`dt:, n2sql:, consulta`), arma consultas, controla paginado, renderiza tablas Markdown y genera la tarjeta FAQ con botones horizontales. |
| `src/teams_gw/settings.py` | Capa de configuración con Pydantic Settings; expone alias compatibles con Azure/Render y valores como triggers, límites y zona horaria. |
| `src/teams_gw/n2sql_client.py` | Cliente HTTP asíncrono (httpx) que construye `dataset/intents/params`, agrega el API key si existe y gestiona el timeout. |
| `src/teams_gw/formatters.py` | Convierte distintos formatos de payload (`columns/rows`, `data`, listas de dicts) a Markdown, respeta límites de filas y añade el SQL cuando está habilitado. |
| `src/teams_gw/health.py` | Endpoints de diagnóstico (`/__ready`, `/health`, `/__env`, `/__auth-probe`) para monitoreo y pruebas de credenciales sin exponer secretos. |
| `teams_autoanswer.py` | Script opcional RPA para macOS que detecta llamadas de Teams via API de Accesibilidad y acepta automáticamente (útil en centros de atención). |
| `tests/test_formatters.py` | Pruebas unitarias que validan la lógica de `format_n2sql_payload`, distintos formatos y el límite de filas. |

Con este mapa puedes continuar agregando nuevas tarjetas, comandos o datasets manteniendo claro dónde vive cada pieza del gateway.
