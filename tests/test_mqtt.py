import json
from types import SimpleNamespace

import pytest

from servers.mqtt import subscriber

ALERT = {"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}

saved = []


def fake_save(alert, msg):
    saved.append((alert, msg.topic, msg.qos, len(msg.payload)))


def message(payload, topic="alert", qos=1):
    if not isinstance(payload, bytes):
        payload = json.dumps(payload).encode()
    return SimpleNamespace(topic=topic, qos=qos, payload=payload)


@pytest.fixture(autouse=True)
def clear_saved():
    saved.clear()


def test_valid_alert_is_saved_with_topic_qos_and_size():
    msg = message(ALERT, qos=2)

    assert subscriber.handle_message(msg, fake_save) is True

    alert, topic, qos, size = saved[0]
    assert alert.device_id == "esp32-01"
    assert (topic, qos, size) == ("alert", 2, len(msg.payload))


def test_optional_fields_are_accepted():
    body = {**ALERT, "event_type": "fall", "battery_level": 80}
    assert subscriber.handle_message(message(body), fake_save) is True
    assert saved[0][0].to_payload() == body


@pytest.mark.parametrize(
    "payload",
    [
        {"device_id": "esp32-01"},
        {**ALERT, "extra": 1},
        {**ALERT, "timestamp": 1760000000.123},
        {**ALERT, "sequence": "1"},
        [ALERT],
        b"{not json",
        b"\xff\xfe",
        b"",
    ],
)
def test_invalid_alert_is_rejected_and_not_saved(payload):
    assert subscriber.handle_message(message(payload), fake_save) is False
    assert saved == []


def test_save_failure_is_reported_without_raising():
    def failing_save(alert, msg):
        raise RuntimeError("db down")

    assert subscriber.handle_message(message(ALERT), failing_save) is False


def test_subscriber_keeps_working_after_bad_message():
    subscriber.handle_message(message(b"{not json"), fake_save)
    assert subscriber.handle_message(message(ALERT), fake_save) is True


class FakeClient:
    def __init__(self):
        self.subscriptions = []

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))


def test_on_connect_subscribes_with_qos_2_to_the_configured_topic():
    client = FakeClient()
    settings = SimpleNamespace(mqtt_topic="alert")

    subscriber.on_connect(client, settings, {}, SimpleNamespace(is_failure=False))

    assert client.subscriptions == [("alert", 2)]


def test_on_connect_does_not_subscribe_when_connection_fails():
    client = FakeClient()
    settings = SimpleNamespace(mqtt_topic="alert")

    subscriber.on_connect(client, settings, {}, SimpleNamespace(is_failure=True))

    assert client.subscriptions == []
