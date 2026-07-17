from datetime import date
from pathlib import Path

import pytest

from tests.contract.source_contract import assert_source_reader_contract
from un_migration.adapters.filesystem.csv_source import CsvSourceReader
from un_migration.config.models import DatasetConfig
from un_migration.domain.errors import (
    CapabilityError,
    ConfigurationError,
    InventoryError,
)
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import DatasetRef, FieldType


def build_reader(
    tmp_path: Path,
    content: str,
    *,
    filename: str = "water_mains.csv",
) -> tuple[CsvSourceReader, DatasetRef]:
    (tmp_path / filename).write_text(content, encoding="utf-8")
    config = DatasetConfig(id="water-mains", path=Path(filename))
    reader = CsvSourceReader(tmp_path, (config,))
    return reader, DatasetRef(DatasetId("water-mains"), filename)


def test_csv_reader_infers_schema_and_streams_typed_batches(
    tmp_path: Path,
) -> None:
    reader, dataset = build_reader(
        tmp_path,
        (
            "asset_id,diameter,active,installed_on,note\n"
            "WM-001,12,true,2020-01-02,\n"
            "WM-002,8,false,2021-03-04,review\n"
            "WM-003,6,true,2022-05-06,ok\n"
        ),
    )

    inventory = reader.inventory(dataset)

    assert inventory.feature_count == 3
    assert [field.name for field in inventory.fields] == [
        "asset_id",
        "diameter",
        "active",
        "installed_on",
        "note",
    ]
    assert [field.type for field in inventory.fields] == [
        FieldType.STRING,
        FieldType.INTEGER,
        FieldType.BOOLEAN,
        FieldType.DATE,
        FieldType.STRING,
    ]
    assert inventory.field("note").nullable is True  # type: ignore[union-attr]

    batches = tuple(reader.read_batches(dataset, None, batch_size=2))
    assert [len(batch) for batch in batches] == [2, 1]
    assert batches[0][0]["diameter"] == 12
    assert batches[0][0]["active"] is True
    assert batches[0][0]["installed_on"] == date(2020, 1, 2)
    assert batches[0][0]["note"] is None


def test_csv_reader_satisfies_source_contract(tmp_path: Path) -> None:
    reader, dataset = build_reader(
        tmp_path,
        "asset_id\nWM-001\nWM-002\nWM-003\n",
    )

    assert_source_reader_contract(reader, dataset)


def test_header_only_csv_is_valid_empty_dataset(tmp_path: Path) -> None:
    reader, dataset = build_reader(tmp_path, "asset_id,diameter\n")

    inventory = reader.inventory(dataset)

    assert inventory.feature_count == 0
    assert all(field.nullable for field in inventory.fields)
    assert tuple(reader.read_batches(dataset, None, batch_size=10)) == ()


def test_utf8_bom_is_removed_from_first_header(tmp_path: Path) -> None:
    reader, dataset = build_reader(tmp_path, "\ufeffasset_id\nWM-001\n")

    assert reader.inventory(dataset).fields[0].name == "asset_id"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("asset_id,ASSET_ID\n1,2\n", "csv.header"),
        ("asset_id,diameter\nWM-001\n", "csv.row-width"),
        ("", "csv.header"),
    ],
)
def test_invalid_csv_uses_stable_inventory_error(
    tmp_path: Path,
    content: str,
    code: str,
) -> None:
    reader, dataset = build_reader(tmp_path, content)

    with pytest.raises(InventoryError) as raised:
        reader.inventory(dataset)

    assert raised.value.code == code


def test_missing_csv_uses_not_found_error(tmp_path: Path) -> None:
    config = DatasetConfig(id="water-mains", path=Path("missing.csv"))
    reader = CsvSourceReader(tmp_path, (config,))
    dataset = DatasetRef(DatasetId("water-mains"), "missing.csv")

    with pytest.raises(InventoryError) as raised:
        reader.inventory(dataset)

    assert raised.value.code == "csv.not-found"


def test_csv_reader_rejects_filters_and_invalid_batch_size(
    tmp_path: Path,
) -> None:
    reader, dataset = build_reader(tmp_path, "asset_id\nWM-001\n")

    with pytest.raises(CapabilityError):
        reader.count(dataset, object())
    with pytest.raises(ConfigurationError):
        tuple(reader.read_batches(dataset, None, batch_size=0))
