from __future__ import annotations
import os, logging
from fastapi import FastAPI, Request
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    ConversationState,
    MemoryStorage,
    TurnContext,
)
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials
from .settings import settings
from .bot import TeamsGatewayBot
from .health import router as health_router

# Logging básico
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("teams_gw.app")

# Exporta nombres que la SDK también busca
os.environ.setdefault("MicrosoftAppId", settings.MICROSOFT_APP_ID)
os.environ.setdefault("MicrosoftAppPassword", os.getenv("MICROSOFT_APP_PASSWORD", ""))
if settings.MICROSOFT_APP_TENANT_ID:
    os.environ.setdefault("MicrosoftAppTenantId", settings.MICROSOFT_APP_TENANT_ID)

app = FastAPI(title="teams_gw")
app.include_router(health_router)

adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(settings.MICROSOFT_APP_ID, os.getenv("MICROSOFT_APP_PASSWORD", ""))
)

conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

# guardamos la última activity (diagnóstico)
_last_activity_info = {}

logger.info(
    "Startup teams_gw | app_id_ending=%s tenant_set=%s",
    settings.MICROSOFT_APP_ID[-6:] if settings.MICROSOFT_APP_ID else "None",
    bool(settings.MICROSOFT_APP_TENANT_ID),
)

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # confiar en el serviceUrl (ayuda en escenarios raros)
    if getattr(activity, "service_url", None):
        MicrosoftAppCredentials.trust_service_url(activity.service_url)

    # log + memoria para diagnóstico
    try:
        recipient_id = getattr(getattr(activity, "recipient", None), "id", None)
    except Exception:
        recipient_id = None
    _last_activity_info.update({
        "type": getattr(activity, "type", None),
        "channel_id": getattr(activity, "channel_id", None),
        "service_url": getattr(activity, "service_url", None),
        "conversation_id": getattr(getattr(activity, "conversation", None), "id", None),
        "from_id": getattr(getattr(activity, "from_property", None), "id", None),
        "recipient_id": recipient_id,
        "env_app_id": settings.MICROSOFT_APP_ID,
        "env_app_id_ending": settings.MICROSOFT_APP_ID[-6:] if settings.MICROSOFT_APP_ID else None,
    })
    logger.info("Incoming activity: %s", _last_activity_info)

    if recipient_id and recipient_id != settings.MICROSOFT_APP_ID:
        logger.warning("recipient.id (%s) != MICROSOFT_APP_ID (%s)", recipient_id, settings.MICROSOFT_APP_ID)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/__last-activity")
async def last_activity():
    return _last_activity_info or {"info": "no activity yet"}

@app.get("/")
async def root():
    return {"service": app.title, "ready": True}
