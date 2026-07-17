import json
from pathlib import Path

import pytest

from un_migration.adapters.filesystem.artifacts import ManagedArtifactStore
from un_migration.adapters.filesystem.staging import CsvStagingWriter
from un_migration.domain.artifacts import ArtifactKind
from un_migration.domain.errors import StagingError
from un_migration.domain.identity import DatasetId, RunId


def test_artifact_store_writes_reads_lists_and_verifies(tmp_path: Path) -> None:
    store = ManagedArtifactStore(tmp_path)

    artifact = store.write(
        "run-1/reports/summary.json", b'{"valid":true}', "application/json"
    )

    assert artifact.kind is ArtifactKind.REPORT
    assert store.read(artifact.path) == b'{"valid":true}'
    assert store.list() == (artifact,)
    assert store.verify(artifact)


@pytest.mark.parametrize("path", ["../secret", "/absolute", "bad\\path"])
def test_artifact_store_rejects_unmanaged_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError, match="managed"):
        ManagedArtifactStore(tmp_path).write(path, b"value", "text/plain")


def test_staging_writer_persists_multiple_batches_and_finalizes_artifact(
    tmp_path: Path,
) -> None:
    writer = CsvStagingWriter(tmp_path)
    writer.initialize(RunId("run-1"))

    assert (
        writer.write_batch(
            DatasetId("utility-lines"),
            ({"asset_id": "A-1", "active": True, "diameter": 4},),
        )
        == 1
    )
    assert (
        writer.write_batch(
            DatasetId("utility-lines"),
            ({"asset_id": "A-2", "active": False, "diameter": 6},),
        )
        == 1
    )
    artifacts = writer.finalize()

    assert len(artifacts) == 1
    assert artifacts[0].kind is ArtifactKind.STAGING
    assert artifacts[0].path == "run-1/staging/utility-lines.csv"
    assert artifacts[0].verify((tmp_path / artifacts[0].path).read_bytes())
    assert (tmp_path / artifacts[0].path).read_text(encoding="utf-8") == (
        "asset_id,active,diameter\nA-1,true,4\nA-2,false,6\n"
    )


def test_staging_writer_rejects_existing_run_directory(tmp_path: Path) -> None:
    (tmp_path / "run-1").mkdir()

    with pytest.raises(StagingError) as raised:
        CsvStagingWriter(tmp_path).initialize(RunId("run-1"))

    assert raised.value.code == "staging.run-exists"


def test_staging_writer_rejects_schema_drift(tmp_path: Path) -> None:
    writer = CsvStagingWriter(tmp_path)
    writer.initialize(RunId("run-1"))
    writer.write_batch(DatasetId("lines"), ({"asset_id": "A-1"},))

    with pytest.raises(StagingError) as raised:
        writer.write_batch(DatasetId("lines"), ({"other_id": "A-2"},))

    assert raised.value.code == "staging.schema-drift"


def test_staging_writer_abort_records_safe_reason(tmp_path: Path) -> None:
    writer = CsvStagingWriter(tmp_path)
    writer.initialize(RunId("run-1"))

    writer.abort("validation rejected")

    marker = json.loads((tmp_path / "run-1" / "ABORTED.json").read_text())
    assert marker == {"reason": "validation rejected", "status": "aborted"}
    with pytest.raises(StagingError):
        writer.write_batch(DatasetId("lines"), ({"id": 1},))


def test_staging_writer_requires_initialization(tmp_path: Path) -> None:
    writer = CsvStagingWriter(tmp_path)

    with pytest.raises(StagingError) as raised:
        writer.finalize()

    assert raised.value.code == "staging.not-initialized"
