from future import annotations
import re
from botbuilder.core import ActivityHandler, TurnContext
from .settings import settings
from .n2sql_client import client
from .formatters import format_n2sql_payload

Formatos soportados:
- dt: <consulta>
- dt[dataset]: <consulta>
- n2sql[dataset]: <consulta>

DATASET_PATTERN = re.compile(
r"^(?P<pfx>dt|n2sql|consulta)\s*(?:
(
?
𝑃
<
𝑑
𝑠
>
[
\w
\-
]
+
)
(?P<ds>[\w\-]+))?:\s*(?P<q>.+)$",
re.IGNORECASE,
)

class TeamsGatewayBot(ActivityHandler):
def _matches_trigger(self, text: str | None) -> bool:
if not text:
return False
t = text.strip().lower()
return any(t.startswith(prefix.lower()) for prefix in settings.triggers)

def _parse_query(self, text: str) -> tuple[str, str | None]:
    """Devuelve (query, dataset_override)."""
    m = DATASET_PATTERN.match(text.strip())
    if m:
        return m.group("q").strip(), (m.group("ds") or None)
    # fallback: quita prefijo simple
    t = text.strip()
    for prefix in settings.triggers:
        if t.lower().startswith(prefix.lower()):
            return t[len(prefix):].strip(), None
    return t, None

async def on_message_activity(self, turn_context: TurnContext):
    text = (turn_context.activity.text or "").strip()

    if self._matches_trigger(text):
        query, ds = self._parse_query(text)
        await turn_context.send_activity("Entendido. Consultando…")
        try:
            payload = await client.ask(query, dataset=ds)
            md = format_n2sql_payload(payload)
            await turn_context.send_activity(md)
        except Exception:
            await turn_context.send_activity(
                "No pude resolver la consulta ahora. Inténtalo de nuevo más tarde."
            )
        return

    await turn_context.send_activity(
        "Para N2SQL usa `dt:` o `dt[dataset]:`. Ej.: `dt[odoo]: facturas pendientes de pago (cliente,monto,total)`"
    )


