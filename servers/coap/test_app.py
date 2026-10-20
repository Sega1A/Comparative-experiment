import json

import aiocoap
import pytest
import pytest_asyncio
from aiocoap import Code, Message, Reliable, Unreliable

from app import create_site

VALID_ALERT = {"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}
PORT = 56830

saved = []


def fake_save(alert, request):
    saved.append((alert, request.mtype, request.mid))


@pytest_asyncio.fixture
async def client():
    saved.clear()
    server = await aiocoap.Context.create_server_context(create_site(fake_save), bind=("127.0.0.1", PORT))
    client = await aiocoap.Context.create_client_context()
    yield client
    await client.shutdown()
    await server.shutdown()


async def post(client, payload, tuning=Reliable, path="alert"):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    request = Message(code=Code.POST, transport_tuning=tuning, payload=body, uri=f"coap://127.0.0.1:{PORT}/{path}")
    return await client.request(request).response


@pytest.mark.asyncio
async def test_valid_alert_returns_true(client):
    response = await post(client, VALID_ALERT)
    assert response.code == Code.CHANGED
    assert json.loads(response.payload) is True


@pytest.mark.asyncio
async def test_confirmable_request_is_acknowledged_with_piggybacked_response(client):
    response = await post(client, VALID_ALERT, tuning=Reliable)
    assert response.mtype == aiocoap.ACK


@pytest.mark.asyncio
async def test_non_confirmable_request_is_accepted(client):
    response = await post(client, VALID_ALERT, tuning=Unreliable)
    assert response.code == Code.CHANGED


@pytest.mark.asyncio
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
        b"{not json",
        b"\xff\xfe",
        b"",
    ],
)
async def test_unexpected_values_return_400(client, body):
    response = await post(client, body)
    assert response.code == Code.BAD_REQUEST
    assert json.loads(response.payload) is False


@pytest.mark.asyncio
async def test_server_keeps_working_after_bad_request(client):
    await post(client, b"{not json")
    response = await post(client, VALID_ALERT)
    assert response.code == Code.CHANGED


@pytest.mark.asyncio
async def test_unknown_path_returns_404(client):
    response = await post(client, VALID_ALERT, path="other")
    assert response.code == Code.NOT_FOUND


@pytest.mark.asyncio
async def test_get_on_alert_is_not_allowed(client):
    request = Message(code=Code.GET, uri=f"coap://127.0.0.1:{PORT}/alert")
    response = await client.request(request).response
    assert response.code == Code.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_valid_alert_is_saved_with_message_type_and_id(client):
    await post(client, VALID_ALERT, tuning=Reliable)
    assert len(saved) == 1
    alert, mtype, mid = saved[0]
    assert alert.device_id == "esp32-01"
    assert mtype == aiocoap.CON
    assert 0 <= mid <= 65535


@pytest.mark.asyncio
async def test_rejected_alert_is_not_saved(client):
    await post(client, {"device_id": "esp32-01"})
    assert saved == []


@pytest.mark.asyncio
async def test_save_failure_returns_500():
    def failing_save(alert, request):
        raise RuntimeError("db down")

    server = await aiocoap.Context.create_server_context(
        create_site(failing_save), bind=("127.0.0.1", PORT + 1)
    )
    client = await aiocoap.Context.create_client_context()
    try:
        request = Message(
            code=Code.POST,
            payload=json.dumps(VALID_ALERT).encode(),
            uri=f"coap://127.0.0.1:{PORT + 1}/alert",
        )
        response = await client.request(request).response
        assert response.code == Code.INTERNAL_SERVER_ERROR
        assert json.loads(response.payload) is False
    finally:
        await client.shutdown()
        await server.shutdown()
