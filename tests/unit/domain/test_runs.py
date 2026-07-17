from dataclasses import replace
from datetime import UTC, datetime

import pytest

from un_migration.domain.errors import IntegrityError
from un_migration.domain.identity import RunId, StepId
from un_migration.domain.runs import (
    MigrationPlan,
    MigrationRun,
    PlanStep,
    RunMetrics,
    StepKind,
)
from un_migration.domain.status import RunState


def test_plan_orders_steps_by_dependencies() -> None:
    configure = PlanStep(StepId("configure"), StepKind.CONFIGURE)
    inventory = PlanStep(
        StepId("inventory"),
        StepKind.INVENTORY,
        prerequisites=(configure.id,),
    )

    plan = MigrationPlan((inventory, configure))

    assert [str(step.id) for step in plan.ordered_steps()] == [
        "configure",
        "inventory",
    ]


def test_plan_rejects_unknown_prerequisite() -> None:
    step = PlanStep(
        StepId("inventory"),
        StepKind.INVENTORY,
        prerequisites=(StepId("configure"),),
    )

    with pytest.raises(ValueError, match="unknown prerequisite"):
        MigrationPlan((step,)).ordered_steps()


def test_plan_rejects_dependency_cycle() -> None:
    first = PlanStep(
        StepId("first"),
        StepKind.CONFIGURE,
        prerequisites=(StepId("second"),),
    )
    second = PlanStep(
        StepId("second"),
        StepKind.INVENTORY,
        prerequisites=(StepId("first"),),
    )

    with pytest.raises(ValueError, match="cycle"):
        MigrationPlan((first, second)).ordered_steps()


def test_run_transition_returns_new_valid_state() -> None:
    run = MigrationRun(
        id=RunId("run-1"),
        state=RunState.CREATED,
        started_at=datetime(2026, 7, 16, tzinfo=UTC),
    )

    configured = run.transition(RunState.CONFIGURED)

    assert configured.state is RunState.CONFIGURED
    assert run.state is RunState.CREATED


def test_run_rejects_invalid_transition() -> None:
    run = MigrationRun(
        id=RunId("run-1"),
        state=RunState.CREATED,
        started_at=datetime(2026, 7, 16, tzinfo=UTC),
    )

    with pytest.raises(IntegrityError, match=r"run\.invalid-transition"):
        run.transition(RunState.STAGED)


def test_run_requires_timezone_aware_start() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MigrationRun(
            id=RunId("run-1"),
            state=RunState.CREATED,
            started_at=datetime(2026, 7, 16),
        )


def test_metrics_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        RunMetrics(selected=-1)


def test_plan_step_can_be_immutably_replaced() -> None:
    step = PlanStep(StepId("inventory"), StepKind.INVENTORY)
    configure = StepId("configure")

    changed = replace(step, prerequisites=(configure,))

    assert changed.prerequisites == (configure,)
    assert step.prerequisites == ()
