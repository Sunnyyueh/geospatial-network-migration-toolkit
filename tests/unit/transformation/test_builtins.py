from datetime import UTC, date, datetime
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

import pytest

from un_migration.domain.errors import TransformationError
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import FieldType
from un_migration.mapping.models import (
    DatasetMapping,
    FieldMapping,
    NullPolicy,
    TransformSpec,
)
from un_migration.transformation.builtins import (
    default_registry,
    transform_record,
)


def apply(name: str, source_value: object, **parameters: object) -> object:
    return default_registry().apply(TransformSpec(name, parameters), source_value)


def mapped_field(
    source: str,
    target: str,
    target_type: FieldType,
    *,
    transform: str = "identity",
    parameters: dict[str, object] | None = None,
    null_policy: NullPolicy = NullPolicy.ALLOW,
    default: object | None = None,
    required: bool = False,
) -> FieldMapping:
    return FieldMapping(
        source,
        target,
        target_type,
        required=required,
        null_policy=null_policy,
        default=default,
        transform=TransformSpec(transform, parameters or {}),
    )


def dataset_mapping(*fields: FieldMapping) -> DatasetMapping:
    return DatasetMapping(
        DatasetId("water-mains"),
        DatasetId("utility-lines"),
        fields,
    )


def test_identity_returns_the_same_value() -> None:
    marker = object()
    assert apply("identity", marker) is marker


@pytest.mark.parametrize(
    ("value", "target", "expected"),
    [
        (12, "string", "12"),
        ("12", "integer", 12),
        ("12.5", "float", 12.5),
        ("12.500", "decimal", Decimal("12.500")),
        ("yes", "boolean", True),
        ("2024-01-02", "date", date(2024, 1, 2)),
        (
            "2024-01-02T03:04:05Z",
            "datetime",
            datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
        ),
        (
            "550e8400-e29b-41d4-a716-446655440000",
            "uuid",
            "550e8400-e29b-41d4-a716-446655440000",
        ),
        ('{"active":true}', "json", {"active": True}),
    ],
)
def test_cast_supports_portable_scalar_types(
    value: object,
    target: str,
    expected: object,
) -> None:
    assert apply("cast", value, to=target) == expected


def test_trim_and_case_transforms_are_deterministic() -> None:
    assert apply("trim", "  Water   Main  ", collapse=True) == "Water Main"
    assert apply("uppercase", "pvc") == "PVC"
    assert apply("lowercase", "Active") == "active"


def test_parse_date_accepts_explicit_format() -> None:
    assert apply("parse_date", "07/16/2026", format="%m/%d/%Y") == date(2026, 7, 16)


def test_constant_and_conditional_default_transforms() -> None:
    assert apply("constant", "ignored", value="network") == "network"
    assert apply("default", None, value="unknown") == "unknown"
    assert apply("default", "", value="unknown", empty=True) == "unknown"
    assert apply("default", "", value="unknown") == ""


def test_lookup_supports_hit_and_explicit_miss_policies() -> None:
    values = {"CI": "CAST_IRON", "DI": "DUCTILE_IRON"}

    assert apply("lookup", "CI", values=values) == "CAST_IRON"
    assert apply("lookup", "PVC", values=values, on_missing="keep") == "PVC"
    assert apply("lookup", "PVC", values=values, on_missing="null") is None
    with pytest.raises(TransformationError) as raised:
        apply("lookup", "PVC", values=values, on_missing="error")
    assert raised.value.code == "transform.lookup-missing"


def test_concatenate_and_coalesce_values() -> None:
    assert (
        apply(
            "concatenate",
            "WM-001",
            parts=["north", "$value", "active"],
            separator="-",
        )
        == "north-WM-001-active"
    )
    assert apply("coalesce", None, values=[None, "", "fallback"]) == "fallback"
    assert apply("coalesce", "present", values=["fallback"]) == "present"


def test_transform_record_projects_values_without_mutating_input() -> None:
    source = {"asset_id": "wm-001", "diameter": "12", "ignored": "source"}
    mapping = dataset_mapping(
        mapped_field(
            "asset_id", "asset_identifier", FieldType.STRING, transform="uppercase"
        ),
        mapped_field("diameter", "diameter_mm", FieldType.INTEGER),
    )

    result = transform_record(source, mapping, default_registry())

    assert result.record == {"asset_identifier": "WM-001", "diameter_mm": 12}
    assert isinstance(result.record, MappingProxyType)
    assert source == {
        "asset_id": "wm-001",
        "diameter": "12",
        "ignored": "source",
    }
    assert result.findings.failed() == ()


def test_transform_record_applies_default_and_reports_rejected_null() -> None:
    mapping = dataset_mapping(
        mapped_field(
            "material",
            "material",
            FieldType.STRING,
            null_policy=NullPolicy.DEFAULT,
            default="UNKNOWN",
        ),
        mapped_field(
            "asset_id",
            "asset_identifier",
            FieldType.STRING,
            null_policy=NullPolicy.REJECT,
            required=True,
        ),
    )

    result = transform_record(
        {"material": None, "asset_id": None},
        mapping,
        default_registry(),
        record_id="row-1",
    )

    assert result.record == {"material": "UNKNOWN", "asset_identifier": None}
    finding = result.findings.failed()[0]
    assert finding.rule_id == "transform.null"
    assert finding.evidence is not None
    assert finding.evidence.record_id == "row-1"


def test_transform_record_error_has_dataset_context() -> None:
    mapping = dataset_mapping(
        mapped_field("diameter", "diameter_mm", FieldType.INTEGER)
    )

    with pytest.raises(TransformationError) as raised:
        transform_record({"diameter": "large"}, mapping, default_registry())

    assert raised.value.code == "transform.cast"
    assert raised.value.context.dataset_id == "water-mains"


def test_transform_record_rejects_missing_source_field() -> None:
    mapping = dataset_mapping(
        mapped_field("asset_id", "asset_identifier", FieldType.STRING)
    )

    with pytest.raises(TransformationError) as raised:
        transform_record({}, mapping, default_registry())

    assert raised.value.code == "transform.source-field"


def test_uuid_cast_returns_canonical_text() -> None:
    value = UUID("550E8400-E29B-41D4-A716-446655440000")

    assert apply("cast", value, to="uuid") == str(value)
