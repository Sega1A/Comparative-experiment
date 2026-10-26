"""Pruebas contra un PostgreSQL real.

Se activan con TEST_DATABASE_URL (una base desechable: se borran las tablas):

    TEST_DATABASE_URL=postgresql://postgres:clave@localhost:5499/alertas pytest -m integration
"""

import os

import pytest
from sqlalchemy import text

from common.db import Base, database, get_engine
from common.schemas import get_settings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="define TEST_DATABASE_URL para estas pruebas")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


def _clear_caches():
    get_settings.cache_clear()
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    database._fabrica_sesiones.cache_clear()


@pytest.fixture
def db(monkeypatch):
    """Base vacía y sin tablas; las funciones de common/db apuntan a ella."""
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.delenv("NETWORK_PROFILE", raising=False)
    _clear_caches()
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS alertas_http, alertas_mqtt, alertas_coap")
        )
    yield engine
    Base.metadata.drop_all(engine)
    _clear_caches()
