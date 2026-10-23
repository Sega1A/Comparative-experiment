"""Los guardados reales de cada servidor, contra PostgreSQL."""

import asyncio
import json
from types import SimpleNamespace

import aiocoap
import pytest
from sqlalchemy import select

from common.db import AlertaCoAP, AlertaHTTP, AlertaMQTT, get_session
from common.db.init_db import init_db
from servers.coap.app import AlertResource
from servers.http.app import create_app
from servers.mqtt.subscriber import handle_message

pytestmark = pytest.mark.integration

ALERT = {"device_id": "esp32-01", "sequence": 7, "timestamp": 1760000000000}
BODY = json.dumps(ALERT).encode()


def test_http_server_stores_the_alert_in_alertas_http(db):
    init_db()
    client = create_app().test_client()

    response = client.post("/alert", data=BODY, content_type="application/json")

    assert response.get_json() is True
    with get_session() as session:
        row = session.scalars(select(AlertaHTTP)).one()
        assert row.payload == ALERT
        assert row.tamano_bytes == len(BODY)
        assert row.ip_origen == "127.0.0.1"
        assert row.content_type == "application/json"


def test_coap_server_stores_the_alert_in_alertas_coap(db):
    init_db()
    request = aiocoap.Message(code=aiocoap.POST, payload=BODY)
    request.mtype = aiocoap.NON
    request.mid = 4321

    response = asyncio.run(AlertResource().render_post(request))

    assert response.code == aiocoap.CHANGED
    with get_session() as session:
        row = session.scalars(select(AlertaCoAP)).one()
        assert (row.tipo_mensaje, row.message_id) == ("NON", 4321)
        assert row.tamano_bytes == len(BODY)
        assert row.payload == ALERT


def test_mqtt_subscriber_stores_the_alert_in_alertas_mqtt(db):
    init_db()
    msg = SimpleNamespace(topic="alert", qos=2, payload=BODY)

    assert handle_message(msg) is True

    with get_session() as session:
        row = session.scalars(select(AlertaMQTT)).one()
        assert (row.topic, row.qos) == ("alert", 2)
        assert row.tamano_bytes == len(BODY)
        assert row.payload == ALERT
