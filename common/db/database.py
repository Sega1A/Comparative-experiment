"""Conexión a PostgreSQL: lectura de DATABASE_URL, engine y sesiones.

La URL se toma de la variable de entorno DATABASE_URL. Si no está definida,
se busca en el archivo .env de la raíz del repositorio (ver .env.example).
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

RAIZ_REPO = Path(__file__).resolve().parents[2]
ARCHIVO_ENV = RAIZ_REPO / ".env"


def _leer_env(ruta: Path) -> dict:
    """Lee un archivo .env simple (CLAVE=valor, se ignoran comentarios)."""
    valores = {}
    if not ruta.is_file():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


# Parámetros que usa Prisma (Node) en la URL y que psycopg no entiende.
_PARAMS_SOLO_PRISMA = {"pgbouncer", "schema", "connection_limit", "pool_timeout"}


def _normalizar_url(url: str) -> str:
    """Acepta la URL en el formato de Prisma/Supabase y la adapta a psycopg v3.

    - postgresql:// o postgres://  ->  postgresql+psycopg://
    - quita parámetros que solo existen en Prisma (?pgbouncer=true, ?schema=public)
    """
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            url = "postgresql+psycopg://" + url[len(prefijo) :]
            break
    partes = urlsplit(url)
    if partes.query:
        params = [
            (k, v)
            for k, v in parse_qsl(partes.query, keep_blank_values=True)
            if k.lower() not in _PARAMS_SOLO_PRISMA
        ]
        url = urlunsplit(partes._replace(query=urlencode(params)))
    return url


def get_database_url() -> str:
    """Devuelve DATABASE_URL (entorno primero, luego .env)."""
    url: str | None = os.environ.get("DATABASE_URL") or _leer_env(ARCHIVO_ENV).get(
        "DATABASE_URL"
    )
    if not url:
        raise RuntimeError(
            "No se encontró DATABASE_URL. Copie .env.example a .env "
            "o defina la variable de entorno."
        )
    return _normalizar_url(url)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Engine único por proceso (se crea la primera vez que se pide)."""
    return create_engine(get_database_url(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def _fabrica_sesiones() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    """Entrega una sesión; hace commit al salir o rollback si hay error.

    Uso:
        with get_session() as sesion:
            sesion.add(AlertaHTTP(...))
    """
    sesion = _fabrica_sesiones()()
    try:
        yield sesion
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise
    finally:
        sesion.close()
