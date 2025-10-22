from __future__ import annotations

import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Credenciales del Bot Channel Registration (no son de Graph)
    MICROSOFT_APP_ID: str = Field(..., description="Azure Bot App ID")
    MICROSOFT_APP_PASSWORD: str = Field(..., description="Azure Bot Client Secret")
    # Opcional: si lo dejas vacío, queda multitenant (organizations)
    MICROSOFT_APP_TENANT_ID: str | None = Field(default=None)

    # Extras de tu servicio (opcional)
    N2SQL_URL: str | None = None
    N2SQL_QUERY_PATH: str = "/v1/query"
    N2SQL_DATASET: str | None = None
    APP_TZ: str = "America/Lima"

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def authority(self) -> str:
        # Multitenant por defecto
        tenant = self.MICROSOFT_APP_TENANT_ID or "organizations"
        return f"https://login.microsoftonline.com/{tenant}"


settings = Settings()

# Config de logging sencilla y consistente
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)
