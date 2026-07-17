from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from un_migration.domain.errors import (
    CapabilityError,
    ConfigurationError,
    ErrorContext,
    InventoryError,
)
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import DatasetInventory, DatasetRef
from un_migration.ports.source import (
    AdapterCapabilities,
    Record,
    RecordBatch,
)


@dataclass(frozen=True, slots=True)
class MemoryDataset:
    """Inventory and records supplied to an in-memory source."""

    inventory: DatasetInventory
    records: tuple[Record, ...]

    def __post_init__(self) -> None:
        if self.inventory.feature_count != len(self.records):
            raise ValueError("memory record count must match inventory")


class MemorySourceReader:
    """Deterministic SourceReader for tests, examples, and embedded use."""

    def __init__(
        self,
        datasets: Mapping[DatasetId, MemoryDataset],
    ) -> None:
        self._datasets = {
            key: MemoryDataset(
                value.inventory,
                tuple(MappingProxyType(dict(record)) for record in value.records),
            )
            for key, value in datasets.items()
        }

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_name="memory",
            operations=frozenset({"inventory", "count", "read"}),
        )

    def _get(self, dataset_id: DatasetId) -> MemoryDataset:
        try:
            return self._datasets[dataset_id]
        except KeyError as error:
            raise InventoryError(
                code="memory.dataset-not-found",
                message=f"Memory dataset is not registered: {dataset_id}",
                guidance="Register the dataset before reading it.",
                context=ErrorContext(dataset_id=str(dataset_id)),
            ) from error

    @staticmethod
    def _require_no_filter(filter_expression: object | None) -> None:
        if filter_expression is not None:
            raise CapabilityError(
                code="adapter.filter-unsupported",
                message="Memory source filters require the filter AST.",
                guidance="Remove the filter until filter support is configured.",
            )

    def inventory(self, dataset: DatasetRef) -> DatasetInventory:
        return self._get(dataset.id).inventory

    def count(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
    ) -> int:
        self._require_no_filter(filter_expression)
        return len(self._get(dataset.id).records)

    def read_batches(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
        batch_size: int,
    ) -> Iterator[RecordBatch]:
        self._require_no_filter(filter_expression)
        if batch_size <= 0:
            raise ConfigurationError(
                code="runtime.batch-size",
                message="Batch size must be positive.",
                guidance="Set runtime.batch_size to a value of at least 1.",
            )
        records = self._get(dataset.id).records
        for offset in range(0, len(records), batch_size):
            yield records[offset : offset + batch_size]
