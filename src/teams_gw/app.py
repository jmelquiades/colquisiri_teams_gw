from __future__ import annotations

import os
import logging
import msal
from fastapi import FastAPI, Request
from botbuilder.schema import Activity
from botbuilder.core import ConversationState, MemoryStorage, TurnContext
from botframework.connector.auth import MicrosoftAppCredentials

from .settings import settings
from .bot import TeamsGatewayBot
from .health import router as health_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("teams_gw.app")

app = FastAPI(title="teams_gw")
app.include_router(health_router)

# --- Preferir CloudAdapter; si no está, caer al clásico ---
USE_CLOUD = True
AdapterKind = "CloudAdapter"
try:
    try:
        from botbuilder.core import CloudAdapter  # 4.14.x
    except Exception:
        from botbuilder.core.cloud_adapter import CloudAdapter  # algunas builds
    from botframework.connector.auth import ConfigurationBotFrameworkAuthentication
except Exception:
    USE_CLOUD = False
    AdapterKind = "BotFrameworkAdapter"
    from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings  # type: ignore

# Respetar tus mismas variables (multitenant) sin renombrar nada
os.environ["MicrosoftAppId"] = settings.MICROSOFT_APP_ID
os.environ["MicrosoftAppPassword"] = settings.MICROSOFT_APP_PASSWORD
os.environ["MicrosoftAppType"] = os.getenv("MicrosoftAppType", "MultiTenant")
if settings.MICROSOFT_APP_TENANT_ID:
    os.environ["MicrosoftAppTenantId"] = settings.MICROSOFT_APP_TENANT_ID

if USE_CLOUD:
    auth = ConfigurationBotFrameworkAuthentication()  # lee envs arriba
    adapter = CloudAdapter(auth)
else:
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

    # Diagnóstico mínimo
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

    # 🔐 MUY IMPORTANTE: confiar el serviceUrl ANTES de responder
    if getattr(activity, "service_url", None):
        MicrosoftAppCredentials.trust_service_url(activity.service_url)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/")
async def root():
    return {"service": app.title, "adapter": AdapterKind, "ready": True}

# Probas token AAD contra Bot Framework (no cambia tus envs)
@app.get("/__auth-probe")
async def auth_probe():
    app_msal = msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_APP_ID,
        client_credential=settings.MICROSOFT_APP_PASSWORD,
        authority="https://login.microsoftonline.com/organizations",
    )
    tok = app_msal.acquire_token_for_client(scopes=["https://api.botframework.com/.default"])
    return {
        "ok": bool(tok.get("access_token")),
        "expires_in": tok.get("expires_in"),
        "error": tok.get("error"),
        "error_description": tok.get("error_description"),
    }
