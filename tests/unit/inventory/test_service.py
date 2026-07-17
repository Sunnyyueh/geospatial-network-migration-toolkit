from dataclasses import replace
from types import MappingProxyType

from un_migration.adapters.memory import MemoryDataset, MemorySourceReader
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import (
    DatasetInventory,
    DatasetRef,
    FieldSchema,
    FieldType,
)
from un_migration.inventory.service import (
    InventoryService,
    compare_inventories,
)


def inventory(
    dataset_id: str,
    *,
    count: int = 1,
    fields: tuple[FieldSchema, ...] | None = None,
) -> DatasetInventory:
    dataset = DatasetRef(DatasetId(dataset_id), dataset_id)
    return DatasetInventory(
        dataset=dataset,
        fields=fields or (FieldSchema("asset_id", FieldType.STRING, nullable=False),),
        feature_count=count,
    )


def test_collect_preserves_order_and_fingerprints_each_inventory() -> None:
    first = inventory("water-mains")
    second = inventory("water-devices", count=0)
    reader = MemorySourceReader(
        {
            first.dataset.id: MemoryDataset(
                first,
                ({"asset_id": "WM-001"},),
            ),
            second.dataset.id: MemoryDataset(second, ()),
        }
    )

    result = InventoryService(reader).collect((second.dataset, first.dataset))

    assert result.adapter.adapter_name == "memory"
    assert [item.dataset.id for item in result.inventories] == [
        second.dataset.id,
        first.dataset.id,
    ]
    assert set(result.fingerprints) == {
        first.dataset.id,
        second.dataset.id,
    }
    assert isinstance(result.fingerprints, MappingProxyType)


def test_compare_inventories_reports_schema_and_count_changes() -> None:
    before = inventory(
        "water-mains",
        count=2,
        fields=(
            FieldSchema("asset_id", FieldType.STRING, nullable=False),
            FieldSchema("old_field", FieldType.INTEGER),
            FieldSchema("diameter", FieldType.INTEGER),
        ),
    )
    after = replace(
        before,
        fields=(
            FieldSchema("asset_id", FieldType.STRING, nullable=False),
            FieldSchema("new_field", FieldType.STRING),
            FieldSchema("diameter", FieldType.FLOAT),
        ),
        feature_count=5,
    )

    comparison = compare_inventories(before, after)

    assert comparison.added_fields == ("new_field",)
    assert comparison.removed_fields == ("old_field",)
    assert comparison.changed_fields == ("diameter",)
    assert comparison.feature_count_delta == 3
    assert not comparison.unchanged


def test_compare_identical_inventory_is_unchanged() -> None:
    value = inventory("water-mains")

    assert compare_inventories(value, value).unchanged
