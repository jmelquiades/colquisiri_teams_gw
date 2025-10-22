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
