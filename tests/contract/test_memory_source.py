from types import MappingProxyType

import pytest

from tests.contract.source_contract import assert_source_reader_contract
from un_migration.adapters.memory.source import (
    MemoryDataset,
    MemorySourceReader,
)
from un_migration.domain.errors import (
    CapabilityError,
    ConfigurationError,
    InventoryError,
)
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import (
    DatasetInventory,
    DatasetRef,
    FieldSchema,
    FieldType,
)


def build_reader() -> tuple[MemorySourceReader, DatasetRef, dict[str, object]]:
    dataset = DatasetRef(DatasetId("water-mains"), "WaterMains")
    inventory = DatasetInventory(
        dataset=dataset,
        fields=(FieldSchema("asset_id", FieldType.STRING, nullable=False),),
        feature_count=3,
    )
    first: dict[str, object] = {"asset_id": "WM-001"}
    reader = MemorySourceReader(
        {
            dataset.id: MemoryDataset(
                inventory,
                (
                    first,
                    {"asset_id": "WM-002"},
                    {"asset_id": "WM-003"},
                ),
            )
        }
    )
    return reader, dataset, first


def test_memory_reader_satisfies_source_contract() -> None:
    reader, dataset, _ = build_reader()

    assert_source_reader_contract(reader, dataset)


def test_memory_reader_defensively_copies_records() -> None:
    reader, dataset, original = build_reader()
    original["asset_id"] = "changed"

    batch = next(reader.read_batches(dataset, None, batch_size=1))

    assert batch[0]["asset_id"] == "WM-001"
    assert isinstance(batch[0], MappingProxyType)
    with pytest.raises(TypeError):
        batch[0]["asset_id"] = "mutated"  # type: ignore[index]


def test_memory_reader_rejects_unknown_dataset() -> None:
    reader, _, _ = build_reader()
    missing = DatasetRef(DatasetId("missing"), "Missing")

    with pytest.raises(InventoryError) as raised:
        reader.inventory(missing)

    assert raised.value.code == "memory.dataset-not-found"


def test_memory_reader_rejects_nonpositive_batch_size() -> None:
    reader, dataset, _ = build_reader()

    with pytest.raises(ConfigurationError) as raised:
        tuple(reader.read_batches(dataset, None, batch_size=0))

    assert raised.value.code == "runtime.batch-size"


def test_memory_reader_rejects_filter_before_filter_ast_is_available() -> None:
    reader, dataset, _ = build_reader()

    with pytest.raises(CapabilityError) as raised:
        reader.count(dataset, object())

    assert raised.value.code == "adapter.filter-unsupported"
