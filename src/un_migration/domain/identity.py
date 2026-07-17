import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol, Self

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9.-]{0,127}$")


class StableId(str):
    """A normalized identifier safe for manifests and managed paths."""

    def __new__(cls, value: str) -> Self:
        normalized = re.sub(r"[\s_]+", "-", value.strip().casefold())
        if not _SAFE_ID.fullmatch(normalized):
            raise ValueError(f"Invalid {cls.__name__}: {value!r}")
        return super().__new__(cls, normalized)


class RunId(StableId):
    """Stable migration run identifier."""


class DatasetId(StableId):
    """Stable logical dataset identifier."""


class StepId(StableId):
    """Stable migration plan step identifier."""


class FindingId(StableId):
    """Stable validation finding identifier."""


class ArtifactId(StableId):
    """Stable output artifact identifier."""


class IdGenerator(Protocol):
    """Generate a stable ID string with a caller-supplied prefix."""

    def new(self, prefix: str) -> str: ...


@dataclass
class SequenceIdGenerator:
    """Deterministic ID generator for tests and reproducible examples."""

    start: int = 1
    _next: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("Sequence start must be nonnegative.")
        self._next = self.start

    def new(self, prefix: str) -> str:
        safe_prefix = StableId(prefix)
        value = f"{safe_prefix}-{self._next:06d}"
        self._next += 1
        return value


class Uuid7LikeGenerator:
    """Generate time-sortable IDs without claiming UUIDv7 conformance."""

    def new(self, prefix: str) -> str:
        safe_prefix = StableId(prefix)
        millis = int(time.time() * 1000)
        suffix = uuid.uuid4().hex[:16]
        return f"{safe_prefix}-{millis:013d}-{suffix}"
