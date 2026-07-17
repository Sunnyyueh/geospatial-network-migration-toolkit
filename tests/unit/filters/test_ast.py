from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from un_migration.filters.ast import (
    And,
    Compare,
    CompareOperator,
    Field,
    InList,
    IsNull,
    LiteralValue,
    Not,
    Or,
    Parameter,
    normalize,
)


def equals(field_name: str, value: object) -> Compare:
    return Compare(
        Field(field_name),
        CompareOperator.EQUAL,
        LiteralValue(value),  # type: ignore[arg-type]
    )


def test_nodes_are_frozen() -> None:
    expression = equals("status", "active")

    with pytest.raises(FrozenInstanceError):
        expression.operator = CompareOperator.NOT_EQUAL  # type: ignore[misc]


@pytest.mark.parametrize("name", ["", " ", "9value", "bad-name", "a.b"])
def test_parameter_requires_safe_name(name: str) -> None:
    with pytest.raises(ValueError, match="parameter"):
        Parameter(name)


@pytest.mark.parametrize("name", ["", " ", "9field", "bad-name", "a..b"])
def test_field_requires_safe_name(name: str) -> None:
    with pytest.raises(ValueError, match="field"):
        Field(name)


def test_in_list_must_not_be_empty() -> None:
    with pytest.raises(ValueError, match="at least one"):
        InList(Field("status"), ())


def test_normalize_uses_canonical_operator_spacing() -> None:
    expression = And(
        (
            Compare(Field("diameter"), CompareOperator.GREATER_EQUAL, LiteralValue(4)),
            Compare(Field("diameter"), CompareOperator.LESS, Parameter("maximum")),
        )
    )

    assert normalize(expression) == "diameter >= 4 AND diameter < :maximum"


def test_normalize_adds_only_precedence_preserving_parentheses() -> None:
    expression = And(
        (
            Or((equals("material", "PVC"), equals("material", "DI"))),
            Not(IsNull(Field("installed"))),
        )
    )

    assert normalize(expression) == (
        "(material = 'PVC' OR material = 'DI') AND NOT (installed IS NULL)"
    )


def test_normalize_formats_dates_and_utc_datetimes() -> None:
    eastern = timezone(timedelta(hours=-5))
    expression = And(
        (
            equals("installed", date(2024, 1, 2)),
            equals("inspected", datetime(2024, 1, 2, 8, 30, tzinfo=eastern)),
        )
    )

    assert normalize(expression) == (
        "installed = DATE '2024-01-02' AND inspected = TIMESTAMP '2024-01-02T13:30:00Z'"
    )


def test_normalize_escapes_apostrophes_and_formats_scalars() -> None:
    expression = InList(
        Field("owner"),
        (
            LiteralValue("O'Brien"),
            LiteralValue(True),
            LiteralValue(Decimal("1.250")),
        ),
        negated=True,
    )

    assert normalize(expression) == "owner NOT IN ('O''Brien', TRUE, 1.250)"


def test_normalize_handles_null_check_and_boolean_precedence() -> None:
    expression = Or(
        (
            And((equals("active", True), IsNull(Field("retired"), negated=True))),
            equals("status", None),
        )
    )

    assert normalize(expression) == (
        "active = TRUE AND retired IS NOT NULL OR status = NULL"
    )


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), Decimal("NaN"), datetime(2024, 1, 1)],
)
def test_literal_rejects_nonportable_values(value: object) -> None:
    with pytest.raises(ValueError, match="literal"):
        LiteralValue(value)  # type: ignore[arg-type]


def test_utc_datetime_keeps_canonical_z_suffix() -> None:
    expression = equals("observed", datetime(2024, 2, 3, tzinfo=UTC))

    assert normalize(expression) == "observed = TIMESTAMP '2024-02-03T00:00:00Z'"
