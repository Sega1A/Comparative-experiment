"""Conexión a PostgreSQL: engine y sesiones.

La URL sale de `common.schemas.Settings` (variable de entorno DATABASE_URL o,
si no existe, el archivo .env de la raíz del repositorio; ver .env.example).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from pydantic import ValidationError
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.schemas import get_settings


def get_database_url() -> str:
    """Devuelve DATABASE_URL ya adaptada a psycopg v3."""
    try:
        return get_settings().database_url
    except ValidationError as error:
        raise RuntimeError(
            "No se encontró DATABASE_URL. Copie .env.example a .env "
            "o defina la variable de entorno."
        ) from error


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
