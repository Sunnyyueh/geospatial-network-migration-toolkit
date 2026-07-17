from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Supply timezone-aware instants to application services."""

    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Return one fixed instant for deterministic tests and examples."""

    instant: datetime

    def __post_init__(self) -> None:
        if self.instant.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware instant.")

    def now(self) -> datetime:
        return self.instant


class SystemClock:
    """Return the current UTC instant."""

    def now(self) -> datetime:
        return datetime.now(UTC)
