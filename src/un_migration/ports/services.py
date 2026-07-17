from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from un_migration.domain.artifacts import Artifact
from un_migration.domain.identity import RunId, StepId
from un_migration.domain.runs import Checkpoint, RunSummary
from un_migration.ports.source import AdapterCapabilities


@dataclass(frozen=True, slots=True)
class Notification:
    """Redacted reviewer message and managed artifact references."""

    subject: str
    message: str
    artifact_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("notification subject must not be empty")
        if not self.message.strip():
            raise ValueError("notification message must not be empty")


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    """Evidence returned by a notification provider."""

    provider: str
    message_id: str
    accepted: bool


@runtime_checkable
class ArtifactStore(Protocol):
    """Persist and verify managed migration artifacts."""

    def write(
        self,
        path: str,
        payload: bytes,
        media_type: str,
    ) -> Artifact: ...

    def read(self, path: str) -> bytes: ...

    def list(self) -> tuple[Artifact, ...]: ...

    def verify(self, artifact: Artifact) -> bool: ...


@runtime_checkable
class CheckpointStore(Protocol):
    """Persist and retrieve workflow checkpoints."""

    def save(self, checkpoint: Checkpoint) -> None: ...

    def load(
        self,
        run_id: RunId,
        step_id: StepId,
    ) -> Checkpoint | None: ...


@runtime_checkable
class DeploymentTarget(Protocol):
    """Preflight and deploy an accepted migration summary."""

    def capabilities(self) -> AdapterCapabilities: ...

    def preflight(self, summary: RunSummary) -> tuple[str, ...]: ...

    def deploy(self, summary: RunSummary) -> tuple[Artifact, ...]: ...


@runtime_checkable
class Notifier(Protocol):
    """Deliver a redacted reviewer notification."""

    def deliver(self, notification: Notification) -> DeliveryReceipt: ...
