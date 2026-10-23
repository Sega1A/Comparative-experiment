import json
from datetime import UTC, datetime

import pytest

from common.schemas import AlertDTO, InvalidAlertError, parse_alert

REQUIRED = {"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}


def parse(payload):
    return parse_alert(json.dumps(payload))


def test_required_fields_only():
    alert = parse(REQUIRED)
    assert alert.event_type is None
    assert alert.to_payload() == REQUIRED


def test_optional_fields_are_accepted():
    payload = {**REQUIRED, "event_type": "fall", "battery_level": 80, "acceleration": 2}
    assert parse(payload).to_payload() == payload


def test_optional_field_sent_as_null_is_omitted():
    assert parse({**REQUIRED, "event_type": None}).to_payload() == REQUIRED


def test_accepts_bytes_and_str():
    raw = json.dumps(REQUIRED)
    assert parse_alert(raw) == parse_alert(raw.encode())


def test_alert_is_immutable():
    with pytest.raises(Exception, match="frozen"):
        parse(REQUIRED).sequence = 2


def test_sent_at_converts_milliseconds_to_utc():
    alert = parse(REQUIRED)
    assert alert.sent_at == datetime.fromtimestamp(1760000000, tz=UTC)
    assert alert.sent_at.tzinfo is UTC


@pytest.mark.parametrize(
    "payload",
    [
        {"device_id": "esp32-01", "sequence": 1},
        {**REQUIRED, "extra": "value"},
        {**REQUIRED, "sequence": "1"},
        {**REQUIRED, "sequence": True},
        {**REQUIRED, "sequence": 1.5},
        {**REQUIRED, "device_id": 42},
        {**REQUIRED, "battery_level": "80"},
        {**REQUIRED, "acceleration": True},
        {**REQUIRED, "timestamp": 1760000000.5},
        {**REQUIRED, "timestamp": 10**30},
        [REQUIRED],
        "alert",
        None,
    ],
)
def test_invalid_payload_is_rejected(payload):
    with pytest.raises(InvalidAlertError):
        parse(payload)


@pytest.mark.parametrize("raw", [b"{not json", b"\xff\xfe", b"", "  "])
def test_malformed_body_is_rejected(raw):
    with pytest.raises(InvalidAlertError):
        parse_alert(raw)


def test_error_message_names_the_field():
    with pytest.raises(InvalidAlertError, match="sequence"):
        parse({**REQUIRED, "sequence": "1"})


def test_json_schema_documents_the_message():
    schema = AlertDTO.model_json_schema()
    assert schema["required"] == ["device_id", "sequence", "timestamp"]
    assert schema["additionalProperties"] is False
