from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"

# Parámetros que usa Prisma (Node) en la URL y que psycopg no entiende.
PRISMA_ONLY_PARAMS = {"pgbouncer", "schema", "connection_limit", "pool_timeout"}


def normalize_database_url(url: str) -> str:
    """Acepta la URL en el formato de Prisma/Supabase y la adapta a psycopg v3.

    - postgresql:// o postgres://  ->  postgresql+psycopg://
    - quita parámetros que solo existen en Prisma (?pgbouncer=true, ?schema=public)
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix) :]
            break
    parts = urlsplit(url)
    if parts.query:
        params = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in PRISMA_ONLY_PARAMS
        ]
        url = urlunsplit(parts._replace(query=urlencode(params)))
    return url


class Settings(BaseSettings):
    """Configuración del proyecto: variables de entorno primero, luego `.env`."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "alert"
    network_profile: str | None = None
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("network_profile", mode="before")
    @classmethod
    def _empty_profile_is_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
