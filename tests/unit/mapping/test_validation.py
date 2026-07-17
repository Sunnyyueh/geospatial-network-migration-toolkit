from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import (
    DatasetInventory,
    DatasetRef,
    FieldSchema,
    FieldType,
)
from un_migration.domain.status import Severity
from un_migration.mapping.models import DatasetMapping, FieldMapping, NullPolicy
from un_migration.mapping.validation import validate_mapping


def inventory(
    dataset_id: str,
    *fields: FieldSchema,
) -> DatasetInventory:
    return DatasetInventory(
        dataset=DatasetRef(DatasetId(dataset_id), dataset_id),
        fields=fields,
        feature_count=10,
    )


def mapping(*fields: FieldMapping) -> DatasetMapping:
    return DatasetMapping(
        source_dataset=DatasetId("water-mains"),
        target_dataset=DatasetId("utility-lines"),
        fields=fields,
    )


def field(
    source: str,
    target: str,
    target_type: FieldType,
    *,
    required: bool = False,
) -> FieldMapping:
    return FieldMapping(
        source_field=source,
        target_field=target,
        target_type=target_type,
        required=required,
        null_policy=NullPolicy.REJECT if required else NullPolicy.ALLOW,
    )


def test_exact_mapping_is_valid() -> None:
    source = inventory(
        "water-mains",
        FieldSchema("asset_id", FieldType.STRING, nullable=False, length=32),
    )
    target = inventory(
        "utility-lines",
        FieldSchema("asset_key", FieldType.STRING, nullable=False, length=32),
    )

    result = validate_mapping(
        mapping(field("asset_id", "asset_key", FieldType.STRING, required=True)),
        source,
        target,
    )

    assert result.valid
    assert tuple(result.findings) == ()


def test_missing_source_field_is_an_error() -> None:
    result = validate_mapping(
        mapping(field("missing", "asset_key", FieldType.STRING)),
        inventory("water-mains"),
    )

    finding = result.findings.failed()[0]
    assert not result.valid
    assert finding.rule_id == "mapping.source-field"
    assert finding.severity is Severity.ERROR
    assert finding.field_name == "missing"


def test_missing_target_field_is_an_error() -> None:
    source = inventory("water-mains", FieldSchema("asset_id", FieldType.STRING))

    result = validate_mapping(
        mapping(field("asset_id", "asset_key", FieldType.STRING)),
        source,
        inventory("utility-lines"),
    )

    assert result.findings.failed()[0].rule_id == "mapping.target-field"


def test_incompatible_source_type_is_an_error() -> None:
    source = inventory("water-mains", FieldSchema("installed", FieldType.DATE))

    result = validate_mapping(
        mapping(field("installed", "install_year", FieldType.INTEGER)),
        source,
    )

    finding = result.findings.failed()[0]
    assert finding.rule_id == "mapping.type"
    assert finding.evidence is not None
    assert finding.evidence.actual == "date"
    assert finding.evidence.expected == "integer"


def test_numeric_widening_is_compatible() -> None:
    source = inventory("water-mains", FieldSchema("diameter", FieldType.INTEGER))

    result = validate_mapping(
        mapping(field("diameter", "diameter", FieldType.DECIMAL)),
        source,
    )

    assert result.valid


def test_string_length_narrowing_is_reported() -> None:
    source = inventory(
        "water-mains",
        FieldSchema("description", FieldType.STRING, length=255),
    )
    target = inventory(
        "utility-lines",
        FieldSchema("description", FieldType.STRING, length=80),
    )

    result = validate_mapping(
        mapping(field("description", "description", FieldType.STRING)),
        source,
        target,
    )

    finding = result.findings.failed()[0]
    assert finding.rule_id == "mapping.length"
    assert finding.severity is Severity.WARNING
    assert finding.evidence is not None
    assert finding.evidence.actual == 255
    assert finding.evidence.expected == 80


def test_nullable_source_to_required_target_is_reported() -> None:
    source = inventory(
        "water-mains", FieldSchema("asset_id", FieldType.STRING, nullable=True)
    )

    result = validate_mapping(
        mapping(field("asset_id", "asset_key", FieldType.STRING, required=True)),
        source,
    )

    finding = result.findings.failed()[0]
    assert finding.rule_id == "mapping.nullability"
    assert finding.severity is Severity.WARNING


def test_findings_follow_declared_field_and_rule_order() -> None:
    source = inventory(
        "water-mains",
        FieldSchema("description", FieldType.STRING, nullable=True, length=255),
    )
    target = inventory(
        "utility-lines",
        FieldSchema("description", FieldType.STRING, nullable=False, length=80),
    )
    candidate = mapping(
        field("missing", "missing_target", FieldType.INTEGER),
        field("description", "description", FieldType.STRING, required=True),
    )

    result = validate_mapping(candidate, source, target)

    assert [finding.rule_id for finding in result.findings] == [
        "mapping.source-field",
        "mapping.target-field",
        "mapping.length",
        "mapping.nullability",
    ]
    assert [str(finding.id) for finding in result.findings] == [
        "mapping-finding-000001",
        "mapping-finding-000002",
        "mapping-finding-000003",
        "mapping-finding-000004",
    ]


def test_target_type_must_match_declared_mapping_type() -> None:
    source = inventory("water-mains", FieldSchema("diameter", FieldType.INTEGER))
    target = inventory("utility-lines", FieldSchema("diameter", FieldType.STRING))

    result = validate_mapping(
        mapping(field("diameter", "diameter", FieldType.INTEGER)),
        source,
        target,
    )

    assert [finding.rule_id for finding in result.findings] == ["mapping.type"]
