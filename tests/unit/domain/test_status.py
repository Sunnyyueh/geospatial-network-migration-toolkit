import pytest

from un_migration.domain.status import (
    RunState,
    Severity,
    can_transition,
    highest_severity,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunState.CREATED, RunState.CONFIGURED),
        (RunState.VALIDATED, RunState.ACCEPTED),
        (RunState.ACCEPTED, RunState.DEPLOYED),
        (RunState.STAGED, RunState.FAILED),
        (RunState.PLANNED, RunState.CANCELLED),
    ],
)
def test_allowed_transitions(current: RunState, target: RunState) -> None:
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunState.CREATED, RunState.PLANNED),
        (RunState.DEPLOYED, RunState.FAILED),
        (RunState.CANCELLED, RunState.CONFIGURED),
        (RunState.FAILED, RunState.CREATED),
    ],
)
def test_disallowed_transitions(current: RunState, target: RunState) -> None:
    assert not can_transition(current, target)


def test_severity_order_matches_acceptance_semantics() -> None:
    assert Severity.CRITICAL > Severity.ERROR > Severity.WARNING > Severity.INFO


def test_highest_severity_handles_values_and_empty_input() -> None:
    assert highest_severity([Severity.INFO, Severity.ERROR]) is Severity.ERROR
    assert highest_severity([]) is None
