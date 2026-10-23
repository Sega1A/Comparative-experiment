import argparse
import csv
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db.database import get_session
from common.db.models import AlertaBase, AlertaCoAP, AlertaHTTP, AlertaMQTT
from common.schemas import REPO_ROOT

RESULTS_DIR = REPO_ROOT / "results"

MODELS: dict[str, type[AlertaBase]] = {
    "http": AlertaHTTP,
    "mqtt": AlertaMQTT,
    "coap": AlertaCoAP,
}

COMMON_COLUMNS = [
    "protocol",
    "id",
    "recibido_en",
    "enviado_en",
    "latency_ms",
    "tamano_bytes",
    "perfil_red",
    "payload",
]


def column_names(model: type[AlertaBase]) -> list[str]:
    return [column.name for column in model.__table__.columns]


def specific_columns(model: type[AlertaBase]) -> list[str]:
    shared = set.intersection(*(set(column_names(m)) for m in MODELS.values()))
    return [name for name in column_names(model) if name not in shared]


def latency_ms(alert: AlertaBase) -> float | None:
    if alert.enviado_en is None or alert.recibido_en is None:
        return None
    delta = _as_utc(alert.recibido_en) - _as_utc(alert.enviado_en)
    return round(delta.total_seconds() * 1000, 3)


def to_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def alert_to_row(alert: AlertaBase, protocol: str) -> dict[str, Any]:
    row: dict[str, Any] = {"protocol": protocol, "latency_ms": latency_ms(alert)}
    for name in column_names(type(alert)):
        row[name] = getattr(alert, name)
    return {key: to_csv_value(value) for key, value in row.items()}


def fetch_alerts(
    session: Session,
    model: type[AlertaBase],
    network_profile: str | None = None,
) -> list[AlertaBase]:
    query = select(model).order_by(model.recibido_en, model.id)
    if network_profile is not None:
        query = query.where(model.perfil_red == network_profile)
    return list(session.scalars(query))


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def export_results(
    session: Session,
    protocols: Sequence[str],
    output_dir: Path,
    network_profile: str | None = None,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    all_rows: list[dict[str, Any]] = []
    for protocol in protocols:
        model = MODELS[protocol]
        alerts = fetch_alerts(session, model, network_profile)
        rows = [alert_to_row(alert, protocol) for alert in alerts]
        columns = COMMON_COLUMNS + specific_columns(model)
        counts[protocol] = write_csv(
            output_dir / f"alerts_{protocol}.csv", columns, rows
        )
        all_rows.extend(rows)
    if len(protocols) > 1:
        counts["all"] = write_csv(
            output_dir / "alerts_all.csv", COMMON_COLUMNS, all_rows
        )
    return counts


def default_output_dir() -> Path:
    return RESULTS_DIR / datetime.now(UTC).strftime("export_%Y%m%d_%H%M%S")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export stored alerts to CSV files.")
    parser.add_argument(
        "--protocol",
        choices=[*MODELS, "all"],
        default="all",
        help="protocol to export (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output folder (default: results/export_<UTC timestamp>)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="export only alerts with this perfil_red value",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    protocols = list(MODELS) if args.protocol == "all" else [args.protocol]
    output_dir = args.output or default_output_dir()
    with get_session() as session:
        counts = export_results(session, protocols, output_dir, args.profile)
    print(f"Exported to {output_dir}")
    for name, count in counts.items():
        print(f"  alerts_{name}.csv: {count} rows")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


if __name__ == "__main__":
    main()
