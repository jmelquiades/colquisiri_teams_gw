from __future__ import annotations
import os, logging
from fastapi import FastAPI, Request
from botbuilder.core import ConversationState, MemoryStorage, TurnContext
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials

# --- Auth/Adapter: preferir CloudAdapter si existe, si no fallback ---
USE_CLOUD = False
try:
    # Algunos builds no exportan CloudAdapter en __init__, import directo del módulo:
    from botbuilder.core.cloud_adapter import CloudAdapter  # type: ignore
    from botframework.connector.auth import ConfigurationBotFrameworkAuthentication
    USE_CLOUD = True
except Exception:
    from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings  # fallback

from .settings import settings
from .bot import TeamsGatewayBot
from .health import router as health_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("teams_gw.app")

# La SDK también lee estas envs:
os.environ.setdefault("MicrosoftAppId", settings.MICROSOFT_APP_ID)
os.environ.setdefault("MicrosoftAppPassword", os.getenv("MICROSOFT_APP_PASSWORD", ""))
if settings.MICROSOFT_APP_TENANT_ID:
    os.environ.setdefault("MicrosoftAppTenantId", settings.MICROSOFT_APP_TENANT_ID)
# Si tu app es single-tenant, deja SingleTenant; si es multi-tenant, cambia a MultiTenant
os.environ.setdefault("MicrosoftAppType", os.getenv("MicrosoftAppType", "SingleTenant"))

app = FastAPI(title="teams_gw")
app.include_router(health_router)

if USE_CLOUD:
    logger.info("Using CloudAdapter")
    adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication())
else:
    logger.info("Using BotFrameworkAdapter (fallback)")
    adapter = BotFrameworkAdapter(
        BotFrameworkAdapterSettings(
            settings.MICROSOFT_APP_ID,
            os.getenv("MICROSOFT_APP_PASSWORD", ""),
        )
    )

conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

_last_activity_info = {}

logger.info(
    "Startup teams_gw | app_id_ending=%s tenant_set=%s app_type=%s",
    settings.MICROSOFT_APP_ID[-6:] if settings.MICROSOFT_APP_ID else "None",
    bool(settings.MICROSOFT_APP_TENANT_ID),
    os.getenv("MicrosoftAppType"),
)

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # Confiar en el serviceUrl de Teams para los replies
    if getattr(activity, "service_url", None):
        MicrosoftAppCredentials.trust_service_url(activity.service_url)

    rid = getattr(getattr(activity, "recipient", None), "id", None)
    rid_norm = rid.split(":", 1)[-1] if isinstance(rid, str) else rid
    _last_activity_info.update({
        "type": getattr(activity, "type", None),
        "channel_id": getattr(activity, "channel_id", None),
        "service_url": getattr(activity, "service_url", None),
        "conversation_id": getattr(getattr(activity, "conversation", None), "id", None),
        "from_id": getattr(getattr(activity, "from_property", None), "id", None),
        "recipient_id": rid,
        "recipient_id_normalized": rid_norm,
        "env_app_id": settings.MICROSOFT_APP_ID,
    })
    logger.info("Incoming activity: %s", _last_activity_info)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    # Ambos adapters exponen process_activity
    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/__last-activity")
async def last_activity():
    return _last_activity_info or {"info": "no activity yet"}

@app.get("/")
async def root():
    return {"service": app.title, "ready": True}
