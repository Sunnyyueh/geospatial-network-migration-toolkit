import json
from datetime import datetime
from pathlib import Path

from un_migration.adapters.filesystem.artifacts import ManagedArtifactStore
from un_migration.domain.artifacts import Checksum
from un_migration.domain.errors import ErrorContext, IntegrityError
from un_migration.domain.identity import RunId, StepId
from un_migration.domain.runs import Checkpoint, PlanStep
from un_migration.domain.serialization import canonical_json


class FilesystemCheckpointStore:
    """Durable canonical JSON checkpoints stored below a managed root."""

    def __init__(self, root: Path) -> None:
        self.store = ManagedArtifactStore(root)

    @staticmethod
    def _logical(run_id: RunId, step_id: StepId) -> str:
        return f"{run_id}/checkpoints/{step_id}.json"

    @staticmethod
    def _error(
        code: str,
        message: str,
        run_id: RunId,
        step_id: StepId,
    ) -> IntegrityError:
        return IntegrityError(
            code=code,
            message=message,
            guidance="Discard the invalid checkpoint and rerun the affected step.",
            context=ErrorContext(run_id=str(run_id), step_id=str(step_id)),
        )

    def save(self, checkpoint: Checkpoint) -> None:
        existing = self.load(checkpoint.run_id, checkpoint.step_id)
        if existing is not None:
            if existing == checkpoint:
                return
            raise self._error(
                "checkpoint.conflict",
                "A different checkpoint already exists for this run step.",
                checkpoint.run_id,
                checkpoint.step_id,
            )
        payload = (canonical_json(checkpoint) + "\n").encode("utf-8")
        self.store.write(
            self._logical(checkpoint.run_id, checkpoint.step_id),
            payload,
            "application/json",
        )

    @staticmethod
    def _checksum(value: object) -> Checksum:
        if not isinstance(value, dict):
            raise TypeError("checksum must be an object")
        return Checksum(str(value["algorithm"]), str(value["digest"]))

    def load(self, run_id: RunId, step_id: StepId) -> Checkpoint | None:
        logical = self._logical(run_id, step_id)
        path = self.store.root / logical
        if not path.is_file():
            return None
        try:
            raw = json.loads(self.store.read(logical))
            if not isinstance(raw, dict):
                raise TypeError("checkpoint root must be an object")
            completed_at = raw["completed_at"]
            if not isinstance(completed_at, str):
                raise TypeError("completed_at must be text")
            checkpoint = Checkpoint(
                RunId(str(raw["run_id"])),
                StepId(str(raw["step_id"])),
                self._checksum(raw["input_checksum"]),
                self._checksum(raw["output_checksum"]),
                datetime.fromisoformat(completed_at.replace("Z", "+00:00")),
            )
            if checkpoint.run_id != run_id or checkpoint.step_id != step_id:
                raise ValueError("checkpoint identity mismatch")
            return checkpoint
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise self._error(
                "checkpoint.corrupt",
                "Checkpoint payload is invalid or does not match its path.",
                run_id,
                step_id,
            ) from error


def can_resume_step(
    step: PlanStep,
    checkpoint: Checkpoint | None,
    input_checksum: Checksum,
) -> bool:
    """Return whether an idempotent step has matching durable input evidence."""

    return (
        step.idempotent
        and checkpoint is not None
        and checkpoint.step_id == step.id
        and checkpoint.input_checksum == input_checksum
    )
