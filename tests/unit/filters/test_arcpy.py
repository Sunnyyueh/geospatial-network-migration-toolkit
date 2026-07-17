from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from un_migration.domain.errors import FilterSyntaxError
from un_migration.filters.arcpy import compile_arcpy
from un_migration.filters.ast import Compare, CompareOperator, Field, Parameter
from un_migration.filters.parser import parse_filter


def brackets(name: str) -> str:
    return f"[{name}]"


def test_arcpy_compiler_escapes_apostrophes() -> None:
    clause = compile_arcpy(parse_filter("owner = 'O''Brien'"), brackets)

    assert clause == "[owner] = 'O''Brien'"


def test_arcpy_compiler_formats_boolean_date_timestamp_and_decimal() -> None:
    eastern = timezone(timedelta(hours=-5))
    expression = parse_filter(
        "active = :active AND installed >= :installed AND observed < :observed "
        "AND pressure = :pressure"
    )

    clause = compile_arcpy(
        expression,
        brackets,
        {
            "active": True,
            "installed": date(2024, 1, 2),
            "observed": datetime(2024, 1, 2, 8, 30, 45, 123456, tzinfo=eastern),
            "pressure": Decimal("12.500"),
        },
    )

    assert clause == (
        "[active] = 1 AND [installed] >= DATE '2024-01-02' AND "
        "[observed] < TIMESTAMP '2024-01-02T13:30:45Z' AND "
        "[pressure] = 12.500"
    )


def test_arcpy_compiler_handles_in_and_null_predicates() -> None:
    clause = compile_arcpy(
        parse_filter("material IN ('PVC', :other) AND retired IS NOT NULL"),
        brackets,
        {"other": "DI"},
    )

    assert clause == "[material] IN ('PVC', 'DI') AND [retired] IS NOT NULL"


def test_arcpy_compiler_preserves_nested_expression_precedence() -> None:
    clause = compile_arcpy(
        parse_filter("active = true AND (diameter = 4 OR diameter = 6)"),
        brackets,
    )

    assert clause == "[active] = 1 AND ([diameter] = 4 OR [diameter] = 6)"


def test_every_field_is_passed_to_delimiter_callback() -> None:
    calls: list[str] = []

    def recording_delimiter(name: str) -> str:
        calls.append(name)
        return f'"{name}"'

    compile_arcpy(
        parse_filter("assets.asset_id = 'A-1' OR retired IS NULL"),
        recording_delimiter,
    )

    assert calls == ["assets.asset_id", "retired"]


def test_missing_parameter_uses_stable_error() -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        compile_arcpy(parse_filter("diameter >= :minimum"), brackets)

    assert raised.value.code == "filter.parameter-missing"


@pytest.mark.parametrize(
    "value",
    [object(), None, float("nan"), float("inf"), "unsafe\x00value"],
)
def test_unsafe_or_unsupported_parameters_are_rejected(value: object) -> None:
    expression = Compare(Field("value"), CompareOperator.EQUAL, Parameter("value"))

    with pytest.raises(FilterSyntaxError) as raised:
        compile_arcpy(expression, brackets, {"value": value})

    assert raised.value.code == "filter.literal"


def test_empty_field_delimiter_result_is_rejected() -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        compile_arcpy(parse_filter("diameter = 4"), lambda _: "")

    assert raised.value.code == "filter.field-delimiter"
