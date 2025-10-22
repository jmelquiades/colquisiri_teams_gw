from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Credenciales Bot Framework (no cambiamos nombres)
    MICROSOFT_APP_ID: str
    MICROSOFT_APP_PASSWORD: str
    # Opcional: si no lo pones, queda multitenant
    MICROSOFT_APP_TENANT_ID: str | None = None

    # Otros (los dejo opcionales para no romper tu carga)
    N2SQL_URL: str | None = None
    N2SQL_QUERY_PATH: str | None = None
    N2SQL_DATASET: str | None = None

    APP_TZ: str = "America/Lima"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
