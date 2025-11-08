from __future__ import annotations

import logging
from typing import Any

from botbuilder.core import ActivityHandler, ConversationState, MessageFactory, TurnContext
from botbuilder.schema import ActionTypes, Activity, Attachment, CardAction, HeroCard, InvokeResponse
from .settings import settings
from .n2sql_client import client
from .formatters import format_n2sql_payload

TRIGGER_BASES = [p.lower().rstrip(":").strip() for p in settings.triggers]
FAQ_GROUPS = [
    {
        "title": "Facturación",
        "items": [
            {
                "title": "Facturas pendientes",
                "desc": "Lista facturas pendientes de pago.",
                "query": "facturas pendientes de pago (cliente,fecha,monto,total)",
            },
            {
                "title": "Total de facturas pendientes",
                "desc": "Total adeudado por facturas pendientes.",
                "query": "total de facturas pendientes de pago",
            },
        ],
    },
    {
        "title": "Clientes",
        "items": [
            {
                "title": "Datos de clientes",
                "desc": "Información básica de clientes.",
                "query": "datos de clientes (cliente,correo,telefono)",
            }
        ],
    },
]

log = logging.getLogger("teams_gw.bot")


class TeamsGatewayBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state
        self._last_query_accessor = conversation_state.create_property("last_n2sql_query")

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

    async def _handle_card_action(self, turn_context: TurnContext) -> bool:
        value = turn_context.activity.value or {}
        if not isinstance(value, dict):
            return False

        action = value.get("action")
        if action == "n2sql_more":
            await self._send_more_rows(turn_context)
            return True
        if action == "n2sql_faq":
            query = (value.get("query") or "").strip()
            if query:
                await self._run_query(turn_context, query, None, announce=False)
            else:
                await turn_context.send_activity("No pude recuperar esa consulta rápida.")
            return True
        return False

    async def on_invoke_activity(self, turn_context: TurnContext):
        if await self._handle_card_action(turn_context):
            return InvokeResponse(status=200)
        return await super().on_invoke_activity(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        if await self._handle_card_action(turn_context):
            return

        text = (turn_context.activity.text or "").strip()

        if self._matches_trigger(text):
            query, ds = self._extract_query_and_dataset(text)
            await self._run_query(turn_context, query, ds)
            return

        normalized = text.lower()
        if normalized in {"faq", "preguntas frecuentes", "ayuda"}:
            await self._send_faq_card(turn_context)
            return

        await turn_context.send_activity(
            "Para N2SQL usa `dt:` o `dt[dataset]:`. Ej.: `dt[odoo]: facturas pendientes de pago (cliente,monto,total)`"
        )
        await self._send_faq_card(turn_context)

    async def _run_query(
        self,
        turn_context: TurnContext,
        query: str,
        dataset: str | None,
        announce: bool = True,
    ):
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

        if self._has_more_rows(payload):
            try:
                await self._send_more_button(turn_context)
            except Exception as exc:
                log.warning("No se pudo enviar el botón 'Ver más filas': %s", exc)

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

    async def _send_faq_card(self, turn_context: TurnContext):
            if not FAQ_GROUPS:
                return

            body: list[dict[str, Any]] = [
                {
                    "type": "TextBlock",
                    "text": "Preguntas frecuentes",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                {
                    "type": "TextBlock",
                    "text": "Selecciona una consulta rápida:",
                    "isSubtle": True,
                    "wrap": True,
                    "spacing": "Small",
                },
            ]

            for idx, group in enumerate(FAQ_GROUPS):
                section_id = f"faq_section_{idx}"

                # Encabezado estilo botón azul para cada grupo
                body.append(
                    {
                        "type": "ActionSet",
                        "spacing": "Medium",
                        "actions": [
                            {
                                "type": "Action.ToggleVisibility",
                                "title": group["title"],
                                "style": "positive",
                                "targetElements": [section_id],
                            }
                        ],
                    }
                )

                group_items = []
                for item in group["items"]:
                    group_items.append(
                        {
                            "type": "Container",
                            "separator": True,
                            "spacing": "Medium",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"**{item['title']}**",
                                    "wrap": True,
                                },
                                {
                                    "type": "TextBlock",
                                    "text": item.get("desc", ""),
                                    "isSubtle": True,
                                    "spacing": "None",
                                    "wrap": True,
                                },
                                {
                                    "type": "ActionSet",
                                    "spacing": "Small",
                                    "actions": [
                                        {
                                            "type": "Action.Submit",
                                            "title": "Ejecutar",
                                            "data": {
                                                "action": "n2sql_faq",
                                                "query": item.get("query"),
                                            },
                                        }
                                    ],
                                },
                            ],
                        }
                    )

                body.append(
                    {
                        "type": "Container",
                        "id": section_id,
                        "isVisible": False,
                        "style": "emphasis",
                        "bleed": True,
                        "spacing": "Small",
                        "items": group_items,
                    }
                )

            card = {
                "type": "AdaptiveCard",
                "version": "1.5",
                "body": body,
            }
            attachment = Attachment(
                content_type="application/vnd.microsoft.card.adaptive",
                content=card,
            )
            await turn_context.send_activity(MessageFactory.attachment(attachment))
