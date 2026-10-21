import pytest

from common.alert import AlertDTO, InvalidAlertError

REQUIRED = {"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}


def test_required_fields_only():
    alert = AlertDTO.from_payload(REQUIRED)
    assert alert.event_type is None
    assert alert.to_payload() == REQUIRED


def test_optional_fields_are_accepted():
    payload = {**REQUIRED, "event_type": "fall", "battery_level": 80, "acceleration": 2}
    assert AlertDTO.from_payload(payload).to_payload() == payload


@pytest.mark.parametrize(
    "payload",
    [
        {"device_id": "esp32-01", "sequence": 1},
        {**REQUIRED, "extra": "value"},
        {**REQUIRED, "sequence": "1"},
        {**REQUIRED, "sequence": True},
        {**REQUIRED, "device_id": 42},
        {**REQUIRED, "battery_level": "80"},
        {**REQUIRED, "acceleration": True},
        [REQUIRED],
        None,
    ],
)
def test_invalid_payload_is_rejected(payload):
    with pytest.raises(InvalidAlertError):
        AlertDTO.from_payload(payload)
