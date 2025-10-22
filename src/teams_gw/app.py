from __future__ import annotations

import json
import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials

from .settings import settings
from .bot import TeamsGatewayBot

# ----------------------------------------------------
# App & logging
# ----------------------------------------------------
logger = logging.getLogger("teams_gw.app")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="teams_gw", version="1.0.0")

# ----------------------------------------------------
# Adapter 4.14.7 (usa settings con app_id y password)
# ¡OJO! Nada de auth_tenant_id aquí (no existe en 4.14)
# ----------------------------------------------------
_adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,
    app_password=settings.MICROSOFT_APP_PASSWORD,
)
adapter = BotFrameworkAdapter(_adapter_settings)

async def _on_turn_error(context: TurnContext, error: Exception):
    logger.exception("on_turn_error: %s", error)
    try:
        await context.send_activity("Lo siento, ocurrió un error procesando tu mensaje.")
    except Exception as send_err:  # noqa: BLE001
        logger.error("No pude enviar el mensaje de error: %s", send_err)

adapter.on_turn_error = _on_turn_error

bot = TeamsGatewayBot()

# ----------------------------------------------------
# Health / info
# ----------------------------------------------------
@app.get("/")
def root() -> dict:
    return {"service": "teams_gw", "adapter": "BotFrameworkAdapter", "ready": True}

@app.get("/__ready")
def ready() -> Response:
    return PlainTextResponse("OK")

@app.get("/__env")
def env_probe() -> JSONResponse:
    return JSONResponse(
        {
            "MICROSOFT_APP_ID_set": bool(settings.MICROSOFT_APP_ID),
            "MICROSOFT_APP_PASSWORD_set": bool(settings.MICROSOFT_APP_PASSWORD),
            "MICROSOFT_APP_TENANT_ID_set": settings.MICROSOFT_APP_TENANT_ID is not None,
        }
    )

# ----------------------------------------------------
# Bot endpoint
# ----------------------------------------------------
@app.post("/api/messages")
async def messages(request: Request) -> Response:
    body = await request.json()
    activity: Activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # Log útil para depurar (sin credenciales)
    info = {
        "type": getattr(activity, "type", None),
        "channel_id": getattr(activity, "channel_id", None),
        "service_url": getattr(activity, "service_url", None),
        "conversation_id": getattr(getattr(activity, "conversation", None), "id", None),
        "from_id": getattr(getattr(activity, "from_property", None), "id", None),
        "recipient_id": getattr(getattr(activity, "recipient", None), "id", None),
        "recipient_id_normalized": (getattr(getattr(activity, "recipient", None), "id", "") or "").replace("28:", ""),
        "env_app_id": settings.MICROSOFT_APP_ID,
    }
    logger.info("Incoming activity: %s", json.dumps(info, ensure_ascii=False))

    # (Opcional) Confiar explícitamente en URLs conocidas de Teams
    service_url = getattr(activity, "service_url", None)
    try:
        if service_url:
            MicrosoftAppCredentials.trust_service_url(service_url)
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/")
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/amer/")
        MicrosoftAppCredentials.trust_service_url("https://api.botframework.com/")
    except Exception as e:  # noqa: BLE001
        logger.warning("No pude registrar trusted service urls: %s", e)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, aux_logic)
        # El 200 es lo que espera el Connector, aunque luego el envío a Teams falle.
        return Response(status_code=200)
    except Exception as e:  # noqa: BLE001
        logger.exception("Connector reply failed")
        # Devolvemos 502 si el fallo ocurre al contestar hacia Teams
        return PlainTextResponse(f"Connector error: {e}", status_code=502)
