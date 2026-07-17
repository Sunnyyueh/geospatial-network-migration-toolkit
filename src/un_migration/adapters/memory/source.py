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
from un_migration.filters.ast import (
    And,
    Compare,
    Expression,
    InList,
    IsNull,
    Not,
    Or,
)
from un_migration.filters.evaluate import evaluate
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
            operations=frozenset({"inventory", "count", "read", "filter"}),
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

    def _records(
        self,
        dataset_id: DatasetId,
        filter_expression: object | None,
    ) -> tuple[Record, ...]:
        records = self._get(dataset_id).records
        if filter_expression is None:
            return records
        if not isinstance(
            filter_expression,
            (Compare, InList, IsNull, Not, And, Or),
        ):
            raise CapabilityError(
                code="adapter.filter-unsupported",
                message="Memory source received an unsupported filter object.",
                guidance="Parse filter text into the toolkit filter AST first.",
            )
        expression: Expression = filter_expression
        return tuple(record for record in records if evaluate(expression, record))

    def inventory(self, dataset: DatasetRef) -> DatasetInventory:
        return self._get(dataset.id).inventory

    def count(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
    ) -> int:
        return len(self._records(dataset.id, filter_expression))

    def read_batches(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
        batch_size: int,
    ) -> Iterator[RecordBatch]:
        if batch_size <= 0:
            raise ConfigurationError(
                code="runtime.batch-size",
                message="Batch size must be positive.",
                guidance="Set runtime.batch_size to a value of at least 1.",
            )
        records = self._records(dataset.id, filter_expression)
        for offset in range(0, len(records), batch_size):
            yield records[offset : offset + batch_size]
