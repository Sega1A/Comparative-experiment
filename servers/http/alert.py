from dataclasses import dataclass, fields
from typing import Any


class InvalidAlertError(ValueError):
    pass


@dataclass(frozen=True)
class AlertDTO:
    device_id: str
    sequence: int
    timestamp: int

    @classmethod
    def from_payload(cls, payload: Any) -> "AlertDTO":
        if not isinstance(payload, dict):
            raise InvalidAlertError("payload must be a JSON object")

        expected = {field.name: field.type for field in fields(cls)}
        received = set(payload)

        missing = expected.keys() - received
        if missing:
            raise InvalidAlertError(f"missing fields: {sorted(missing)}")

        unexpected = received - expected.keys()
        if unexpected:
            raise InvalidAlertError(f"unexpected fields: {sorted(unexpected)}")

        for name, expected_type in expected.items():
            if not _matches_type(payload[name], expected_type):
                raise InvalidAlertError(
                    f"field '{name}' must be of type {expected_type.__name__}"
                )

        return cls(**payload)


def _matches_type(value: Any, expected_type: type) -> bool:
    if isinstance(value, bool) and expected_type is not bool:
        return False
    return isinstance(value, expected_type)
