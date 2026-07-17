from datetime import UTC, date, datetime
from types import MappingProxyType

import pytest

from un_migration.domain.errors import FilterSyntaxError
from un_migration.filters.parser import parse_filter
from un_migration.filters.sql import CompiledSql, SqlDialect, compile_sql


def test_qmark_sql_separates_apostrophe_value_from_text() -> None:
    compiled = compile_sql(
        parse_filter("asset_id = 'O''Brien'"),
        SqlDialect(),
    )

    assert compiled == CompiledSql('"asset_id" = ?', ("O'Brien",))
    assert "O'Brien" not in compiled.text


def test_named_sql_uses_stable_generated_parameters() -> None:
    compiled = compile_sql(
        parse_filter("diameter >= :minimum AND diameter <= :maximum"),
        SqlDialect(placeholder="named"),
        {"maximum": 12, "minimum": 4},
    )

    assert compiled.text == '"diameter" >= :p1 AND "diameter" <= :p2'
    assert compiled.parameters == {"p1": 4, "p2": 12}
    assert isinstance(compiled.parameters, MappingProxyType)


def test_in_list_expands_one_placeholder_per_value() -> None:
    compiled = compile_sql(
        parse_filter("material NOT IN ('PVC', 'DI', :other)"),
        SqlDialect(),
        {"other": "COPPER"},
    )

    assert compiled.text == '"material" NOT IN (?, ?, ?)'
    assert compiled.parameters == ("PVC", "DI", "COPPER")


def test_null_predicates_do_not_allocate_parameters() -> None:
    compiled = compile_sql(
        parse_filter("retired IS NULL OR abandoned IS NOT NULL"),
        SqlDialect(),
    )

    assert compiled.text == '"retired" IS NULL OR "abandoned" IS NOT NULL'
    assert compiled.parameters == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("retired = NULL", '"retired" IS NULL'),
        ("retired != NULL", '"retired" IS NOT NULL'),
    ],
)
def test_null_equality_compiles_to_null_predicate(
    text: str,
    expected: str,
) -> None:
    compiled = compile_sql(parse_filter(text), SqlDialect())

    assert compiled == CompiledSql(expected, ())


def test_date_and_datetime_remain_typed_parameters() -> None:
    compiled = compile_sql(
        parse_filter(
            "installed >= DATE '2024-01-01' AND "
            "observed < TIMESTAMP '2025-01-01T00:00:00Z'"
        ),
        SqlDialect(),
    )

    assert compiled.parameters == (
        date(2024, 1, 1),
        datetime(2025, 1, 1, tzinfo=UTC),
    )


def test_missing_named_parameter_uses_stable_error() -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        compile_sql(parse_filter("diameter >= :minimum"), SqlDialect())

    assert raised.value.code == "filter.parameter-missing"


def test_nested_parentheses_preserve_boolean_precedence() -> None:
    compiled = compile_sql(
        parse_filter("active = true AND (material = 'PVC' OR material = 'DI')"),
        SqlDialect(),
    )

    assert compiled.text == ('"active" = ? AND ("material" = ? OR "material" = ?)')
    assert compiled.parameters == (True, "PVC", "DI")


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ('"', '"assets"."asset_id"'),
        ("`", "`assets`.`asset_id`"),
        ("[", "[assets].[asset_id]"),
    ],
)
def test_dialect_quotes_each_identifier_segment(
    quote: str,
    expected: str,
) -> None:
    compiled = compile_sql(
        parse_filter("assets.asset_id = 'A-1'"),
        SqlDialect(identifier_quote=quote),
    )

    assert compiled.text == f"{expected} = ?"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"identifier_quote": "'"},
        {"identifier_quote": ""},
        {"placeholder": "format"},
    ],
)
def test_dialect_rejects_unsafe_configuration(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        SqlDialect(**kwargs)  # type: ignore[arg-type]
