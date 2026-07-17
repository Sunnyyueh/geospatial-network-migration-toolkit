from datetime import UTC, datetime
from pathlib import Path

import pytest

from un_migration.domain.artifacts import Checksum
from un_migration.domain.errors import IntegrityError
from un_migration.domain.identity import RunId, StepId
from un_migration.domain.runs import Checkpoint, PlanStep, StepKind
from un_migration.workflow.checkpoints import (
    FilesystemCheckpointStore,
    can_resume_step,
)


def checkpoint(output: bytes = b"output") -> Checkpoint:
    return Checkpoint(
        RunId("run-1"),
        StepId("transform"),
        Checksum.sha256(b"input"),
        Checksum.sha256(output),
        datetime(2026, 7, 16, 12, 30, tzinfo=UTC),
    )


def test_checkpoint_store_round_trips_canonical_json(tmp_path: Path) -> None:
    store = FilesystemCheckpointStore(tmp_path)
    value = checkpoint()

    store.save(value)

    assert store.load(value.run_id, value.step_id) == value
    text = (tmp_path / "run-1" / "checkpoints" / "transform.json").read_text()
    assert text.endswith("\n")
    assert '"completed_at":"2026-07-16T12:30:00Z"' in text


def test_checkpoint_store_allows_idempotent_identical_save(tmp_path: Path) -> None:
    store = FilesystemCheckpointStore(tmp_path)
    value = checkpoint()

    store.save(value)
    store.save(value)

    assert store.load(value.run_id, value.step_id) == value


def test_checkpoint_store_rejects_conflicting_save(tmp_path: Path) -> None:
    store = FilesystemCheckpointStore(tmp_path)
    store.save(checkpoint())

    with pytest.raises(IntegrityError) as raised:
        store.save(checkpoint(b"changed"))

    assert raised.value.code == "checkpoint.conflict"


def test_checkpoint_store_rejects_corrupt_payload(tmp_path: Path) -> None:
    path = tmp_path / "run-1" / "checkpoints"
    path.mkdir(parents=True)
    (path / "transform.json").write_text('{"broken":true}\n', encoding="utf-8")

    with pytest.raises(IntegrityError) as raised:
        FilesystemCheckpointStore(tmp_path).load(RunId("run-1"), StepId("transform"))

    assert raised.value.code == "checkpoint.corrupt"


def test_missing_checkpoint_returns_none(tmp_path: Path) -> None:
    assert (
        FilesystemCheckpointStore(tmp_path).load(RunId("run-1"), StepId("transform"))
        is None
    )


def test_resume_requires_idempotent_step_and_matching_input() -> None:
    value = checkpoint()
    idempotent = PlanStep(StepId("transform"), StepKind.TRANSFORM)
    non_idempotent = PlanStep(StepId("deploy"), StepKind.DEPLOY, idempotent=False)

    assert can_resume_step(idempotent, value, Checksum.sha256(b"input"))
    assert not can_resume_step(idempotent, value, Checksum.sha256(b"changed"))
    assert not can_resume_step(non_idempotent, value, value.input_checksum)
    assert not can_resume_step(idempotent, None, value.input_checksum)
