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

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("teams_gw.app")

app = FastAPI(title="teams_gw")
app.include_router(health_router)

# ⚠️ Importante: tomamos ID/SECRET desde settings (que ya acepta camelCase)
APP_ID = settings.MICROSOFT_APP_ID
APP_SECRET = settings.MICROSOFT_APP_PASSWORD

# Construye adapter clásico con credenciales explícitas (sin depender de env)
adapter = BotFrameworkAdapter(BotFrameworkAdapterSettings(APP_ID, APP_SECRET))
conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

logger.info(
    "Startup teams_gw | app_id_end=%s secret_present=%s",
    (APP_ID[-6:] if APP_ID else "None"),
    bool(APP_SECRET),
)

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # Confiar en el serviceUrl de Teams para poder responder
    if getattr(activity, "service_url", None):
        MicrosoftAppCredentials.trust_service_url(activity.service_url)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    await adapter.process_activity(activity, auth_header, aux_logic)
    return {"ok": True}

@app.get("/__cred-check")
async def cred_check():
    # Diagnóstico mínimo sin exponer secretos
    return {
        "adapter": "BotFrameworkAdapter",
        "settings_app_id_end": (APP_ID[-6:] if APP_ID else None),
        "settings_secret_present": bool(APP_SECRET),
        "env_MICROSOFT_APP_PASSWORD_present": bool(os.getenv("MICROSOFT_APP_PASSWORD")),
        "env_MicrosoftAppPassword_present": bool(os.getenv("MicrosoftAppPassword")),
    }

@app.get("/")
async def root():
    return {"service": app.title, "ready": True}
