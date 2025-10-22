from __future__ import annotations
import re
from botbuilder.core import ActivityHandler, TurnContext
from .n2sql_client import client

TRIGGERS = re.compile(
    r"^(?P<pfx>dt|n2sql|consulta)\s*(?::|\s)\s*(?P<payload>.+)$",
    re.IGNORECASE | re.DOTALL,
)

class TeamsGatewayBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        text = (turn_context.activity.text or "").strip()
        m = TRIGGERS.match(text)
        if not m:
            await turn_context.send_activity(
                "Hola 👋. Usa `consulta: <pregunta>` o `n2sql: <pregunta>`."
            )
            return

        question = m.group("payload").strip()
        result = await client.query(question)

        if not result.get("ok"):
            err = result.get("error") or result.get("data", {}).get("text", "")
            await turn_context.send_activity(f"❌ Error consultando N2SQL: {err}")
            return

        data = result["data"]
        # Intenta un resumen simple
        if isinstance(data, dict):
            rows = data.get("rows") or data.get("data")
            if rows and isinstance(rows, list):
                preview = rows[:5]
                await turn_context.send_activity(f"✅ {len(rows)} filas. Muestra:\n```\n{preview}\n```")
                return

        await turn_context.send_activity(f"✅ Respuesta:\n```\n{data}\n```")
