from __future__ import annotations

import json
import logging
from typing import Any, Dict

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

# Adapter para SDK 4.14.7 (solo app_id y app_password)
bf_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,
    app_password=settings.MICROSOFT_APP_PASSWORD,
)
adapter = BotFrameworkAdapter(bf_settings)


async def _on_turn_error(context: TurnContext, error: Exception):
    logger.exception("on_turn_error: %s", error)
    try:
        await context.send_activity("Lo siento, hubo un error al procesar tu mensaje.")
    except Exception as send_err:  # noqa: BLE001
        logger.error("Fallo al enviar mensaje de error: %s", send_err)


adapter.on_turn_error = _on_turn_error
bot = TeamsGatewayBot()


@app.get("/")
def root() -> Dict[str, Any]:
    return {"service": "teams_gw", "adapter": "BotFrameworkAdapter", "ready": True}


@app.get("/__ready")
def ready() -> Response:
    return PlainTextResponse("OK")


@app.get("/__env")
def env_dump() -> Dict[str, Any]:
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
    Prueba directa con MSAL al scope del Bot Framework.
    """
    if not settings.MICROSOFT_APP_ID or not settings.MICROSOFT_APP_PASSWORD:
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_credentials",
                "error_description": "Faltan MICROSOFT_APP_ID o MICROSOFT_APP_PASSWORD en el entorno.",
            },
            status_code=500,
        )

    authority = (
        f"https://login.microsoftonline.com/{settings.MICROSOFT_APP_TENANT_ID}"
        if settings.MICROSOFT_APP_TENANT_ID
        else "https://login.microsoftonline.com/organizations"
    )

    cca = msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_APP_ID,
        client_credential=settings.MICROSOFT_APP_PASSWORD,
        authority=authority,
    )
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


@app.post("/api/messages")
async def messages(request: Request) -> Response:
    """
    Endpoint para el Bot Framework Connector.
    """
    body = await request.json()
    activity: Activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    service_url = getattr(activity, "service_url", None)

    # Confiar en los hosts de Teams **antes** de procesar la actividad.
    # En 4.14.7 la lista interna es privada; usamos is_trusted_service_url para verificar.
    try:
        if service_url:
            MicrosoftAppCredentials.trust_service_url(service_url)
        # plus hosts comunes
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/")
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/amer/")
        MicrosoftAppCredentials.trust_service_url("https://api.botframework.com/")
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo registrar trusted service urls: %s", e)

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

    # Log de verificación de confianza (bool) para cada URL relevante
    try:
        checks = {
            "service_url_trusted": bool(service_url and MicrosoftAppCredentials.is_trusted_service_url(service_url)),
            "smba_root_trusted": MicrosoftAppCredentials.is_trusted_service_url("https://smba.trafficmanager.net/"),
            "smba_amer_trusted": MicrosoftAppCredentials.is_trusted_service_url("https://smba.trafficmanager.net/amer/"),
            "api_bf_trusted": MicrosoftAppCredentials.is_trusted_service_url("https://api.botframework.com/"),
        }
        logger.info("Trusted checks: %s", checks)
    except Exception:
        pass

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, aux_logic)
        # Si todo va bien, devolvemos 200 al Connector (independiente de si pudimos responder a Teams).
        return Response(status_code=200)
    except Exception as e:  # noqa: BLE001
        logger.exception("Connector reply failed")
        # Devolvemos 502 para que el channel refleje fallo aguas abajo
        return PlainTextResponse(f"Connector error: {e}", status_code=502)
