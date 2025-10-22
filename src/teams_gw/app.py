from __future__ import annotations
import os
import logging
from typing import Optional

from fastapi import FastAPI, Request, Header
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials

from .settings import settings
from .bot import TeamsGatewayBot

log = logging.getLogger("teams_gw.app")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="teams_gw")

# Adapter SIN tenant explícito (evita tokens con audiencia equivocada)
adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,
    app_password=settings.MICROSOFT_APP_PASSWORD,
)
adapter = BotFrameworkAdapter(adapter_settings)
bot = TeamsGatewayBot()

def _trust_service_urls(service_url: str) -> list[str]:
    """
    Confiamos en: 1) URL completa recibida, 2) raíz del host, 3) base regional /amer/
    """
    urls = []
    if service_url:
        su = service_url.strip()
        urls.append(su)
        # host root
        if su.startswith("https://smba.trafficmanager.net/"):
            urls.append("https://smba.trafficmanager.net/")
            # base regional
            parts = su.split("/")
            # https: '' smba.trafficmanager.net amer <guid> ''
            if len(parts) > 4 and parts[3]:
                urls.append(f"https://smba.trafficmanager.net/{parts[3]}/")
        for u in urls:
            try:
                MicrosoftAppCredentials.trust_service_url(u)
            except Exception:
                pass
    return urls

@app.get("/")
async def root():
    return {"service": settings.SERVICE_NAME, "adapter": "BotFrameworkAdapter", "ready": True}

@app.get("/__ready")
async def ready():
    return {"ok": True}

@app.get("/__env")
async def env_probe():
    return {
        "MICROSOFT_APP_ID_set": bool(settings.MICROSOFT_APP_ID),
        "MICROSOFT_APP_PASSWORD_set": bool(settings.MICROSOFT_APP_PASSWORD),
        "MICROSOFT_APP_TENANT_ID_set": settings.MICROSOFT_APP_TENANT_ID is not None,
        "N2SQL_URL": settings.N2SQL_URL,
        "N2SQL_QUERY_PATH": settings.N2SQL_QUERY_PATH,
        "N2SQL_DATASET": settings.N2SQL_DATASET,
        "APP_TZ": settings.APP_TZ,
    }

@app.post("/api/messages")
async def messages(request: Request, authorization: Optional[str] = Header(None)):
    body = await request.json()
    activity = Activity().deserialize(body)

    # Logs útiles
    rid = (activity.recipient.id or "").replace("28:", "")
    log.info(
        "Incoming activity: {'type': %s, 'channel_id': %s, 'service_url': %s, 'conversation_id': %s, 'from_id': %s, 'recipient_id': %s, 'recipient_id_normalized': %s, 'env_app_id': %s}",
        activity.type,
        getattr(activity.channel_data, "channel", "msteams") if hasattr(activity, "channel_data") else "msteams",
        activity.service_url,
        activity.conversation.id if activity.conversation else None,
        activity.from_property.id if activity.from_property else None,
        activity.recipient.id if activity.recipient else None,
        rid,
        settings.MICROSOFT_APP_ID,
    )

    trusted = _trust_service_urls(activity.service_url or "")
    log.info("Trusted service URLs: %s", trusted)

    auth_header = authorization or ""

    async def aux_logic(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, aux_logic)
        return {"ok": True}
    except Exception as e:
        # Cuando el Connector responde 401, el SDK levanta una excepción genérica sin body
        log.error(
            "Connector reply failed: status=None reason=Unauthorized url=%s convo=%s activityId=%s body=<no-body>",
            activity.service_url,
            activity.conversation.id if activity.conversation else None,
            activity.id,
        )
        raise


# ... imports existentes ...
import asyncio
import json
from datetime import datetime, timezone

import jwt  # >>> DIAGNÓSTICO
from botframework.connector.auth import MicrosoftAppCredentials  # >>> DIAGNÓSTICO
from botframework.connector.aio import ConnectorClient  # >>> DIAGNÓSTICO

from .settings import settings
from .bot import MyBot  # o como se llame tu handler

app = FastAPI()
adapter = BotFrameworkAdapter(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
bot = MyBot()

# Guarda la última actividad para probar el reply
LAST = {"activity": None}  # >>> DIAGNÓSTICO

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

@app.get("/")
async def root():
    return {"service": settings.SERVICE_NAME, "adapter": "BotFrameworkAdapter", "ready": True}

@app.get("/__ready")
async def ready():
    return {"ok": True, "ts": _now_iso()}

@app.get("/__env")
async def env():
    return {
        "MICROSOFT_APP_ID_set": bool(settings.MICROSOFT_APP_ID),
        "MICROSOFT_APP_PASSWORD_set": bool(settings.MICROSOFT_APP_PASSWORD),
        "MICROSOFT_APP_TENANT_ID_set": bool(settings.MICROSOFT_APP_TENANT_ID),
        "N2SQL_URL": settings.N2SQL_URL,
        "APP_TZ": settings.APP_TZ,
    }

# ============ WEBHOOK ============
@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)

    # Log corto
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
    app.logger.info(f"Incoming activity: {info}")

    # Confía serviceUrl (por si cambia el path)
    su = activity.service_url.rstrip("/") + "/"
    MicrosoftAppCredentials.trust_service_url(su)
    MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/")
    MicrosoftAppCredentials.trust_service_url("https://smba.trafficmanager.net/amer/")
    app.logger.info(f"Trusted service URLs: {[su, 'https://smba.trafficmanager.net/', 'https://smba.trafficmanager.net/amer/']}")

    # Guarda última actividad para el probe
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
    except Exception as e:
        app.logger.exception("process_activity failed")
        raise

# ============ DIAGNÓSTICO ============
@app.get("/__bf-token")  # Muestra claims del token que usaría el SDK
async def bf_token():
    creds = MicrosoftAppCredentials(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
    token = await creds.get_access_token()
    # Decodifica sin verificar firmas, solo para ver 'aud', 'appid', etc.
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

@app.post("/__connector-probe")  # Intenta responder a la última actividad vía ConnectorClient directo
async def connector_probe():
    if not LAST["activity"]:
        return {"ok": False, "error": "no_last_activity"}

    a = LAST["activity"]
    creds = MicrosoftAppCredentials(settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD)
    client = ConnectorClient(credentials=creds, base_url=a["service_url"])

    txt = f"probe @ { _now_iso() }"
    activity = Activity(
        type="message",
        text=txt,
    )

    try:
        res = await client.conversations.reply_to_activity(
            a["conversation_id"], a["reply_to_id"], activity
        )
        return {"ok": True, "status": getattr(res, "_status_code", None)}
    except Exception as ex:
        # Log más explícito
        app.logger.error(
            "Connector reply failed: status=%s reason=%s url=%s convo=%s activityId=%s",
            getattr(getattr(ex, "response", None), "status_code", None),
            getattr(getattr(ex, "response", None), "reason", getattr(ex, "message", None)),
            a["service_url"],
            a["conversation_id"],
            a["reply_to_id"],
        )
        # Intenta extraer cuerpo si existe
        body = None
        try:
            body = ex.response.text() if hasattr(ex.response, "text") else None
        except Exception:
            body = "<no-body>"
        return {
            "ok": False,
            "status": getattr(getattr(ex, "response", None), "status_code", None),
            "reason": getattr(getattr(ex, "response", None), "reason", None),
            "body": body if isinstance(body, str) else "<no-body>",
        }
