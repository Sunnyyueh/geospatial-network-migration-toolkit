from typing import Protocol, runtime_checkable

from un_migration.domain.artifacts import Artifact
from un_migration.domain.identity import DatasetId, RunId
from un_migration.ports.source import AdapterCapabilities, RecordBatch


@runtime_checkable
class StagingWriter(Protocol):
    """Write transformed records to an isolated staging target."""

    def capabilities(self) -> AdapterCapabilities: ...

    def initialize(self, run_id: RunId) -> None: ...

    def write_batch(
        self,
        dataset_id: DatasetId,
        records: RecordBatch,
    ) -> int: ...

    def finalize(self) -> tuple[Artifact, ...]: ...

    def abort(self, reason: str) -> None: ...
