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

# === Adapter: tolerante a credenciales faltantes ===
bf_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,                 # puede ser None
    app_password=settings.MICROSOFT_APP_PASSWORD,     # puede ser None
    auth_tenant_id=settings.MICROSOFT_APP_TENANT_ID,  # multitenant si None -> organizations
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
        "app_id_alias_used": settings.app_id_alias_used,
        "app_secret_alias_used": settings.app_secret_alias_used,
        "APP_TZ": settings.APP_TZ,
        "N2SQL_URL": settings.N2SQL_URL,
        "N2SQL_QUERY_PATH": settings.N2SQL_QUERY_PATH,
        "N2SQL_DATASET": settings.N2SQL_DATASET,
    }


@app.get("/__auth-probe")
def auth_probe() -> JSONResponse:
    """
    Prueba directa con MSAL usando el scope de Bot Framework.
    Útil para confirmar que las credenciales funcionan sin pasar por el SDK.
    """
    if not settings.has_bot_credentials:
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_credentials",
                "error_description": "No hay MICROSOFT_APP_ID/MICROSOFT_APP_PASSWORD en el entorno (se aceptan alias).",
                "app_id_alias_used": settings.app_id_alias_used,
                "app_secret_alias_used": settings.app_secret_alias_used,
            },
            status_code=500,
        )

    cca = msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_APP_ID,
        client_credential=settings.MICROSOFT_APP_PASSWORD,
        authority=settings.authority,  # organizations o tenant específico
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

    # Confiar en las URLs de Teams para evitar errores 401 por host no confiable
    service_url = getattr(activity, "service_url", None)
    if service_url:
        MicrosoftAppCredentials.trust_service_url(service_url)
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/")
        MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/amer/")

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

    try:
        logger.info(
            "Trusted service URLs: %s",
            list(getattr(MicrosoftAppCredentials, "trusted_host_names", set())),
        )
    except Exception:
        pass

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, aux_logic)
        # Si no lanza excepción, el SDK ya respondió al Connector correctamente
        return Response(status_code=200)
    except Exception as e:  # noqa: BLE001
        logger.error(
            "Connector reply failed: %s", e, exc_info=True
        )
        # Responder 502 para que el channel sepa que falló aguas abajo
        return PlainTextResponse("Connector Unauthorized", status_code=502)
