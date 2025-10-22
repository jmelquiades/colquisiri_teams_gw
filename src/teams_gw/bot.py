from __future__ import annotations

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.core import MessageFactory


class TeamsGatewayBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        # Echo simple para validar ida y vuelta con Teams
        text = turn_context.activity.text or ""
        reply = f"echo: {text}"
        await turn_context.send_activity(MessageFactory.text(reply))
