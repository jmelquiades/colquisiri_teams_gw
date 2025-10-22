from __future__ import annotations

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext


class TeamsGatewayBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        text = (turn_context.activity.text or "").strip()
        reply = f"Echo: {text}" if text else "Hola 👋"
        await turn_context.send_activity(MessageFactory.text(reply))

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text("¡Hola! Estoy listo en este canal de Teams.")
                )
