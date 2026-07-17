from collections.abc import Iterator

from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import DatasetInventory, DatasetRef
from un_migration.ports.source import (
    AdapterCapabilities,
    RecordBatch,
    SourceReader,
)


class IncompleteSource:
    pass


class CompleteSource:
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_name="complete",
            operations=frozenset({"inventory", "read"}),
        )

    def inventory(self, dataset: DatasetRef) -> DatasetInventory:
        return DatasetInventory(dataset=dataset, fields=(), feature_count=0)

    def count(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
    ) -> int:
        return 0

    def read_batches(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
        batch_size: int,
    ) -> Iterator[RecordBatch]:
        yield ()


def test_source_protocol_rejects_incomplete_adapter() -> None:
    assert not isinstance(IncompleteSource(), SourceReader)


def test_source_protocol_accepts_complete_adapter() -> None:
    assert isinstance(CompleteSource(), SourceReader)


def test_adapter_capabilities_are_explicit() -> None:
    capabilities = CompleteSource().capabilities()

    assert capabilities.supports("inventory")
    assert not capabilities.supports("deploy")
    assert capabilities.adapter_name == "complete"


def test_complete_source_returns_portable_inventory() -> None:
    dataset = DatasetRef(DatasetId("water-mains"), "WaterMains")

    assert CompleteSource().inventory(dataset).dataset is dataset
