from __future__ import annotations

import logging
import os
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices


APP_ID_ALIASES: List[str] = [
    "MICROSOFT_APP_ID",
    "MicrosoftAppId",
    "BOT_ID",
    "APP_ID",
]

APP_SECRET_ALIASES: List[str] = [
    "MICROSOFT_APP_PASSWORD",
    "MicrosoftAppPassword",
    "MICROSOFT_APP_SECRET",
    "BOT_PASSWORD",
    "APP_PASSWORD",
    "CLIENT_SECRET",
]


def _first_present(names: List[str]) -> Optional[str]:
    for n in names:
        v = os.getenv(n)
        if v:
            return n
    return None


class Settings(BaseSettings):
    # Credenciales del Bot Channel (con alias tolerantes)
    MICROSOFT_APP_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(*APP_ID_ALIASES),
        description="Azure Bot App ID",
    )
    MICROSOFT_APP_PASSWORD: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(*APP_SECRET_ALIASES),
        description="Azure Bot Client Secret",
    )
    MICROSOFT_APP_TENANT_ID: Optional[str] = Field(default=None)

    # Extras de tu servicio
    N2SQL_URL: Optional[str] = None
    N2SQL_QUERY_PATH: str = "/v1/query"
    N2SQL_DATASET: Optional[str] = None
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
        tenant = self.MICROSOFT_APP_TENANT_ID or "organizations"
        return f"https://login.microsoftonline.com/{tenant}"

    # Utilidades de depuración
    @property
    def app_id_alias_used(self) -> Optional[str]:
        return _first_present(APP_ID_ALIASES)

    @property
    def app_secret_alias_used(self) -> Optional[str]:
        return _first_present(APP_SECRET_ALIASES)

    @property
    def has_bot_credentials(self) -> bool:
        return bool(self.MICROSOFT_APP_ID and self.MICROSOFT_APP_PASSWORD)


settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)
