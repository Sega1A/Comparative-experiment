from contextlib import contextmanager

from common.db import AlertaHTTP, repository
from common.schemas import parse_alert

ALERT = parse_alert(
    '{"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}'
)


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, row):
        self.added.append(row)


def test_store_alert_builds_row_from_alert_and_metadata(monkeypatch):
    session = FakeSession()

    @contextmanager
    def fake_session():
        yield session

    class FakeSettings:
        network_profile = "ideal"

    monkeypatch.setattr(repository, "get_session", fake_session)
    monkeypatch.setattr(repository, "get_settings", lambda: FakeSettings())

    repository.store_alert(AlertaHTTP, ALERT, 68, ip_origen="1.2.3.4", content_type="x")

    (row,) = session.added
    assert isinstance(row, AlertaHTTP)
    assert row.payload == ALERT.to_payload()
    assert row.tamano_bytes == 68
    assert row.enviado_en == ALERT.sent_at
    assert row.perfil_red == "ideal"
    assert (row.ip_origen, row.content_type) == ("1.2.3.4", "x")
