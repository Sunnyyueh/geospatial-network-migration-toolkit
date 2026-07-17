from collections.abc import Iterable
from enum import IntEnum, StrEnum


class RunState(StrEnum):
    """Lifecycle state of a migration run."""

    CREATED = "created"
    CONFIGURED = "configured"
    PLANNED = "planned"
    INVENTORIED = "inventoried"
    EXTRACTED = "extracted"
    TRANSFORMED = "transformed"
    STAGED = "staged"
    VALIDATED = "validated"
    ACCEPTED = "accepted"
    DEPLOYED = "deployed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Severity(IntEnum):
    """Ordered validation severity."""

    INFO = 10
    WARNING = 20
    ERROR = 30
    CRITICAL = 40


class FindingStatus(StrEnum):
    """Outcome of one validation rule evaluation."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AcceptanceStatus(StrEnum):
    """High-level acceptance outcome for a migration run."""

    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    REJECTED = "rejected"
    INCOMPLETE = "incomplete"


_NEXT_STATES: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({RunState.CONFIGURED}),
    RunState.CONFIGURED: frozenset({RunState.PLANNED}),
    RunState.PLANNED: frozenset({RunState.INVENTORIED}),
    RunState.INVENTORIED: frozenset({RunState.EXTRACTED}),
    RunState.EXTRACTED: frozenset({RunState.TRANSFORMED}),
    RunState.TRANSFORMED: frozenset({RunState.STAGED}),
    RunState.STAGED: frozenset({RunState.VALIDATED}),
    RunState.VALIDATED: frozenset({RunState.ACCEPTED}),
    RunState.ACCEPTED: frozenset({RunState.DEPLOYED}),
    RunState.DEPLOYED: frozenset(),
    RunState.CANCELLED: frozenset(),
    RunState.FAILED: frozenset(),
}

_TERMINAL_STATES = frozenset({RunState.DEPLOYED, RunState.CANCELLED, RunState.FAILED})


def can_transition(current: RunState, target: RunState) -> bool:
    """Return whether the state machine permits a transition."""

    if current in _TERMINAL_STATES:
        return False
    if target in {RunState.CANCELLED, RunState.FAILED}:
        return True
    return target in _NEXT_STATES[current]


def highest_severity(values: Iterable[Severity]) -> Severity | None:
    """Return the highest severity, or None when no values are supplied."""

    return max(values, default=None)
