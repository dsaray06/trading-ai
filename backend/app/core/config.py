"""Application settings.

All configuration is sourced from environment variables (loaded from `.env`
locally) via pydantic-settings. This is the single place the app reads config;
never use `os.getenv` elsewhere. See `.env.example` for the full surface.
"""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_db_url(url: str) -> str:
    """Ensure the psycopg driver is used (Render/Heroku hand out bare URLs)."""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-prod"

    # ---- Database ----
    database_url: str = (
        "postgresql+psycopg://tradingai:tradingai@localhost:5432/tradingai"
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def _fix_db_driver(cls, v: str) -> str:
        return _normalize_db_url(v)

    # ---- Auth (JWT) ----
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ---- AI layer ----
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # ---- Market data ----
    polygon_api_key: str = ""
    finnhub_api_key: str = ""
    sec_edgar_user_agent: str = "trading-ai dev@example.com"

    # ---- Execution: Alpaca paper trading ----
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # ---- CORS / frontend ----
    # Comma-separated list of allowed origins (a bare host gets https:// prepended).
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        out: list[str] = []
        for raw in self.cors_origins.split(","):
            origin = raw.strip()
            if not origin:
                continue
            out.append(origin if origin.startswith("http") else f"https://{origin}")
        return out


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Call this everywhere instead of constructing Settings()."""
    return Settings()
