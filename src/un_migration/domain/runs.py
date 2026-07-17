from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from un_migration.domain.artifacts import Artifact, Checksum
from un_migration.domain.errors import ErrorContext, IntegrityError
from un_migration.domain.findings import FindingCollection
from un_migration.domain.identity import RunId, StepId
from un_migration.domain.status import (
    AcceptanceStatus,
    RunState,
    can_transition,
)


class StepKind(StrEnum):
    """Portable operation represented by a migration plan step."""

    CONFIGURE = "configure"
    PLAN = "plan"
    INVENTORY = "inventory"
    EXTRACT = "extract"
    TRANSFORM = "transform"
    STAGE = "stage"
    VALIDATE = "validate"
    REPORT = "report"
    DEPLOY = "deploy"
    NOTIFY = "notify"


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One immutable operation and its dependencies."""

    id: StepId
    kind: StepKind
    prerequisites: tuple[StepId, ...] = ()
    idempotent: bool = True

    def __post_init__(self) -> None:
        if len(self.prerequisites) != len(set(self.prerequisites)):
            raise ValueError("plan step contains duplicate prerequisites")


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    """Dependency-ordered set of migration operations."""

    steps: tuple[PlanStep, ...]

    def ordered_steps(self) -> tuple[PlanStep, ...]:
        """Return a stable topological order and reject invalid graphs."""

        by_id = {step.id: step for step in self.steps}
        if len(by_id) != len(self.steps):
            raise ValueError("plan contains duplicate step IDs")

        indegree = {step.id: 0 for step in self.steps}
        dependents: dict[StepId, list[StepId]] = defaultdict(list)
        for step in self.steps:
            for prerequisite in step.prerequisites:
                if prerequisite not in by_id:
                    raise ValueError(f"unknown prerequisite: {prerequisite}")
                indegree[step.id] += 1
                dependents[prerequisite].append(step.id)

        ready: deque[StepId] = deque(
            step.id for step in self.steps if indegree[step.id] == 0
        )
        ordered: list[PlanStep] = []
        while ready:
            current = ready.popleft()
            ordered.append(by_id[current])
            for dependent in dependents[current]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)

        if len(ordered) != len(self.steps):
            raise ValueError("plan contains a dependency cycle")
        return tuple(ordered)


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """Durable evidence that one idempotent plan step completed."""

    run_id: RunId
    step_id: StepId
    input_checksum: Checksum
    output_checksum: Checksum
    completed_at: datetime

    def __post_init__(self) -> None:
        if self.completed_at.tzinfo is None:
            raise ValueError("checkpoint completed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class MigrationRun:
    """Identity and current lifecycle state for one migration execution."""

    id: RunId
    state: RunState
    started_at: datetime

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise ValueError("run started_at must be timezone-aware")

    def transition(self, target: RunState) -> "MigrationRun":
        """Return a copy in the target state or raise an integrity error."""

        if not can_transition(self.state, target):
            raise IntegrityError(
                code="run.invalid-transition",
                message=(f"Cannot move from {self.state.value} to {target.value}."),
                guidance="Follow the migration plan state order.",
                context=ErrorContext(run_id=str(self.id)),
            )
        return replace(self, state=target)


@dataclass(frozen=True, slots=True)
class RunMetrics:
    """Portable counts and timing for a migration run."""

    selected: int = 0
    transformed: int = 0
    staged: int = 0
    rejected: int = 0
    validated: int = 0
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.selected,
            self.transformed,
            self.staged,
            self.rejected,
            self.validated,
            self.duration_seconds,
        )
        if any(value < 0 for value in values):
            raise ValueError("run metrics must be nonnegative")


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Final run state, evidence, artifacts, and counters."""

    run: MigrationRun
    acceptance: AcceptanceStatus
    findings: FindingCollection
    artifacts: tuple[Artifact, ...]
    metrics: RunMetrics
