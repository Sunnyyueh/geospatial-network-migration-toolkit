from types import MappingProxyType

import pytest

from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import FieldType
from un_migration.mapping.models import (
    DatasetMapping,
    FieldMapping,
    NullPolicy,
    ReferenceTable,
    TransformSpec,
)


def field_mapping(**overrides: object) -> FieldMapping:
    values: dict[str, object] = {
        "source_field": " asset_id ",
        "target_field": "asset_identifier",
        "target_type": FieldType.STRING,
    }
    values.update(overrides)
    return FieldMapping(**values)  # type: ignore[arg-type]


def dataset_mapping(*fields: FieldMapping) -> DatasetMapping:
    return DatasetMapping(
        source_dataset=DatasetId("Water Mains"),
        target_dataset=DatasetId("Utility Network Lines"),
        fields=fields or (field_mapping(),),
    )


def test_field_mapping_normalizes_surrounding_whitespace() -> None:
    mapping = field_mapping(source_field=" asset_id ", target_field=" asset_key ")

    assert mapping.source_field == "asset_id"
    assert mapping.target_field == "asset_key"


def test_transform_parameters_are_frozen_and_copied() -> None:
    parameters: dict[str, object] = {"to": "integer"}
    transform = TransformSpec(name="cast", parameters=parameters)
    parameters["to"] = "string"

    assert isinstance(transform.parameters, MappingProxyType)
    assert transform.parameters == {"to": "integer"}
    with pytest.raises(TypeError):
        transform.parameters["to"] = "decimal"  # type: ignore[index]


@pytest.mark.parametrize("name", ["", " ", "Trim Value", "../lookup"])
def test_transform_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValueError, match="transformation name"):
        TransformSpec(name=name)


@pytest.mark.parametrize("attribute", ["source_field", "target_field"])
@pytest.mark.parametrize("value", ["", " ", "9field", "field-name"])
def test_field_mapping_rejects_invalid_identifiers(attribute: str, value: str) -> None:
    with pytest.raises(ValueError, match=attribute):
        field_mapping(**{attribute: value})


def test_required_field_cannot_allow_null() -> None:
    with pytest.raises(ValueError, match="required field"):
        field_mapping(required=True, null_policy=NullPolicy.ALLOW)


def test_default_policy_requires_a_default_value() -> None:
    with pytest.raises(ValueError, match="default value"):
        field_mapping(null_policy=NullPolicy.DEFAULT)


def test_dataset_mapping_rejects_duplicate_target_fields_case_insensitively() -> None:
    with pytest.raises(ValueError, match="duplicate target field"):
        dataset_mapping(
            field_mapping(source_field="asset_id", target_field="asset_key"),
            field_mapping(source_field="legacy_id", target_field="ASSET_KEY"),
        )


def test_reference_table_requires_schema_version_one() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        ReferenceTable(schema_version=2, datasets=(dataset_mapping(),))  # type: ignore[arg-type]


def test_reference_table_rejects_duplicate_source_datasets() -> None:
    first = dataset_mapping()
    second = DatasetMapping(
        source_dataset=DatasetId("water_mains"),
        target_dataset=DatasetId("alternate-lines"),
        fields=(field_mapping(),),
    )

    with pytest.raises(ValueError, match="duplicate source dataset"):
        ReferenceTable(schema_version=1, datasets=(first, second))


def test_mapping_models_normalize_dataset_identifiers() -> None:
    table = ReferenceTable(schema_version=1, datasets=(dataset_mapping(),))

    assert table.datasets[0].source_dataset == "water-mains"
    assert table.datasets[0].target_dataset == "utility-network-lines"
