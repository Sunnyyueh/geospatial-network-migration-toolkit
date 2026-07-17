import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Literal

from un_migration.domain.serialization import canonical_json

EventLevel = Literal["debug", "info", "warning", "error", "critical"]
_SECRET_KEY = re.compile(
    r"(?:token|password|secret|credential|authorization|api[_-]?key)",
    re.IGNORECASE,
)
_REDACTED = "***REDACTED***"


@dataclass(frozen=True, slots=True)
class RunEvent:
    sequence: int
    timestamp: datetime
    level: EventLevel
    event: str
    data: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("event sequence must be positive")
        if self.timestamp.tzinfo is None:
            raise ValueError("event timestamp must be timezone-aware")
        if not self.event.strip():
            raise ValueError("event name must not be empty")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


def _redact(value: object, secrets: tuple[str, ...], key: str | None = None) -> object:
    if key is not None and _SECRET_KEY.search(key):
        return _REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): _redact(item, secrets, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, tuple | list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, _REDACTED)
        return redacted
    return value


def render_event_log(
    events: tuple[RunEvent, ...],
    *,
    secrets: tuple[str, ...] = (),
) -> bytes:
    """Render ordered, recursively redacted JSON Lines run events."""

    sequences = [event.sequence for event in events]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise ValueError("event sequences must be unique and ordered")
    lines = []
    for event in events:
        timestamp = (
            event.timestamp.astimezone(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        lines.append(
            canonical_json(
                {
                    "sequence": event.sequence,
                    "timestamp": timestamp,
                    "level": event.level,
                    "event": event.event,
                    "data": _redact(event.data, secrets),
                }
            )
        )
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")
