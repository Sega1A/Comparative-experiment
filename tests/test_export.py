import csv
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from common.db import export
from common.db.models import AlertaCoAP, AlertaHTTP, AlertaMQTT, Base

SENT_AT = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
PAYLOAD = {"device_id": "esp32-01", "sequence": 1, "event": "caída"}


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(type_, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                AlertaHTTP(
                    payload=PAYLOAD,
                    tamano_bytes=64,
                    enviado_en=SENT_AT,
                    recibido_en=SENT_AT + timedelta(milliseconds=42),
                    perfil_red="ideal",
                    ip_origen="127.0.0.1",
                    content_type="application/json",
                ),
                AlertaHTTP(
                    payload=PAYLOAD,
                    tamano_bytes=64,
                    enviado_en=None,
                    recibido_en=SENT_AT + timedelta(seconds=1),
                    perfil_red="lossy",
                    ip_origen="127.0.0.1",
                    content_type=None,
                ),
                AlertaMQTT(
                    payload=PAYLOAD,
                    tamano_bytes=48,
                    enviado_en=SENT_AT,
                    recibido_en=SENT_AT + timedelta(milliseconds=15),
                    perfil_red="ideal",
                    topic="alerts/falls",
                    qos=1,
                ),
                AlertaCoAP(
                    payload=PAYLOAD,
                    tamano_bytes=32,
                    enviado_en=SENT_AT,
                    recibido_en=SENT_AT + timedelta(milliseconds=9),
                    perfil_red="ideal",
                    tipo_mensaje="CON",
                    message_id=7,
                ),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_latency_is_computed_in_milliseconds():
    alert = AlertaHTTP(
        enviado_en=SENT_AT, recibido_en=SENT_AT + timedelta(milliseconds=12.5)
    )
    assert export.latency_ms(alert) == 12.5


def test_latency_is_empty_without_sent_time():
    alert = AlertaHTTP(enviado_en=None, recibido_en=SENT_AT)
    assert export.latency_ms(alert) is None


def test_values_are_converted_for_csv():
    local_time = datetime(2026, 10, 20, 8, 0, tzinfo=timezone(timedelta(hours=-4)))
    assert export.to_csv_value(None) == ""
    assert export.to_csv_value(local_time) == "2026-10-20T12:00:00+00:00"
    assert export.to_csv_value({"a": "ñ"}) == '{"a":"ñ"}'
    assert export.to_csv_value(5) == 5


def test_specific_columns_per_protocol():
    assert export.specific_columns(AlertaHTTP) == ["ip_origen", "content_type"]
    assert export.specific_columns(AlertaMQTT) == ["topic", "qos"]
    assert export.specific_columns(AlertaCoAP) == ["tipo_mensaje", "message_id"]


def test_export_all_protocols_writes_one_file_per_protocol_and_combined(
    session, tmp_path
):
    counts = export.export_results(session, list(export.MODELS), tmp_path)

    assert counts == {"http": 2, "mqtt": 1, "coap": 1, "all": 4}

    http_rows = read_csv(tmp_path / "alerts_http.csv")
    assert list(http_rows[0]) == export.COMMON_COLUMNS + ["ip_origen", "content_type"]
    assert http_rows[0]["protocol"] == "http"
    assert http_rows[0]["latency_ms"] == "42.0"
    assert http_rows[0]["recibido_en"] == "2026-10-20T12:00:00.042000+00:00"
    assert json.loads(http_rows[0]["payload"]) == PAYLOAD
    assert http_rows[1]["latency_ms"] == ""
    assert http_rows[1]["content_type"] == ""

    mqtt_rows = read_csv(tmp_path / "alerts_mqtt.csv")
    assert mqtt_rows[0]["topic"] == "alerts/falls"
    assert mqtt_rows[0]["qos"] == "1"

    all_rows = read_csv(tmp_path / "alerts_all.csv")
    assert list(all_rows[0]) == export.COMMON_COLUMNS
    assert [row["protocol"] for row in all_rows] == ["http", "http", "mqtt", "coap"]


def test_export_single_protocol_skips_combined_file(session, tmp_path):
    counts = export.export_results(session, ["coap"], tmp_path)

    assert counts == {"coap": 1}
    assert (tmp_path / "alerts_coap.csv").exists()
    assert not (tmp_path / "alerts_all.csv").exists()


def test_export_filters_by_network_profile(session, tmp_path):
    counts = export.export_results(session, ["http"], tmp_path, network_profile="lossy")

    assert counts == {"http": 1}
    assert read_csv(tmp_path / "alerts_http.csv")[0]["perfil_red"] == "lossy"


def test_export_with_no_alerts_writes_header_only(session, tmp_path):
    export.export_results(session, ["mqtt"], tmp_path, network_profile="missing")

    content = (tmp_path / "alerts_mqtt.csv").read_text(encoding="utf-8")
    assert content.strip() == ",".join(export.COMMON_COLUMNS + ["topic", "qos"])


def test_main_exports_using_command_line_options(
    session, tmp_path, monkeypatch, caplog
):
    @contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr(export, "get_session", fake_session)

    with caplog.at_level("INFO", logger="common.db.export"):
        export.main(
            ["--protocol", "http", "--output", str(tmp_path), "--profile", "ideal"]
        )

    assert len(read_csv(tmp_path / "alerts_http.csv")) == 1
    assert "alerts_http.csv: 1 rows" in caplog.text


def test_default_output_dir_is_inside_results():
    output_dir = export.default_output_dir()
    assert output_dir.parent == export.RESULTS_DIR
    assert output_dir.name.startswith("export_")
