from __future__ import annotations
import os
import logging
from urllib.parse import urlparse

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

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("teams_gw.app")

app = FastAPI(title="teams_gw")
app.include_router(health_router)

# Mantener el adapter clásico (no cambiamos env vars)
adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
)
ADAPTER_KIND = "BotFrameworkAdapter"

conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # Log de diagnóstico (no bloquea)
    rid = (activity.recipient and activity.recipient.id) or ""
    rid_norm = rid.split(":", 1)[-1] if rid else ""
    log.info(
        "Incoming activity: {'type': %s, 'channel_id': %s, 'service_url': %s, "
        "'conversation_id': %s, 'from_id': %s, 'recipient_id': %s, "
        "'recipient_id_normalized': %s, 'env_app_id': %s}",
        activity.type,
        activity.channel_id,
        activity.service_url,
        (activity.conversation and activity.conversation.id),
        (activity.from_property and activity.from_property.id),
        rid,
        rid_norm,
        settings.MICROSOFT_APP_ID,
    )

    # 🔐 MUY IMPORTANTE: confiar el serviceUrl y el host base antes de responder
    svc = getattr(activity, "service_url", None)
    if svc:
        try:
            MicrosoftAppCredentials.trust_service_url(svc)
            p = urlparse(svc)
            base = f"{p.scheme}://{p.netloc}/"
            MicrosoftAppCredentials.trust_service_url(base)
            log.debug("Trusted serviceUrl: %s and base: %s", svc, base)
        except Exception as e:
            log.warning("Could not trust serviceUrl: %s (%s)", svc, e)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/")
async def root():
    return {"service": app.title, "adapter": ADAPTER_KIND, "ready": True}
