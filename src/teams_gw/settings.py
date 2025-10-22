from typing import Optional
from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Lee credenciales desde variables de entorno o .env.
    Acepta alias comunes para evitar “no lo encuentra” si el host no usa el nombre exacto.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # Acepta MICROSOFT_APP_ID / MicrosoftAppId / MICROSOFTAPPID
    MICROSOFT_APP_ID: str = Field(
        ...,
        validation_alias=AliasChoices(
            "MICROSOFT_APP_ID",
            "MicrosoftAppId",
            "MICROSOFTAPPID",
        ),
    )

    # Acepta MICROSOFT_APP_PASSWORD / MicrosoftAppPassword / MICROSOFTAPPPASSWORD
    MICROSOFT_APP_PASSWORD: str = Field(
        ...,
        validation_alias=AliasChoices(
            "MICROSOFT_APP_PASSWORD",
            "MicrosoftAppPassword",
            "MICROSOFTAPPPASSWORD",
        ),
    )

    # Opcionales (gov/sovereign o pruebas)
    BOT_OPENID_METADATA: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("BOT_OPENID_METADATA", "BotOpenIdMetadata"),
    )
    CHANNEL_SERVICE: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("CHANNEL_SERVICE", "ChannelService"),
    )

    # Otros settings de tu app (ejemplo)
    APP_TZ: Optional[str] = Field(default="UTC")

    @field_validator("MICROSOFT_APP_ID", "MICROSOFT_APP_PASSWORD", mode="before")
    @classmethod
    def _strip_spaces(cls, v):
        # Recorta espacios si por error se pegaron con espacios al inicio/fin
        if isinstance(v, str):
            return v.strip()
        return v


settings = Settings()
