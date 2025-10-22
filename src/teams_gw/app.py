from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials

import msal

from .settings import settings
from .bot import TeamsGatewayBot

logger = logging.getLogger("teams_gw.app")

app = FastAPI(title="teams_gw", version="1.0.0")


# -----------------------------
# Adapter (v4.14.x API)
# -----------------------------
bf_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,
    app_password=settings.MICROSOFT_APP_PASSWORD,
    # channel_service=None => público
    auth_tenant_id=settings.MICROSOFT_APP_TENANT_ID,  # None => multitenant
)
adapter = BotFrameworkAdapter(bf_settings)

# Manejo de errores a nivel de turno
async def _on_turn_error(context: TurnContext, error: Exception):
    logger.exception("on_turn_error: %s", error)
    # Intenta avisar al usuario; si falla, sólo log
    try:
        await context.send_activity("Lo siento, hubo un error al procesar tu mensaje.")
    except Exception as send_err:  # noqa: BLE001
        logger.error("Fallo al enviar mensaje de error: %s", send_err)

adapter.on_turn_error = _on_turn_error

# Bot
bot = TeamsGatewayBot()


# -----------------------------
# Rutas auxiliares
# -----------------------------
@app.get("/")
def root() -> Dict[str, Any]:
    return {"service": "teams_gw", "adapter": "BotFrameworkAdapter", "ready": True}


@app.get("/__ready")
def ready() -> Response:
    return PlainTextResponse("OK")


@app.get("/__env")
def env_dump() -> Dict[str, Any]:
    # Útil para verificar que Render cargó variables (sin exponer secretos)
    return {
        "MICROSOFT_APP_ID_set": bool(settings.MICROSOFT_APP_ID),
        "MICROSOFT_APP_PASSWORD_set": bool(settings.MICROSOFT_APP_PASSWORD),
        "MICROSOFT_APP_TENANT_ID_set": settings.MICROSOFT_APP_TENANT_ID is not None,
        "APP_TZ": settings.APP_TZ,
        "N2SQL_URL": settings.N2SQL_URL,
        "N2SQL_QUERY_PATH": settings.N2SQL_QUERY_PATH,
        "N2SQL_DATASET": settings.N2SQL_DATASET,
    }


@app.get("/__auth-probe")
def auth_probe() -> JSONResponse:
    """
    Pide un token vía MSAL usando client_credentials contra el scope del Bot Framework.
    No retorna token; sólo {ok, expires_in|error,...}
    """
    cca = msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_APP_ID,
        client_credential=settings.MICROSOFT_APP_PASSWORD,
        authority=settings.authority,
    )
    # Scope del servicio de Bot Framework (no Graph)
    scopes = ["https://api.botframework.com/.default"]
    result = cca.acquire_token_for_client(scopes=scopes)

    if "access_token" in result:
        return JSONResponse({"ok": True, "expires_in": result.get("expires_in")})
    else:
        return JSONResponse(
            {
                "ok": False,
                "error": result.get("error"),
                "error_description": result.get("error_description"),
            },
            status_code=500,
        )


# -----------------------------
# Webhook de Bot Framework
# -----------------------------
@app.post("/api/messages")
async def messages(request: Request) -> Response:
    """
    Endpoint estándar del Bot Framework. Teams envía Activities aquí.
    """
    body = await request.json()
    activity: Activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # Para evitar problemas de "serviceUrl not trusted" (suele afectar al Emulator, pero dejamos explícito)
    service_url = getattr(activity, "service_url", None)
    if service_url:
        # Confiamos en las URLs de Teams:
        MicrosoftAppCredentials.trust_service_url(service_url)
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/")
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/amer/")

    # Log compacto y útil
    info = {
        "type": getattr(activity, "type", None),
        "channel_id": getattr(activity, "channel_id", None),
        "service_url": service_url,
        "conversation_id": getattr(getattr(activity, "conversation", None), "id", None),
        "from_id": getattr(getattr(activity, "from_property", None), "id", None),
        "recipient_id": getattr(getattr(activity, "recipient", None), "id", None),
        "recipient_id_normalized": (getattr(getattr(activity, "recipient", None), "id", "") or "").replace("28:", ""),
        "env_app_id": settings.MICROSOFT_APP_ID,
    }
    logger.info("Incoming activity: %s", json.dumps(info, ensure_ascii=False))

    trusted = list(MicrosoftAppCredentials.trusted_host_names)
    logger.info("Trusted service URLs: %s", trusted)

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, aux_logic)
        # 200 OK: el conector no requiere body
        return Response(status_code=200)
    except Exception as e:  # noqa: BLE001
        # Los 401/403 de Connector suelen materializarse aquí como ErrorResponseException
        # Al menos deja trazabilidad clara:
        logger.error(
            "Connector reply failed: %s", e, exc_info=True,
        )
        # No exponemos detalles crudos; 502 imita 'Bad Gateway' visto en tus logs
        return PlainTextResponse("Connector Unauthorized", status_code=502)
