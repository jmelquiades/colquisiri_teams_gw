from __future__ import annotations
import os
import httpx
from .settings import settings

class N2SQLClient:
    def __init__(self) -> None:
        self.base = (settings.N2SQL_URL or "").rstrip("/")
        self.path = settings.N2SQL_QUERY_PATH
        self.dataset = settings.N2SQL_DATASET
        self.api_key = settings.N2SQL_API_KEY
        self.max_rows = settings.N2SQL_MAX_ROWS

    async def query(self, question: str) -> dict:
        if not self.base:
            return {"ok": False, "error": "N2SQL_URL not configured."}

        url = f"{self.base}{self.path}"
        payload = {
            "dataset": self.dataset,
            "question": question,
            "limit": self.max_rows,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(url, json=payload, headers=headers)
            ok = 200 <= r.status_code < 300
            return {
                "ok": ok,
                "status": r.status_code,
                "data": (r.json() if ok else {"text": r.text}),
            }

client = N2SQLClient()
