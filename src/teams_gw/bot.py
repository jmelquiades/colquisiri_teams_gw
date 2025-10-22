import logging
from botbuilder.core import ActivityHandler, MessageFactory, TurnContext
from botframework.connector.auth import MicrosoftAppCredentials

log = logging.getLogger("teams_gw.bot")


class TeamsGwBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        # MUY IMPORTANTE: confiar el serviceUrl antes de responder
        try:
            MicrosoftAppCredentials.trust_service_url(
                turn_context.activity.service_url
            )
        except Exception as e:
            log.warning("No se pudo trust_service_url: %s", e)

        # Debug útil
        log.info("Trusted service URL: %s", turn_context.activity.service_url)

        text = (turn_context.activity.text or "").strip()
        reply = f"echo: {text}" if text else "Hola 👋"
        await turn_context.send_activity(MessageFactory.text(reply))
