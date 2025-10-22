from __future__ import annotations
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

def _first_env(*names: str) -> str | None:
    for n in names:
        v = os.getenv(n)
        if v and v.strip():
            return v.strip()
    return None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "teams_gw"

    # Acepta múltiples alias sin que tengas que renombrar nada en Render
    MICROSOFT_APP_ID: str | None = Field(default=None)
    MICROSOFT_APP_PASSWORD: str | None = Field(default=None)
    MICROSOFT_APP_TENANT_ID: str | None = Field(default=None)

    # N2SQL (opcionales)
    N2SQL_URL: str | None = None
    N2SQL_QUERY_PATH: str = "/v1/query"
    N2SQL_DATASET: str | None = None
    N2SQL_API_KEY: str | None = None
    N2SQL_MAX_ROWS: int = 20
    N2SQL_TRIGGERS: str = "dt:,consulta ,n2sql:"

    APP_TZ: str = "UTC"

    @model_validator(mode="after")
    def _fill_ms_aliases(self):
        # ID
        if not self.MICROSOFT_APP_ID:
            self.MICROSOFT_APP_ID = _first_env(
                "MICROSOFT_APP_ID",
                "MicrosoftAppId",
                "BOT_ID",
                "APP_ID",
            )
        # SECRET
        if not self.MICROSOFT_APP_PASSWORD:
            self.MICROSOFT_APP_PASSWORD = _first_env(
                "MICROSOFT_APP_PASSWORD",
                "MicrosoftAppPassword",
                "BOT_PASSWORD",
                "APP_PASSWORD",
            )
        # TENANT (opcional)
        if not self.MICROSOFT_APP_TENANT_ID:
            self.MICROSOFT_APP_TENANT_ID = _first_env(
                "MICROSOFT_APP_TENANT_ID",
                "MicrosoftAppTenantId",
                "TENANT_ID",
            )
        # Validación final clara
        missing = []
        if not self.MICROSOFT_APP_ID:
            missing.append("MICROSOFT_APP_ID / MicrosoftAppId")
        if not self.MICROSOFT_APP_PASSWORD:
            missing.append("MICROSOFT_APP_PASSWORD / MicrosoftAppPassword")
        if missing:
            raise ValueError(
                "Faltan credenciales: " + ", ".join(missing) +
                ". Las leemos con múltiples alias para no requerir cambios en Render."
            )
        return self

settings = Settings()
