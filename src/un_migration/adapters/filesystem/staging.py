import csv
from pathlib import Path

from un_migration.adapters.filesystem.artifacts import ManagedArtifactStore
from un_migration.domain.artifacts import Artifact, ArtifactKind
from un_migration.domain.errors import ErrorContext, StagingError
from un_migration.domain.identity import DatasetId, RunId
from un_migration.domain.serialization import canonical_json, to_primitive
from un_migration.ports.source import AdapterCapabilities, RecordBatch


class CsvStagingWriter:
    """Write transformed batches into an isolated, managed CSV run directory."""

    def __init__(self, root: Path) -> None:
        self.store = ManagedArtifactStore(root)
        self._run_id: RunId | None = None
        self._schemas: dict[DatasetId, tuple[str, ...]] = {}
        self._files: set[str] = set()
        self._closed = False

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            "filesystem-csv",
            frozenset({"initialize", "write", "finalize", "abort"}),
        )

    def initialize(self, run_id: RunId) -> None:
        if self._run_id is not None:
            raise self._error("staging.initialized", "Staging writer is initialized.")
        run_path = self.store.root / str(run_id)
        try:
            run_path.mkdir()
        except FileExistsError as error:
            raise self._error(
                "staging.run-exists",
                f"Managed run directory already exists: {run_id}.",
            ) from error
        self._run_id = run_id

    def _error(self, code: str, message: str) -> StagingError:
        return StagingError(
            code=code,
            message=message,
            guidance="Use a new run ID and a consistent transformed record schema.",
            context=ErrorContext(
                run_id=str(self._run_id) if self._run_id is not None else None
            ),
        )

    def _require_open(self) -> RunId:
        if self._run_id is None:
            raise self._error("staging.not-initialized", "Staging is not initialized.")
        if self._closed:
            raise self._error("staging.closed", "Staging is already closed.")
        return self._run_id

    @staticmethod
    def _cell(value: object) -> object:
        primitive = to_primitive(value)
        if primitive is None:
            return ""
        if isinstance(primitive, bool):
            return str(primitive).casefold()
        if isinstance(primitive, list | dict):
            return canonical_json(primitive)
        return primitive

    def write_batch(self, dataset_id: DatasetId, records: RecordBatch) -> int:
        run_id = self._require_open()
        if not records:
            return 0
        schema = tuple(records[0])
        expected = self._schemas.setdefault(dataset_id, schema)
        if not schema or any(tuple(record) != expected for record in records):
            raise self._error(
                "staging.schema-drift",
                f"Transformed schema changed for dataset {dataset_id}.",
            )
        logical = f"{run_id}/staging/{dataset_id}.csv"
        target = self.store.root / logical
        target.parent.mkdir(parents=True, exist_ok=True)
        first_write = logical not in self._files
        try:
            with target.open("a", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=expected,
                    lineterminator="\n",
                )
                if first_write:
                    writer.writeheader()
                for record in records:
                    writer.writerow(
                        {name: self._cell(record[name]) for name in expected}
                    )
        except OSError as error:
            raise self._error(
                "staging.write",
                f"Could not write staging dataset {dataset_id}.",
            ) from error
        self._files.add(logical)
        return len(records)

    def finalize(self) -> tuple[Artifact, ...]:
        self._require_open()
        self._closed = True
        return tuple(
            self.store.register_existing(
                logical,
                "text/csv",
                ArtifactKind.STAGING,
            )
            for logical in sorted(self._files)
        )

    def abort(self, reason: str) -> None:
        run_id = self._require_open()
        self.store.write(
            f"{run_id}/ABORTED.json",
            canonical_json({"reason": reason, "status": "aborted"}).encode("utf-8"),
            "application/json",
        )
        self._closed = True
