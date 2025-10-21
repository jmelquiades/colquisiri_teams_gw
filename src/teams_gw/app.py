from __future__ import annotations
import os, logging, msal
from fastapi import FastAPI, Request
from botbuilder.core import ConversationState, MemoryStorage, TurnContext
from botbuilder.schema import Activity
from botbuilder.core.cloud_adapter import CloudAdapter
from botframework.connector.auth import (
    ConfigurationBotFrameworkAuthentication,
    MicrosoftAppCredentials,
)
from .settings import settings
from .bot import TeamsGatewayBot
from .health import router as health_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("teams_gw.app")

app = FastAPI(title="teams_gw")
app.include_router(health_router)

# === Forzar a que CloudAdapter lea exactamente estas credenciales (MultiTenant) ===
os.environ["MicrosoftAppId"] = settings.MICROSOFT_APP_ID
os.environ["MicrosoftAppPassword"] = settings.MICROSOFT_APP_PASSWORD
# Respetamos tu configuración actual (MultiTenant) sin pedir cambios
os.environ["MicrosoftAppType"] = os.getenv("MicrosoftAppType", "MultiTenant")

# Construimos CloudAdapter con configuración por entorno
adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication())
conversation_state = ConversationState(MemoryStorage())
bot = TeamsGatewayBot()

logger.info(
    "Startup teams_gw | app_id_end=%s app_type=%s",
    settings.MICROSOFT_APP_ID[-6:],
    os.environ["MicrosoftAppType"],
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

# ===== Probes de diagnostico (no exponen secretos) =====
@app.get("/__cred-check")
async def cred_check():
    return {
        "MicrosoftAppId_end": settings.MICROSOFT_APP_ID[-6:],
        "MicrosoftAppPassword_present": bool(settings.MICROSOFT_APP_PASSWORD),
        "MicrosoftAppType": os.environ.get("MicrosoftAppType"),
    }

@app.get("/__auth-probe")
async def auth_probe():
    # Pide token como app para el scope de Bot Framework (MultiTenant)
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

@app.get("/")
async def root():
    return {"service": app.title, "ready": True}
