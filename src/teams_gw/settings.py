from __future__ import annotations
import os
from typing import List, Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Lee .env si existe y no distingue mayúsc/minúsculas
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # === Microsoft Bot Framework (acepta UPPER y camelCase) ===
    MICROSOFT_APP_ID: str = Field(
        validation_alias=AliasChoices("MICROSOFT_APP_ID", "MicrosoftAppId")
    )
    MICROSOFT_APP_PASSWORD: str = Field(
        validation_alias=AliasChoices("MICROSOFT_APP_PASSWORD", "MicrosoftAppPassword")
    )
    MICROSOFT_APP_TENANT_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MICROSOFT_APP_TENANT_ID", "MicrosoftAppTenantId"),
    )

    # === N2SQL ===
    N2SQL_URL: str
    N2SQL_QUERY_PATH: str = "/v1/query"
    N2SQL_API_KEY: Optional[str] = None
    N2SQL_TIMEOUT_S: int = 30

    # === App ===
    APP_TZ: str = "America/Lima"
    N2SQL_TRIGGERS: str = "dt:,consulta ,n2sql:"
    N2SQL_MAX_ROWS: int = 20
    PORT: int = int(os.getenv("PORT", "8000"))
    ENV: str = os.getenv("ENV", "prod")

    @property
    def triggers(self) -> List[str]:
        return [t.strip() for t in self.N2SQL_TRIGGERS.split(",") if t.strip()]

settings = Settings()
