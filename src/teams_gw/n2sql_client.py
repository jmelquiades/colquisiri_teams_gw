from __future__ import annotations
from typing import Any, Dict, Optional
import httpx
from .settings import settings

class N2SQLClient:
    def __init__(self) -> None:
        self.base = settings.N2SQL_URL.rstrip("/")
        self.path = settings.N2SQL_QUERY_PATH
        self.headers = {"Content-Type": "application/json"}
        if settings.N2SQL_API_KEY:
            self.headers["Authorization"] = f"Bearer {settings.N2SQL_API_KEY}"
        self.timeout = settings.N2SQL_TIMEOUT_S

    def build_payload(self, question: str, dataset: Optional[str] = None) -> Dict[str, Any]:
        # Contrato de colquisiri_n2sql_service: dataset/intent/params
        return {
            "dataset": dataset or getattr(settings, "N2SQL_DATASET", "odoo"),
            "intent": question,
            "params": {},
        }

    async def ask(self, question: str, dataset: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base}{self.path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=self.build_payload(question, dataset), headers=self.headers)
            resp.raise_for_status()
            return resp.json()

client = N2SQLClient()
