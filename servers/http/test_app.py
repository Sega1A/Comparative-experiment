import pytest

from app import create_app

VALID_ALERT = {"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_valid_alert_returns_true(client):
    response = client.post("/http/alert", json=VALID_ALERT)
    assert response.status_code == 200
    assert response.get_json() is True


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
    response = client.post("/http/alert", data="{not json", content_type="application/json")
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
