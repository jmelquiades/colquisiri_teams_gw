import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from botbuilder.core import (
    ActivityHandler,
    TurnContext,
    BotFrameworkAdapter,
)
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials
from botframework.connector.aio import ConnectorClient

import jwt  # para inspección del token sin verificación

from .settings import settings

logger = logging.getLogger("teams_gw.app")

app = FastAPI()

# Adapter con las credenciales del bot (NO cambiamos tus envs)
adapter = BotFrameworkAdapter(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)

# ===== Import robusto del bot =====
AppBot = None
try:
    from .bot import MyBot as AppBot  # si tu clase se llama MyBot
except Exception:
    try:
        from .bot import AppBot as AppBot  # si tu clase se llama AppBot
    except Exception:
        try:
            from .bot import Bot as AppBot  # si tu clase se llama Bot
        except Exception:
            AppBot = None

# Fallback bot (por si no existe ninguna de las clases anteriores)
if AppBot is None:
    class FallbackBot(ActivityHandler):
        async def on_message_activity(self, turn_context: TurnContext):
            await turn_context.send_activity(Activity(type="message", text="✅ Bot operativo (fallback)."))
    AppBot = FallbackBot

bot = AppBot()

# Última actividad entrante para el probe
LAST = {"activity": None}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
async def root():
    return {"service": getattr(settings, "SERVICE_NAME", "teams_gw"),
            "adapter": "BotFrameworkAdapter",
            "ready": True}


@app.get("/__ready")
async def ready():
    return {"ok": True, "ts": _now_iso()}


@app.get("/__env")
async def env():
    return {
        "MICROSOFT_APP_ID_set": bool(settings.MICROSOFT_APP_ID),
        "MICROSOFT_APP_PASSWORD_set": bool(settings.MICROSOFT_APP_PASSWORD),
        "MICROSOFT_APP_TENANT_ID_set": bool(getattr(settings, "MICROSOFT_APP_TENANT_ID", None)),
        "N2SQL_URL": getattr(settings, "N2SQL_URL", None),
        "APP_TZ": getattr(settings, "APP_TZ", None),
    }


@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)

    info = {
        "type": getattr(activity, "type", None),
        "channel_id": getattr(activity, "channel_id", None),
        "service_url": getattr(activity, "service_url", None),
        "conversation_id": getattr(getattr(activity, "conversation", None), "id", None),
        "from_id": getattr(getattr(activity, "from_property", None), "id", None),
        "recipient_id": getattr(getattr(activity, "recipient", None), "id", None),
    }
    env_app_id = settings.MICROSOFT_APP_ID
    info["recipient_id_normalized"] = (info["recipient_id"] or "").split(":", 1)[-1]
    info["env_app_id"] = env_app_id
    logger.info(f"Incoming activity: {info}")

    # Confiar serviceUrl que llega y prefijos comunes
    su = (activity.service_url or "").rstrip("/") + "/"
    if su != "/":
        MicrosoftAppCredentials.trust_service_url(su)
    MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/")
    MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/amer/")
    logger.info(f"Trusted service URLs: {[su, 'https://smba.trafficmanager.net/', 'https://smba.trafficmanager.net/amer/']}")

    # Guardar última actividad para el probe
    LAST["activity"] = {
        "service_url": su,
        "conversation_id": activity.conversation.id if activity.conversation else None,
        "reply_to_id": getattr(activity, "id", None),
    }

    auth_header = request.headers.get("Authorization", "")
    try:
        async def aux_logic(turn_context: TurnContext):
            await bot.on_turn(turn_context)

        await adapter.process_activity(activity, auth_header, aux_logic)
        return Response(status_code=201)
    except Exception:
        logger.exception("process_activity failed")
        raise


# ====== DIAGNÓSTICO ======

@app.get("/__bf-token")
async def bf_token():
    """
    Devuelve las claims del token que usa el SDK para hablar con el Connector.
    Verifica que:
      - aud == "https://api.botframework.com"
      - appid (o azp) == settings.MICROSOFT_APP_ID
    """
    creds = MicrosoftAppCredentials(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
    token = await creds.get_access_token()
    hdr = jwt.get_unverified_header(token)
    claims = jwt.decode(token, options={"verify_signature": False})
    return {
        "preview": token[:28] + "...",
        "aud": claims.get("aud"),
        "appid": claims.get("appid") or claims.get("azp"),
        "iss": claims.get("iss"),
        "nbf": claims.get("nbf"),
        "exp": claims.get("exp"),
        "header_kid": hdr.get("kid"),
    }


@app.post("/__connector-probe")
async def connector_probe():
    """
    Intenta responder a la última actividad recibida usando ConnectorClient directo.
    Usa el mismo par AppId/Password y serviceUrl que el SDK.
    """
    if not LAST["activity"]:
        return {"ok": False, "error": "no_last_activity"}

    a = LAST["activity"]
    creds = MicrosoftAppCredentials(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
    client = ConnectorClient(credentials=creds, base_url=a["service_url"])

    reply = Activity(type="message", text=f"probe @ { _now_iso() }")

    try:
        res = await client.conversations.reply_to_activity(a["conversation_id"], a["reply_to_id"], reply)
        status = getattr(res, "_status_code", None)
        return {"ok": True, "status": status}
    except Exception as ex:
        # Log explícito
        status = getattr(getattr(ex, "response", None), "status_code", None)
        reason = getattr(getattr(ex, "response", None), "reason", None)
        logger.error(
            "Connector reply failed: status=%s reason=%s url=%s convo=%s activityId=%s",
            status, reason, a["service_url"], a["conversation_id"], a["reply_to_id"]
        )
        body = "<no-body>"
        try:
            if hasattr(ex, "response") and hasattr(ex.response, "text"):
                body = await ex.response.text()
        except Exception:
            pass
        return {"ok": False, "status": status, "reason": reason, "body": body}
