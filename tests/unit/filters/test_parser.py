from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from un_migration.domain.errors import FilterSyntaxError
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import (
    DatasetInventory,
    DatasetRef,
    FieldSchema,
    FieldType,
)
from un_migration.filters.ast import And, Not, Or, normalize
from un_migration.filters.parser import parse_filter, validate_filter_fields


def source_inventory() -> DatasetInventory:
    return DatasetInventory(
        dataset=DatasetRef(DatasetId("water-mains"), "water_mains"),
        fields=(
            FieldSchema("asset_id", FieldType.STRING),
            FieldSchema("diameter", FieldType.INTEGER),
            FieldSchema("pressure", FieldType.DECIMAL),
            FieldSchema("active", FieldType.BOOLEAN),
            FieldSchema("installed", FieldType.DATE),
            FieldSchema("observed", FieldType.DATETIME),
        ),
        feature_count=2,
    )


@pytest.mark.parametrize(
    ("operator", "normalized"),
    [
        ("=", "="),
        ("!=", "!="),
        ("<>", "!="),
        ("<", "<"),
        ("<=", "<="),
        (">", ">"),
        (">=", ">="),
    ],
)
def test_parse_comparison_operators(operator: str, normalized: str) -> None:
    expression = parse_filter(f"diameter {operator} :limit")

    assert normalize(expression) == f"diameter {normalized} :limit"


def test_parser_preserves_not_and_or_precedence() -> None:
    expression = parse_filter(
        "NOT active = false AND diameter >= 4 OR pressure < 12.50"
    )

    assert isinstance(expression, Or)
    assert isinstance(expression.expressions[0], And)
    first_and = expression.expressions[0]
    assert isinstance(first_and.expressions[0], Not)
    assert normalize(expression) == (
        "NOT (active = FALSE) AND diameter >= 4 OR pressure < 12.50"
    )


def test_parentheses_override_precedence() -> None:
    expression = parse_filter("active = true AND (diameter = 4 OR diameter = 6)")

    assert normalize(expression) == ("active = TRUE AND (diameter = 4 OR diameter = 6)")


@pytest.mark.parametrize(
    ("text", "normalized"),
    [
        ("diameter IN (4, 6, :size)", "diameter IN (4, 6, :size)"),
        ("diameter NOT IN (4, 6)", "diameter NOT IN (4, 6)"),
        ("installed IS NULL", "installed IS NULL"),
        ("installed IS NOT NULL", "installed IS NOT NULL"),
    ],
)
def test_parse_collection_and_null_predicates(text: str, normalized: str) -> None:
    assert normalize(parse_filter(text)) == normalized


def test_parse_string_numeric_boolean_and_null_literals() -> None:
    expression = parse_filter(
        "asset_id = 'O''Brien' OR pressure = -12.50 OR active = true OR asset_id = null"
    )

    assert normalize(expression) == (
        "asset_id = 'O''Brien' OR pressure = -12.50 OR active = TRUE OR asset_id = NULL"
    )


def test_parse_date_and_timestamp_literals() -> None:
    expression = parse_filter(
        "installed >= DATE '2024-01-02' AND observed < TIMESTAMP '2024-01-03T12:30:00Z'"
    )

    assert normalize(expression) == (
        "installed >= DATE '2024-01-02' AND observed < TIMESTAMP '2024-01-03T12:30:00Z'"
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "diameter == 4",
        "diameter IN ()",
        "diameter = @value",
        "asset_id = 'unterminated",
        "(diameter = 4",
        "diameter NOT BETWEEN 1 AND 2",
        "diameter =",
    ],
)
def test_invalid_syntax_uses_positioned_stable_error(text: str) -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        parse_filter(text)

    assert raised.value.code == "filter.syntax"
    assert "position" in raised.value.message


def test_validate_filter_accepts_compatible_fields_and_literals() -> None:
    expression = parse_filter(
        "asset_id = 'A-1' AND diameter >= 4 AND pressure < 12.5 "
        "AND active = true AND installed >= DATE '2024-01-01' "
        "AND observed < TIMESTAMP '2025-01-01T00:00:00Z'"
    )

    validate_filter_fields(expression, source_inventory())


def test_validate_filter_rejects_unknown_field() -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        validate_filter_fields(parse_filter("missing = 1"), source_inventory())

    assert raised.value.code == "filter.unknown-field"


@pytest.mark.parametrize(
    "text",
    [
        "diameter = 'large'",
        "active = 1",
        "installed = TIMESTAMP '2024-01-01T00:00:00Z'",
        "observed = DATE '2024-01-01'",
        "diameter IN (1, 'two')",
    ],
)
def test_validate_filter_rejects_incompatible_literal_type(text: str) -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        validate_filter_fields(parse_filter(text), source_inventory())

    assert raised.value.code == "filter.type"


def test_parsed_literal_values_have_portable_python_types() -> None:
    expression = parse_filter(
        "installed = DATE '2024-01-01' AND "
        "observed = TIMESTAMP '2024-01-02T03:04:05Z' AND pressure = 1.25"
    )
    assert isinstance(expression, And)
    values = [item.right.value for item in expression.expressions]  # type: ignore[union-attr]

    assert values == [
        date(2024, 1, 1),
        datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
        Decimal("1.25"),
    ]
