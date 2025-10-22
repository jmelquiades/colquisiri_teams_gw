from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    SERVICE_NAME: str = "teams_gw"

    # Credenciales de Azure AD para el Bot Framework Connector
    MICROSOFT_APP_ID: str = Field(..., description="Azure AD App (client) ID")
    MICROSOFT_APP_PASSWORD: str = Field(..., description="Client secret")
    # Mantener opcional: no lo usamos en el adapter para evitar 401 con el Connector
    MICROSOFT_APP_TENANT_ID: str | None = None

    # N2SQL (opcionales)
    N2SQL_URL: str | None = None
    N2SQL_QUERY_PATH: str = "/v1/query"
    N2SQL_DATASET: str | None = None
    N2SQL_API_KEY: str | None = None
    N2SQL_MAX_ROWS: int = 20
    N2SQL_TRIGGERS: str = "dt:,consulta ,n2sql:"

    APP_TZ: str = "UTC"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
