from __future__ import annotations
import logging
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

log = logging.getLogger("teams_gw.app")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="teams_gw")
app.include_router(health_router)

# Adapter clásico, sin cambiar envs
adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
)

conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # --- Diagnóstico útil en logs ---
    env_app = settings.MICROSOFT_APP_ID
    rid = (activity.recipient and activity.recipient.id) or ""
    rid_norm = rid.split(":", 1)[-1] if rid else ""
    log.info(
        "Incoming activity: {'type': %s, 'channel_id': %s, 'service_url': %s, "
        "'conversation_id': %s, 'from_id': %s, 'recipient_id': %s, 'recipient_id_normalized': %s, 'env_app_id': %s}",
        activity.type,
        activity.channel_id,
        activity.service_url,
        (activity.conversation and activity.conversation.id),
        (activity.from_property and activity.from_property.id),
        rid,
        rid_norm,
        env_app,
    )

    # 1) Confiar el service_url ANTES de responder (mitiga 401 del conector)
    if getattr(activity, "service_url", None):
        MicrosoftAppCredentials.trust_service_url(activity.service_url)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/")
async def root():
    return {"service": app.title, "ready": True}

# Sonda para comprobar que el par AppId/AppPassword obtiene token (sin tocar envs)
@app.get("/__auth-probe")
async def auth_probe():
    creds = MicrosoftAppCredentials(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
    token = await creds.get_access_token()
    # si falla, levanta PermissionError y verás el stack en logs; si no, ok
    return {"ok": True, "expires_in": 3599 if token else 0}
