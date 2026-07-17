from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from un_migration.domain.errors import FilterSyntaxError
from un_migration.filters.ast import (
    And,
    Compare,
    CompareOperator,
    Expression,
    Field,
    InList,
    IsNull,
    LiteralValue,
    Not,
    Or,
    Parameter,
)


@dataclass(frozen=True, slots=True)
class SqlDialect:
    """Minimal safe SQL surface required by the portable compiler."""

    identifier_quote: str = '"'
    placeholder: Literal["qmark", "named"] = "qmark"

    def __post_init__(self) -> None:
        if self.identifier_quote not in {'"', "`", "["}:
            raise ValueError(
                "identifier_quote must be one of double quote, backtick, ["
            )
        if self.placeholder not in {"qmark", "named"}:
            raise ValueError("placeholder must be qmark or named")


@dataclass(frozen=True, slots=True)
class CompiledSql:
    """SQL text plus values that must be bound separately by a driver."""

    text: str
    parameters: tuple[object, ...] | Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.parameters, Mapping):
            object.__setattr__(
                self,
                "parameters",
                MappingProxyType(dict(self.parameters)),
            )


class _Compiler:
    def __init__(
        self,
        dialect: SqlDialect,
        parameters: Mapping[str, object],
    ) -> None:
        self.dialect = dialect
        self.supplied = parameters
        self.values: list[object] = []

    def quote(self, field: Field) -> str:
        opening = self.dialect.identifier_quote
        closing = "]" if opening == "[" else opening
        return ".".join(
            f"{opening}{segment}{closing}" for segment in field.name.split(".")
        )

    def resolve(self, value: LiteralValue | Parameter) -> object:
        if isinstance(value, LiteralValue):
            return value.value
        try:
            return self.supplied[value.name]
        except KeyError as error:
            raise FilterSyntaxError(
                code="filter.parameter-missing",
                message=f"Filter parameter {value.name!r} was not supplied.",
                guidance="Supply every named parameter before SQL compilation.",
            ) from error

    def bind(self, value: LiteralValue | Parameter) -> str:
        self.values.append(self.resolve(value))
        if self.dialect.placeholder == "qmark":
            return "?"
        return f":p{len(self.values)}"

    def precedence(self, expression: Expression) -> int:
        if isinstance(expression, Or):
            return 1
        if isinstance(expression, And):
            return 2
        if isinstance(expression, Not):
            return 3
        return 4

    def render(self, expression: Expression, parent_precedence: int = 0) -> str:
        precedence = self.precedence(expression)
        if isinstance(expression, Compare):
            if (
                isinstance(expression.right, LiteralValue)
                and expression.right.value is None
                and expression.operator
                in {CompareOperator.EQUAL, CompareOperator.NOT_EQUAL}
            ):
                operator = (
                    "IS NULL"
                    if expression.operator is CompareOperator.EQUAL
                    else "IS NOT NULL"
                )
                rendered = f"{self.quote(expression.left)} {operator}"
            else:
                rendered = (
                    f"{self.quote(expression.left)} {expression.operator.value} "
                    f"{self.bind(expression.right)}"
                )
        elif isinstance(expression, InList):
            operator = "NOT IN" if expression.negated else "IN"
            values = ", ".join(self.bind(value) for value in expression.values)
            rendered = f"{self.quote(expression.field)} {operator} ({values})"
        elif isinstance(expression, IsNull):
            operator = "IS NOT NULL" if expression.negated else "IS NULL"
            rendered = f"{self.quote(expression.field)} {operator}"
        elif isinstance(expression, Not):
            rendered = f"NOT ({self.render(expression.expression)})"
        elif isinstance(expression, And):
            rendered = " AND ".join(
                self.render(item, precedence) for item in expression.expressions
            )
        elif isinstance(expression, Or):
            rendered = " OR ".join(
                self.render(item, precedence) for item in expression.expressions
            )
        else:
            raise TypeError(f"Unsupported filter node: {type(expression).__name__}")
        if precedence < parent_precedence:
            return f"({rendered})"
        return rendered


def compile_sql(
    expression: Expression,
    dialect: SqlDialect,
    parameters: Mapping[str, object] | None = None,
) -> CompiledSql:
    """Compile an expression without interpolating any values into SQL text."""

    compiler = _Compiler(dialect, parameters if parameters is not None else {})
    text = compiler.render(expression)
    if dialect.placeholder == "qmark":
        compiled_parameters: tuple[object, ...] | Mapping[str, object] = tuple(
            compiler.values
        )
    else:
        compiled_parameters = {
            f"p{index}": value for index, value in enumerate(compiler.values, start=1)
        }
    return CompiledSql(text, compiled_parameters)
