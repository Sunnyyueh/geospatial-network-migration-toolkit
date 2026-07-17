from decimal import Decimal

import pytest

from un_migration.domain.errors import FilterSyntaxError
from un_migration.filters.evaluate import evaluate
from un_migration.filters.parser import parse_filter


@pytest.mark.parametrize(
    ("text", "record", "expected"),
    [
        ("diameter = 6", {"diameter": 6}, True),
        ("diameter != 6", {"diameter": 4}, True),
        ("diameter < 6", {"diameter": 4}, True),
        ("diameter <= 6", {"diameter": 6}, True),
        ("diameter > 6", {"diameter": 4}, False),
        ("diameter >= 6", {"diameter": 6}, True),
    ],
)
def test_evaluate_comparison_operators(
    text: str,
    record: dict[str, object],
    expected: bool,
) -> None:
    assert evaluate(parse_filter(text), record) is expected


@pytest.mark.parametrize(
    ("text", "value", "expected"),
    [
        ("retired IS NULL", None, True),
        ("retired IS NOT NULL", None, False),
        ("retired = NULL", None, True),
        ("retired != NULL", "2024", True),
        ("retired > '2020'", None, False),
    ],
)
def test_evaluate_null_semantics(text: str, value: object, expected: bool) -> None:
    assert evaluate(parse_filter(text), {"retired": value}) is expected


def test_evaluate_in_not_in_and_boolean_precedence() -> None:
    record = {"material": "PVC", "diameter": 4, "active": False}

    assert evaluate(
        parse_filter(
            "material IN ('PVC', 'DI') AND diameter NOT IN (2, 3) OR active = true"
        ),
        record,
    )
    assert not evaluate(
        parse_filter("NOT (material = 'PVC' OR diameter = 4)"),
        record,
    )


def test_evaluate_resolves_fields_case_insensitively() -> None:
    assert evaluate(parse_filter("asset_id = 'WM-001'"), {"ASSET_ID": "WM-001"})


def test_evaluate_missing_record_field_uses_stable_error() -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        evaluate(parse_filter("asset_id = 'WM-001'"), {})

    assert raised.value.code == "filter.field-missing"


def test_evaluate_resolves_named_parameters() -> None:
    expression = parse_filter("diameter >= :minimum AND diameter <= :maximum")

    assert evaluate(expression, {"diameter": 6}, {"minimum": 4, "maximum": 8})


def test_evaluate_missing_parameter_uses_stable_error() -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        evaluate(parse_filter("diameter >= :minimum"), {"diameter": 6})

    assert raised.value.code == "filter.parameter-missing"


def test_evaluate_incomparable_values_use_stable_error() -> None:
    with pytest.raises(FilterSyntaxError) as raised:
        evaluate(
            parse_filter("diameter > 1.5"),
            {"diameter": "large"},
        )

    assert raised.value.code == "filter.incomparable"


def test_evaluate_handles_decimal_record_values() -> None:
    assert evaluate(
        parse_filter("pressure >= 1.25"),
        {"pressure": Decimal("1.250")},
    )
