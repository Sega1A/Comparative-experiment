from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import inspect, select

from common.db import AlertaCoAP, AlertaHTTP, AlertaMQTT, get_session, store_alert
from common.db.init_db import init_db, prueba_insertar_y_leer
from common.schemas import parse_alert

pytestmark = pytest.mark.integration

TABLES = {"alertas_http", "alertas_mqtt", "alertas_coap"}
ALERT = parse_alert(
    '{"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000,'
    ' "event_type": "fall"}'
)


def test_init_db_creates_the_tables(db):
    assert set(init_db()) == TABLES
    assert TABLES <= set(inspect(db).get_table_names())


def test_init_db_is_safe_when_called_at_the_same_time(db):
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: init_db(), range(6)))
    assert all(set(tables) == TABLES for tables in results)


def test_init_db_check_inserts_reads_and_cleans(db):
    init_db()
    prueba_insertar_y_leer()
    with get_session() as session:
        assert session.scalars(select(AlertaHTTP)).all() == []


@pytest.mark.parametrize(
    ("model", "metadata"),
    [
        (AlertaHTTP, {"ip_origen": "10.0.0.5", "content_type": "application/json"}),
        (AlertaMQTT, {"topic": "alertas/caidas", "qos": 2}),
        (AlertaCoAP, {"tipo_mensaje": "CON", "message_id": 4321}),
    ],
)
def test_store_alert_saves_common_and_protocol_columns(db, model, metadata):
    init_db()
    store_alert(model, ALERT, 75, **metadata)

    with get_session() as session:
        row = session.scalars(select(model)).one()
        assert row.payload == ALERT.to_payload()
        assert row.tamano_bytes == 75
        assert row.enviado_en == ALERT.sent_at
        assert row.recibido_en is not None
        assert row.perfil_red is None
        for name, value in metadata.items():
            assert getattr(row, name) == value


def test_store_alert_records_network_profile(db, monkeypatch):
    init_db()
    monkeypatch.setenv("NETWORK_PROFILE", "perdida_10")
    from common.schemas import get_settings

    get_settings.cache_clear()
    store_alert(AlertaCoAP, ALERT, 75, tipo_mensaje="NON", message_id=1)

    with get_session() as session:
        assert session.scalars(select(AlertaCoAP)).one().perfil_red == "perdida_10"


def test_database_constraints_reject_invalid_metadata(db):
    init_db()
    with pytest.raises(Exception, match="ck_alertas_mqtt_qos"):
        store_alert(AlertaMQTT, ALERT, 75, topic="t", qos=3)
