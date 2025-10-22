from __future__ import annotations
import os, logging
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    ConversationState,
    MemoryStorage,
    TurnContext,
)
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials
from botframework.connector import models as connector_models  # <-- para capturar el error

from .settings import settings
from .bot import TeamsGatewayBot
from .health import router as health_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("teams_gw.app")

app = FastAPI(title="teams_gw")
app.include_router(health_router)

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

    # Confiamos explíticamente serviceUrl y host base (bien para Teams)
    svc = getattr(activity, "service_url", None)
    if svc:
        try:
            MicrosoftAppCredentials.trust_service_url(svc)
            p = urlparse(svc)
            base = f"{p.scheme}://{p.netloc}/"
            MicrosoftAppCredentials.trust_service_url(base)
        except Exception as e:
            log.warning("Could not trust serviceUrl: %s (%s)", svc, e)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, aux_logic)
        return {"ok": True}
    except connector_models.ErrorResponseException as e:
        # Esto nos da el cuerpo que envía el servicio (la clave para saber por qué 401)
        status = getattr(e.response, "status", None)
        reason = getattr(e.response, "reason", None)
        try:
            body_text = await e.response.text()  # aiohttp response
        except Exception:
            body_text = "<no-body>"
        log.error(
            "Connector reply failed: status=%s reason=%s url=%s convo=%s activityId=%s body=%s",
            status, reason, activity.service_url,
            (activity.conversation and activity.conversation.id),
            getattr(activity, "id", None),
            body_text,
        )
        return JSONResponse(status_code=502, content={"ok": False, "error": "connector_unauthorized"})
    except Exception as e:
        log.exception("Unexpected error replying to Teams: %s", e)
        return JSONResponse(status_code=500, content={"ok": False, "error": "unexpected"})
        
@app.get("/")
async def root():
    return {"service": app.title, "adapter": ADAPTER_KIND, "ready": True}
