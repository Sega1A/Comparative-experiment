import pytest

from servers.http.app import create_app

VALID_ALERT = {"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}

saved = []


def fake_save(alert, request):
    saved.append(
        (alert, len(request.get_data()), request.remote_addr, request.content_type)
    )


@pytest.fixture
def client():
    saved.clear()
    app = create_app(fake_save)
    app.config["TESTING"] = True
    return app.test_client()


def test_valid_alert_returns_true(client):
    response = client.post("/http/alert", json=VALID_ALERT)
    assert response.status_code == 200
    assert response.get_json() is True


def test_optional_fields_are_accepted_like_in_the_other_protocols(client):
    body = {**VALID_ALERT, "event_type": "fall", "battery_level": 80}
    response = client.post("/http/alert", json=body)
    assert response.status_code == 200
    assert saved[0][0].to_payload() == body


@pytest.mark.parametrize(
    "body",
    [
        {"device_id": "esp32-01", "sequence": 1},
        {**VALID_ALERT, "extra": "value"},
        {**VALID_ALERT, "sequence": "1"},
        {**VALID_ALERT, "sequence": True},
        {**VALID_ALERT, "device_id": 42},
        [VALID_ALERT],
        "alert",
        None,
    ],
)
def test_unexpected_values_return_400(client, body):
    response = client.post("/http/alert", json=body)
    assert response.status_code == 400
    assert response.get_json() is False


def test_malformed_json_returns_400(client):
    response = client.post(
        "/http/alert", data="{not json", content_type="application/json"
    )
    assert response.status_code == 400
    assert response.get_json() is False


def test_non_json_body_returns_400(client):
    response = client.post("/http/alert", data="plain text", content_type="text/plain")
    assert response.status_code == 400
    assert response.get_json() is False


def test_server_keeps_working_after_bad_request(client):
    client.post("/http/alert", data="{not json", content_type="application/json")
    response = client.post("/http/alert", json=VALID_ALERT)
    assert response.status_code == 200
    assert response.get_json() is True


def test_valid_alert_is_saved_with_size_origin_and_content_type(client):
    body = b'{"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}'
    client.post("/http/alert", data=body, content_type="application/json")

    assert len(saved) == 1
    alert, size, remote_addr, content_type = saved[0]
    assert alert.device_id == "esp32-01"
    assert size == len(body)
    assert remote_addr == "127.0.0.1"
    assert content_type == "application/json"


def test_rejected_alert_is_not_saved(client):
    client.post("/http/alert", json={"device_id": "esp32-01"})
    assert saved == []


def test_save_failure_returns_500():
    def failing_save(alert, request):
        raise RuntimeError("db down")

    response = (
        create_app(failing_save).test_client().post("/http/alert", json=VALID_ALERT)
    )
    assert response.status_code == 500
    assert response.get_json() is False
