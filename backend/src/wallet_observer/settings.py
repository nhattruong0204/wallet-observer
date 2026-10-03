"""One server-side configuration contract; values never appear in diagnostics."""

from typing import Literal
from urllib.parse import urlsplit

from psycopg.conninfo import conninfo_to_dict
from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """Contains only field names and static corrective messages."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )
    database_url: SecretStr
    app_mode: Literal["fixture", "live"] = "fixture"
    database_timeout_seconds: float = Field(default=3, ge=0.1, le=10)
    worker_poll_seconds: float = Field(default=5, ge=0.1, le=60)
    helius_enabled: bool = False
    telegram_enabled: bool = False
    helius_api_key: SecretStr = SecretStr("")
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: SecretStr = SecretStr("")

    @field_validator("database_url")
    @classmethod
    def database_uri(cls, value):
        try:
            uri = value.get_secret_value().replace("postgresql+psycopg://", "postgresql://", 1)
            parsed = urlsplit(uri)
            if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
                raise ValueError
            details = conninfo_to_dict(uri)
            if not details.get("dbname") or not details.get("user"):
                raise ValueError
        except Exception:
            raise ValueError("requires a PostgreSQL URL with host, user and database") from None
        return value

    @model_validator(mode="after")
    def enabled_capabilities(self):
        if self.app_mode == "fixture" and (self.helius_enabled or self.telegram_enabled):
            raise ValueError(
                "fixture mode requires HELIUS_ENABLED=false and TELEGRAM_ENABLED=false"
            )
        if self.helius_enabled:
            if not self.helius_api_key.get_secret_value().strip():
                raise ValueError("HELIUS_ENABLED requires HELIUS_API_KEY")
            raise ValueError(
                "HELIUS_ENABLED is unavailable until collector issue #6 is implemented"
            )
        if self.telegram_enabled:
            if not all(
                s.get_secret_value().strip()
                for s in (self.telegram_bot_token, self.telegram_chat_id)
            ):
                raise ValueError(
                    "TELEGRAM_ENABLED requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
                )
            raise ValueError(
                "TELEGRAM_ENABLED is unavailable until delivery issue #14 is implemented"
            )
        return self

    def database_dsn(self):
        return self.database_url.get_secret_value().replace(
            "postgresql+psycopg://",
            "postgresql://",
            1,
        )


def load_settings(**overrides):
    try:
        return Settings(**overrides)
    except ValidationError as error:
        messages = []
        for detail in error.errors(include_input=False, include_context=False, include_url=False):
            field = str(detail["loc"][0]).upper() if detail["loc"] else "SETTINGS"
            # Pydantic input/context/exception rendering is intentionally excluded.
            messages.append(f"{field}: {detail['msg']}")
        raise ConfigurationError("; ".join(messages)) from None
