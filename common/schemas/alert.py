"""Mensaje de alerta común a los tres protocolos (HTTP, MQTT y CoAP).

El dispositivo envía un objeto JSON. Los servidores lo validan con
`parse_alert()` y guardan `alert.to_payload()`; no definen formatos propios.

    {"device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000}

`timestamp` son milisegundos desde epoch (UTC). Los campos opcionales pueden
omitirse; cualquier otro campo se rechaza.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class InvalidAlertError(ValueError):
    """El mensaje no es JSON o no cumple el formato de alerta."""


class AlertDTO(BaseModel):
    # strict: "1" no vale como entero y True no vale como número.
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    device_id: str
    sequence: int
    timestamp: int
    event_type: str | None = None
    battery_level: int | None = None
    acceleration: float | None = None

    @property
    def sent_at(self) -> datetime:
        """Momento de envío (UTC) a partir del `timestamp` en milisegundos."""
        return datetime.fromtimestamp(self.timestamp / 1000, tz=UTC)

    def to_payload(self) -> dict[str, Any]:
        """Los campos presentes, tal como se guardan en la columna `payload`."""
        return self.model_dump(exclude_none=True)


def parse_alert(raw: str | bytes | bytearray) -> AlertDTO:
    """Convierte el cuerpo de un mensaje en `AlertDTO` o lanza InvalidAlertError."""
    try:
        alert = AlertDTO.model_validate_json(raw)
        _ = alert.sent_at  # falla si el timestamp no es una fecha válida
    except ValidationError as error:
        raise InvalidAlertError(_describe(error)) from error
    except (OverflowError, OSError, ValueError) as error:
        raise InvalidAlertError("'timestamp' is out of range") from error
    return alert


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'body'}: {item['msg']}"
        for item in error.errors(include_url=False)
    )
