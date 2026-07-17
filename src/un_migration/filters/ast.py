from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TypeAlias

Scalar: TypeAlias = None | bool | int | float | Decimal | str | date | datetime

_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_PARAMETER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class LiteralValue:
    """A portable scalar embedded in a filter expression."""

    value: Scalar

    def __post_init__(self) -> None:
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("filter literal float must be finite")
        if isinstance(self.value, Decimal) and not self.value.is_finite():
            raise ValueError("filter literal decimal must be finite")
        if isinstance(self.value, datetime) and self.value.tzinfo is None:
            raise ValueError("filter literal datetime must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Field:
    """A validated field reference, optionally qualified by dataset."""

    name: str

    def __post_init__(self) -> None:
        normalized = self.name.strip()
        if not _FIELD_NAME.fullmatch(normalized):
            raise ValueError("invalid filter field name")
        object.__setattr__(self, "name", normalized)


@dataclass(frozen=True, slots=True)
class Parameter:
    """A named value supplied separately when evaluating a filter."""

    name: str

    def __post_init__(self) -> None:
        normalized = self.name.strip()
        if not _PARAMETER_NAME.fullmatch(normalized):
            raise ValueError("invalid filter parameter name")
        object.__setattr__(self, "name", normalized)


class CompareOperator(StrEnum):
    """Portable binary comparison operators."""

    EQUAL = "="
    NOT_EQUAL = "!="
    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="


@dataclass(frozen=True, slots=True)
class Compare:
    left: Field
    operator: CompareOperator
    right: LiteralValue | Parameter


@dataclass(frozen=True, slots=True)
class InList:
    field: Field
    values: tuple[LiteralValue | Parameter, ...]
    negated: bool = False

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("IN list must contain at least one value")


@dataclass(frozen=True, slots=True)
class IsNull:
    field: Field
    negated: bool = False


@dataclass(frozen=True, slots=True)
class Not:
    expression: Expression


@dataclass(frozen=True, slots=True)
class And:
    expressions: tuple[Expression, ...]

    def __post_init__(self) -> None:
        if len(self.expressions) < 2:
            raise ValueError("AND requires at least two expressions")


@dataclass(frozen=True, slots=True)
class Or:
    expressions: tuple[Expression, ...]

    def __post_init__(self) -> None:
        if len(self.expressions) < 2:
            raise ValueError("OR requires at least two expressions")


Expression: TypeAlias = Compare | InList | IsNull | Not | And | Or


def _literal(value: Scalar) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC).isoformat(timespec="auto")
        return f"TIMESTAMP '{normalized.replace('+00:00', 'Z')}'"
    if isinstance(value, date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, str):
        return f"'{value.replace(chr(39), chr(39) * 2)}'"
    return str(value)


def _value(value: LiteralValue | Parameter) -> str:
    if isinstance(value, Parameter):
        return f":{value.name}"
    return _literal(value.value)


def _precedence(expression: Expression) -> int:
    if isinstance(expression, Or):
        return 1
    if isinstance(expression, And):
        return 2
    if isinstance(expression, Not):
        return 3
    return 4


def _render(expression: Expression, parent_precedence: int = 0) -> str:
    precedence = _precedence(expression)
    if isinstance(expression, Compare):
        rendered = (
            f"{expression.left.name} {expression.operator.value} "
            f"{_value(expression.right)}"
        )
    elif isinstance(expression, InList):
        operator = "NOT IN" if expression.negated else "IN"
        rendered_values = ", ".join(_value(item) for item in expression.values)
        rendered = f"{expression.field.name} {operator} ({rendered_values})"
    elif isinstance(expression, IsNull):
        operator = "IS NOT NULL" if expression.negated else "IS NULL"
        rendered = f"{expression.field.name} {operator}"
    elif isinstance(expression, Not):
        rendered = f"NOT ({_render(expression.expression)})"
    elif isinstance(expression, And):
        rendered = " AND ".join(
            _render(item, precedence) for item in expression.expressions
        )
    else:
        rendered = " OR ".join(
            _render(item, precedence) for item in expression.expressions
        )
    if precedence < parent_precedence:
        return f"({rendered})"
    return rendered


def normalize(expression: Expression) -> str:
    """Render a deterministic, backend-independent filter expression."""

    return _render(expression)
