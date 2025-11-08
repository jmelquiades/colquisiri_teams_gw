from __future__ import annotations
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity
from .settings import settings
from .n2sql_client import client
from .formatters import format_n2sql_payload

TRIGGER_BASES = [p.lower().rstrip(":").strip() for p in settings.triggers]

class TeamsGatewayBot(ActivityHandler):
    def _matches_trigger(self, text: str | None) -> bool:
        if not text:
            return False
        t = text.strip()
        low = t.lower()

        # 1) Triggers directos (ej. "dt:", "n2sql:", "consulta ")
        if any(low.startswith(p.lower()) for p in settings.triggers):
            return True

        # 2) Forma con dataset: "<trigger>[...]:" (ej. "dt[odoo]: ...")
        colon = low.find(":")
        if colon != -1:
            header = low[:colon]               # "dt[odoo]" | "dt"
            base = header.split("[", 1)[0]     # "dt"
            if base in TRIGGER_BASES:
                return True

        return False

    def _extract_query_and_dataset(self, text: str) -> tuple[str, str | None]:
        """Devuelve (query, dataset_override) a partir de:
        - "dt: consulta ..."
        - "dt[odoo]: consulta ..."
        - "consulta ...", "n2sql: ..." (prefijos simples definidos en N2SQL_TRIGGERS)
        """
        t = text.strip()
        low = t.lower()

        # Caso con encabezado y ":", preferido para dataset
        colon = t.find(":")
        if colon != -1:
            header = t[:colon].strip()     # "dt[odoo]" o "dt"
            query = t[colon + 1:].strip()
            base = header.split("[", 1)[0].lower()

            if base in TRIGGER_BASES:
                # dataset opcional entre corchetes
                ds = None
                lb = header.find("[")
                rb = header.find("]")
                if lb != -1 and rb != -1 and rb > lb + 1:
                    ds = header[lb + 1:rb].strip()
                return query, ds

        # Fallback: prefijo simple de settings.triggers (p.ej. "consulta ")
        for prefix in settings.triggers:
            if low.startswith(prefix.lower()):
                return t[len(prefix):].strip(), None

        # Último recurso: todo el texto como consulta
        return t, None

    async def on_message_activity(self, turn_context: TurnContext):
        text = (turn_context.activity.text or "").strip()

        if self._matches_trigger(text):
            query, ds = self._extract_query_and_dataset(text)
            await turn_context.send_activity("Entendido. Consultando…")
            try:
                payload = await client.ask(query, dataset=ds)
                md = format_n2sql_payload(payload)
                await turn_context.send_activity(Activity(text=md, text_format="markdown"))
            except Exception:
                await turn_context.send_activity(
                    "No pude resolver la consulta ahora. Inténtalo de nuevo más tarde."
                )
            return

        await turn_context.send_activity(
            "Para N2SQL usa `dt:` o `dt[dataset]:`. Ej.: `dt[odoo]: facturas pendientes de pago (cliente,monto,total)`"
        )
