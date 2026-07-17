import csv
import io
import json
from pathlib import Path

import pytest

from un_migration.domain.errors import MappingError
from un_migration.domain.schema import FieldType
from un_migration.mapping.models import NullPolicy
from un_migration.mapping.reference import load_reference, normalize_reference

HEADERS = (
    "schema_version",
    "source_dataset",
    "target_dataset",
    "source_field",
    "target_field",
    "target_type",
    "required",
    "null_policy",
    "default",
    "transform",
    "transform_parameters",
)


def valid_rows() -> list[dict[str, str]]:
    return [
        {
            "schema_version": "1",
            "source_dataset": "water-mains",
            "target_dataset": "utility-lines",
            "source_field": "asset_id",
            "target_field": "asset_identifier",
            "target_type": "string",
            "required": "true",
            "null_policy": "reject",
            "default": "",
            "transform": "trim",
            "transform_parameters": '{"collapse":true}',
        },
        {
            "schema_version": "1",
            "source_dataset": "water-mains",
            "target_dataset": "utility-lines",
            "source_field": "diameter",
            "target_field": "diameter_mm",
            "target_type": "integer",
            "required": "false",
            "null_policy": "default",
            "default": "0",
            "transform": "cast",
            "transform_parameters": '{"to":"integer"}',
        },
        {
            "schema_version": "1",
            "source_dataset": "valves",
            "target_dataset": "utility-devices",
            "source_field": "valve_id",
            "target_field": "asset_identifier",
            "target_type": "string",
            "required": "false",
            "null_policy": "allow",
            "default": "",
            "transform": "identity",
            "transform_parameters": "{}",
        },
    ]


def write_reference(
    path: Path,
    rows: list[dict[str, str]],
    headers: tuple[str, ...] = HEADERS,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def error_code(path: Path) -> str:
    with pytest.raises(MappingError) as raised:
        load_reference(path)
    return raised.value.code


def test_load_reference_groups_rows_and_parses_types(tmp_path: Path) -> None:
    path = tmp_path / "reference.csv"
    write_reference(path, valid_rows())

    table = load_reference(path)

    assert table.schema_version == 1
    assert [str(item.source_dataset) for item in table.datasets] == [
        "water-mains",
        "valves",
    ]
    diameter = table.datasets[0].fields[1]
    assert diameter.target_type is FieldType.INTEGER
    assert diameter.null_policy is NullPolicy.DEFAULT
    assert diameter.required is False
    assert diameter.default == "0"
    assert diameter.transform.parameters == {"to": "integer"}


def test_normalization_is_deterministic_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "reference.csv"
    rows = valid_rows()
    rows[0]["transform_parameters"] = '{ "collapse": true }'
    rows[0]["required"] = "TRUE"
    write_reference(path, rows)

    normalized = normalize_reference(load_reference(path))
    parsed = list(csv.DictReader(io.StringIO(normalized), strict=True))

    assert normalized.endswith("\n")
    assert tuple(parsed[0]) == HEADERS
    assert parsed[0]["required"] == "true"
    assert parsed[0]["transform_parameters"] == '{"collapse":true}'
    normalized_path = tmp_path / "normalized.csv"
    normalized_path.write_text(normalized, encoding="utf-8")
    assert normalize_reference(load_reference(normalized_path)) == normalized


def test_missing_reference_uses_stable_error(tmp_path: Path) -> None:
    assert error_code(tmp_path / "missing.csv") == "reference.not-found"


def test_empty_reference_uses_stable_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    assert error_code(path) == "reference.empty"


def test_missing_header_uses_stable_error(tmp_path: Path) -> None:
    path = tmp_path / "reference.csv"
    write_reference(path, valid_rows(), HEADERS[:-1])

    assert error_code(path) == "reference.header"


@pytest.mark.parametrize("version", ["", "2", "latest"])
def test_unsupported_version_uses_stable_error(
    tmp_path: Path,
    version: str,
) -> None:
    path = tmp_path / "reference.csv"
    rows = valid_rows()
    rows[0]["schema_version"] = version
    write_reference(path, rows)

    assert error_code(path) == "reference.version"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("required", "yes"),
        ("target_type", "bigint"),
        ("null_policy", "ignore"),
        ("transform_parameters", "[]"),
        ("transform_parameters", "{broken"),
    ],
)
def test_invalid_row_value_uses_stable_error(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    path = tmp_path / "reference.csv"
    rows = valid_rows()
    rows[0][field] = value
    write_reference(path, rows)

    assert error_code(path) == "reference.row"


def test_duplicate_mapping_row_uses_stable_error(tmp_path: Path) -> None:
    path = tmp_path / "reference.csv"
    rows = valid_rows()
    rows.insert(1, dict(rows[0]))
    write_reference(path, rows)

    assert error_code(path) == "reference.row"


def test_transform_parameters_must_have_string_keys(tmp_path: Path) -> None:
    path = tmp_path / "reference.csv"
    rows = valid_rows()
    rows[0]["transform_parameters"] = json.dumps({1: "value"})
    write_reference(path, rows)

    # JSON object keys are always decoded as strings and therefore safe names.
    assert load_reference(path).datasets[0].fields[0].transform.parameters == {
        "1": "value"
    }
