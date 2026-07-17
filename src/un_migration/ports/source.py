from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeAlias, runtime_checkable

from un_migration.domain.schema import DatasetInventory, DatasetRef

Record: TypeAlias = Mapping[str, object]
RecordBatch: TypeAlias = tuple[Record, ...]


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """Explicit operations supported by an adapter instance."""

    adapter_name: str
    operations: frozenset[str]

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("adapter_name must not be empty")
        if any(not operation.strip() for operation in self.operations):
            raise ValueError("capability operation must not be empty")

    def supports(self, operation: str) -> bool:
        return operation in self.operations


@runtime_checkable
class SourceReader(Protocol):
    """Read inventory and bounded record batches from a source."""

    def capabilities(self) -> AdapterCapabilities: ...

    def inventory(self, dataset: DatasetRef) -> DatasetInventory: ...

    def count(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
    ) -> int: ...

    def read_batches(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
        batch_size: int,
    ) -> Iterator[RecordBatch]: ...
