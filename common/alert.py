import types
from dataclasses import MISSING, dataclass, fields
from typing import Any, Union, get_args, get_origin


class InvalidAlertError(ValueError):
    pass


@dataclass(frozen=True)
class AlertDTO:
    device_id: str
    sequence: int
    timestamp: int
    event_type: str | None = None
    battery_level: int | None = None
    acceleration: float | None = None

    @classmethod
    def from_payload(cls, payload: Any) -> "AlertDTO":
        if not isinstance(payload, dict):
            raise InvalidAlertError("payload must be a JSON object")

        definitions = fields(cls)
        names = {field.name for field in definitions}
        required = {field.name for field in definitions if field.default is MISSING}
        received = set(payload)

        missing = required - received
        if missing:
            raise InvalidAlertError(f"missing fields: {sorted(missing)}")

        unexpected = received - names
        if unexpected:
            raise InvalidAlertError(f"unexpected fields: {sorted(unexpected)}")

        for field in definitions:
            value = payload.get(field.name)
            if field.name not in required and value is None:
                continue
            expected = _base_type(field.type)
            if not _matches_type(value, expected):
                raise InvalidAlertError(f"'{field.name}' must be {expected.__name__}")

        return cls(**payload)

    def to_payload(self) -> dict[str, Any]:
        values = {field.name: getattr(self, field.name) for field in fields(self)}
        return {name: value for name, value in values.items() if value is not None}


def _base_type(annotation: Any) -> type:
    if get_origin(annotation) in (Union, types.UnionType):
        return next(arg for arg in get_args(annotation) if arg is not type(None))
    return annotation


def _matches_type(value: Any, expected_type: type) -> bool:
    if isinstance(value, bool) and expected_type is not bool:
        return False
    if expected_type is float and isinstance(value, int):
        return True
    return isinstance(value, expected_type)
