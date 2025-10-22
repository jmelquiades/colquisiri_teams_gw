import json
import logging
from fastapi import FastAPI, Request
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
from botframework.connector.auth import MicrosoftAppCredentials

from .settings import settings
from .bot import TeamsGwBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("teams_gw.app")

app = FastAPI()

# Adapter clásico 4.14.7 (solo app_id + app_password)
bf_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,
    app_password=settings.MICROSOFT_APP_PASSWORD,
)
adapter = BotFrameworkAdapter(bf_settings)

async def on_error(turn_context: TurnContext, error: Exception):
    logger.error("on_turn_error: %s", error, exc_info=True)
    try:
        await turn_context.send_activity("Lo siento, ocurrió un error.")
    except Exception as e:
        logger.error("Fallo al enviar mensaje de error: %s", e)

adapter.on_turn_error = on_error

bot = TeamsGwBot()


@app.get("/")
async def root():
    return {"service": "teams_gw", "adapter": "BotFrameworkAdapter", "ready": True}


@app.get("/__ready")
async def ready():
    return {"ok": True}


# Sonda para verificar que en *runtime* podemos obtener token con tus credenciales
@app.get("/__probe/token")
async def probe_token():
    creds = MicrosoftAppCredentials(
        settings.MICROSOFT_APP_ID, settings.MICROSOFT_APP_PASSWORD
    )
    token = await creds.get_access_token()
    return {"ok": bool(token)}


@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # Log útil (sin secretos)
    try:
        logger.info(
            "Incoming activity: %s",
            json.dumps(
                {
                    "type": activity.type,
                    "channel_id": activity.channel_id,
                    "service_url": activity.service_url,
                    "conversation_id": activity.conversation.id if activity.conversation else None,
                    "from_id": activity.from_property.id if activity.from_property else None,
                    "recipient_id": activity.recipient.id if activity.recipient else None,
                    "env_app_id": settings.MICROSOFT_APP_ID,
                }
            ),
        )
    except Exception:
        pass

    await adapter.process_activity(activity, auth_header, lambda ctx: bot.on_turn(ctx))
    # 200 vacío es lo esperado por el Connector
    return {}
