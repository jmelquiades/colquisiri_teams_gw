from future import annotations
from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
# Bot
MICROSOFT_APP_ID: str
MICROSOFT_APP_PASSWORD: str
MICROSOFT_APP_TENANT_ID: str | None = None

# N2SQL
N2SQL_URL: str
N2SQL_QUERY_PATH: str = "/v1/query"
N2SQL_API_KEY: str | None = None
N2SQL_TIMEOUT_S: int = 30
N2SQL_DATASET: str = "odoo"

# App
APP_TZ: str = "America/Lima"
N2SQL_TRIGGERS: str = "dt:,consulta ,n2sql:"
N2SQL_MAX_ROWS: int = 20
PORT: int = int(os.getenv("PORT", "8000"))
ENV: str = os.getenv("ENV", "prod")

class Config:
    env_file = ".env"

@property
def triggers(self) -> List[str]:
    return [t.strip() for t in self.N2SQL_TRIGGERS.split(",") if t.strip()]


settings = Settings()
