from __future__ import annotations
import os, logging
from fastapi import FastAPI, Request
from botbuilder.core import ConversationState, MemoryStorage, TurnContext
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials

# --- 1) Intentar CloudAdapter (nuevo). Si no está, fallback al adapter clásico.
USE_CLOUD = True
try:
    from botbuilder.core.cloud_adapter import CloudAdapter  # disponible en 4.14+
    from botframework.connector.auth import ConfigurationBotFrameworkAuthentication
except Exception:
    USE_CLOUD = False
    from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings  # fallback

from .settings import settings
from .bot import TeamsGatewayBot
from .health import router as health_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("teams_gw.app")

# --- 2) Exportar variables EXACTAS que lee el SDK (como en tu servicio que funciona)
APP_ID  = settings.MICROSOFT_APP_ID
APP_PWD = os.getenv("MICROSOFT_APP_PASSWORD", "")
TENANT  = settings.MICROSOFT_APP_TENANT_ID or ""
APP_TYPE = os.getenv("MicrosoftAppType", "SingleTenant")  # igual que en tu otro servicio

# CamelCase (SDK moderno)
os.environ["MicrosoftAppId"] = APP_ID or ""
os.environ["MicrosoftAppPassword"] = APP_PWD or ""
os.environ["MicrosoftAppType"] = APP_TYPE or ""
if TENANT:
    os.environ["MicrosoftAppTenantId"] = TENANT

# UPPER (por compatibilidad con tu .env)
os.environ["MICROSOFT_APP_ID"] = APP_ID or ""
os.environ["MICROSOFT_APP_PASSWORD"] = APP_PWD or ""
if TENANT:
    os.environ["MICROSOFT_APP_TENANT_ID"] = TENANT

app = FastAPI(title="teams_gw")
app.include_router(health_router)

# --- 3) Construir adapter
if USE_CLOUD:
    logger.info("Using CloudAdapter (auth from environment)")
    adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication())
else:
    logger.info("Using BotFrameworkAdapter (fallback)")
    adapter = BotFrameworkAdapter(
        BotFrameworkAdapterSettings(os.environ["MicrosoftAppId"], os.environ["MicrosoftAppPassword"])
    )

conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

logger.info(
    "Startup | app_id_end=%s tenant_set=%s app_type=%s cloud=%s",
    (APP_ID[-6:] if APP_ID else "None"),
    bool(TENANT),
    APP_TYPE,
    USE_CLOUD,
)

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # Confiar en serviceUrl de Teams para poder responder
    if getattr(activity, "service_url", None):
        MicrosoftAppCredentials.trust_service_url(activity.service_url)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/")
async def root():
    return {"service": app.title, "ready": True}
