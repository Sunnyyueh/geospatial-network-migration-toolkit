import pytest

from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import (
    CodedDomain,
    DatasetInventory,
    DatasetRef,
    DomainValue,
    FieldSchema,
    FieldType,
    GeometrySchema,
    GeometryType,
)


def test_inventory_finds_fields_case_insensitively() -> None:
    asset_id = FieldSchema(
        name="asset_id",
        type=FieldType.STRING,
        nullable=False,
        length=64,
    )
    inventory = DatasetInventory(
        dataset=DatasetRef(DatasetId("water-mains"), "WaterMains"),
        fields=(asset_id,),
        feature_count=2,
        geometry=GeometrySchema(
            type=GeometryType.POLYLINE,
            spatial_reference="EPSG:26985",
        ),
    )

    assert inventory.field("ASSET_ID") is asset_id
    assert inventory.field("missing") is None


def test_inventory_rejects_duplicate_field_names() -> None:
    field = FieldSchema(name="asset_id", type=FieldType.STRING, nullable=False)
    duplicate = FieldSchema(name="ASSET_ID", type=FieldType.STRING)

    with pytest.raises(ValueError, match="duplicate field"):
        DatasetInventory(
            dataset=DatasetRef(DatasetId("water-mains"), "WaterMains"),
            fields=(field, duplicate),
            feature_count=2,
        )


def test_inventory_rejects_negative_feature_count() -> None:
    with pytest.raises(ValueError, match="feature_count"):
        DatasetInventory(
            dataset=DatasetRef(DatasetId("water-mains"), "WaterMains"),
            fields=(),
            feature_count=-1,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "type": FieldType.STRING},
        {"name": "material", "type": FieldType.STRING, "length": -1},
        {
            "name": "diameter",
            "type": FieldType.DECIMAL,
            "precision": 4,
            "scale": 5,
        },
    ],
)
def test_field_schema_rejects_invalid_constraints(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        FieldSchema(**kwargs)  # type: ignore[arg-type]


def test_coded_domain_rejects_duplicate_codes() -> None:
    with pytest.raises(ValueError, match="duplicate domain code"):
        CodedDomain(
            name="material",
            values=(
                DomainValue(code="PVC", label="PVC"),
                DomainValue(code="PVC", label="Polyvinyl chloride"),
            ),
        )


def test_dataset_reference_requires_physical_name() -> None:
    with pytest.raises(ValueError, match="physical_name"):
        DatasetRef(DatasetId("water-mains"), " ")
