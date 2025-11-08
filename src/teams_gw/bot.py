from __future__ import annotations

import logging
from typing import Any

from botbuilder.core import ActivityHandler, ConversationState, MessageFactory, TurnContext
from botbuilder.schema import ActionTypes, Activity, Attachment, CardAction, HeroCard
from .settings import settings
from .n2sql_client import client
from .formatters import format_n2sql_payload

TRIGGER_BASES = [p.lower().rstrip(":").strip() for p in settings.triggers]
HISTORY_LIMIT = 5

log = logging.getLogger("teams_gw.bot")


class TeamsGatewayBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state
        self._last_query_accessor = conversation_state.create_property("last_n2sql_query")
        self._history_accessor = conversation_state.create_property("n2sql_history")

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
        value = turn_context.activity.value or {}
        if isinstance(value, dict):
            action = value.get("action")
            if action == "n2sql_more":
                await self._send_more_rows(turn_context)
                return
            if action == "n2sql_history":
                await self._execute_query(
                    turn_context,
                    (value.get("query") or "").strip(),
                    value.get("dataset"),
                    announce=False,
                )
                return

        text = (turn_context.activity.text or "").strip()

        if self._matches_trigger(text):
            query, ds = self._extract_query_and_dataset(text)
            await self._execute_query(turn_context, query, ds)
            return

        normalized = text.lower()
        if normalized in {"historial", "history"}:
            await self._send_history_buttons(turn_context, include_current=True)
            return

        await turn_context.send_activity(
            "Para N2SQL usa `dt:` o `dt[dataset]:`. Ej.: `dt[odoo]: facturas pendientes de pago (cliente,monto,total)`"
        )

    async def _execute_query(
        self,
        turn_context: TurnContext,
        query: str,
        dataset: str | None,
        announce: bool = True,
    ):
        if not query:
            await turn_context.send_activity("No pude recuperar esa consulta.")
            return

        if announce:
            await turn_context.send_activity("Entendido. Consultando…")

        try:
            payload = await client.ask(query, dataset=dataset)
        except Exception:
            await turn_context.send_activity(
                "No pude resolver la consulta ahora. Inténtalo de nuevo más tarde."
            )
            return

        await self._last_query_accessor.set(
            turn_context,
            {"payload": payload, "query": query, "dataset": dataset, "stage": "initial"},
        )
        md = format_n2sql_payload(payload)
        await turn_context.send_activity(Activity(text=md, text_format="markdown"))
        await self.conversation_state.save_changes(turn_context)

        await self._record_history(turn_context, query, dataset)

        if self._has_more_rows(payload):
            try:
                await self._send_more_button(turn_context)
            except Exception as exc:
                log.warning("No se pudo enviar el botón 'Ver más filas': %s", exc)

        await self._send_history_buttons(turn_context)

    def _has_more_rows(self, payload: dict[str, Any]) -> bool:
        total = self._total_rows(payload)
        return total > settings.N2SQL_MAX_ROWS

    def _total_rows(self, payload: dict[str, Any]) -> int:
        total = payload.get("rowcount")
        if total is None:
            rows = payload.get("rows") or payload.get("data")
            if isinstance(rows, list):
                total = len(rows)
        return int(total or 0)

    async def _send_more_rows(self, turn_context: TurnContext):
        last = await self._last_query_accessor.get(turn_context, None)
        if not last:
            await turn_context.send_activity("No hay ninguna consulta previa para ampliar.")
            return
        payload = last.get("payload")
        if not payload:
            await turn_context.send_activity("No pude recuperar los resultados anteriores.")
            return
        total = self._total_rows(payload)
        if not total:
            await turn_context.send_activity("No tengo más filas para mostrar.")
            return

        stage = last.get("stage", "initial")
        show_more = False
        if stage == "initial":
            target_rows = min(settings.N2SQL_MAX_ROWS_EXPANDED, total)
            next_stage = "expanded"
            show_more = total > target_rows
        elif stage == "expanded":
            target_rows = total
            next_stage = "done"
        else:
            await turn_context.send_activity("Ya estás viendo todas las filas disponibles.")
            return

        md = format_n2sql_payload(payload, max_rows=target_rows)
        await turn_context.send_activity(Activity(text=md, text_format="markdown"))
        last["stage"] = next_stage
        await self._last_query_accessor.set(turn_context, last)
        await self.conversation_state.save_changes(turn_context)

        if show_more:
            await self._send_more_button(turn_context)
        else:
            # Después de mostrar todo, ofrece historial para reutilizar consultas.
            await self._send_history_buttons(turn_context)

    async def _send_more_button(self, turn_context: TurnContext):
        # Enviar tarjeta con botón "Ver más" para que el usuario amplíe resultados.
        card = HeroCard(
            text="Hay más filas disponibles:",
            buttons=[
                CardAction(
                    type=ActionTypes.message_back,
                    title="Ver más filas",
                    text="ver_mas_filas",
                    display_text="Ver más filas",
                    value={"action": "n2sql_more"},
                )
            ],
        )
        attachment = Attachment(
            content_type="application/vnd.microsoft.card.hero",
            content=card.serialize(),
        )
        message = MessageFactory.attachment(attachment)
        await turn_context.send_activity(message)

    async def _record_history(self, turn_context: TurnContext, query: str, dataset: str | None):
        entry = {"query": query, "dataset": dataset}
        history = await self._history_accessor.get(turn_context, [])
        history = [h for h in history if not (h.get("query") == query and h.get("dataset") == dataset)]
        history.insert(0, entry)
        history = history[:HISTORY_LIMIT]
        await self._history_accessor.set(turn_context, history)
        await self.conversation_state.save_changes(turn_context)

    async def _send_history_buttons(self, turn_context: TurnContext, include_current: bool = False):
        history = await self._history_accessor.get(turn_context, [])
        entries = history if include_current else history[1:]
        entries = entries[:max(0, HISTORY_LIMIT - (0 if include_current else 1))]
        if not entries:
            return

        buttons = []
        for entry in entries:
            title = entry.get("query") or ""
            if entry.get("dataset"):
                title = f"[{entry['dataset']}] {title}"
            title = title.strip() or "(consulta sin texto)"
            if len(title) > 40:
                title = f"{title[:37]}…"
            buttons.append(
                CardAction(
                    type=ActionTypes.message_back,
                    title=title,
                    text="consulta_reciente",
                    display_text=title,
                    value={
                        "action": "n2sql_history",
                        "query": entry.get("query"),
                        "dataset": entry.get("dataset"),
                    },
                )
            )

        card = HeroCard(
            text="¿Quieres repetir una consulta reciente?",
            buttons=buttons,
        )
        attachment = Attachment(
            content_type="application/vnd.microsoft.card.hero",
            content=card.serialize(),
        )
        message = MessageFactory.attachment(attachment)
        await turn_context.send_activity(message)
