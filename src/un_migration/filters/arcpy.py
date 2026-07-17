import math
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal

from un_migration.domain.errors import FilterSyntaxError
from un_migration.filters.ast import (
    And,
    Compare,
    Expression,
    Field,
    InList,
    IsNull,
    LiteralValue,
    Not,
    Or,
    Parameter,
)

DelimitField = Callable[[str], str]


def _error(code: str, message: str, guidance: str) -> FilterSyntaxError:
    return FilterSyntaxError(code=code, message=message, guidance=guidance)


class _Compiler:
    def __init__(
        self,
        delimit_field: DelimitField,
        parameters: Mapping[str, object],
    ) -> None:
        self.delimit_field = delimit_field
        self.parameters = parameters

    def field(self, field: Field) -> str:
        delimited = self.delimit_field(field.name)
        if not isinstance(delimited, str) or not delimited or "\x00" in delimited:
            raise _error(
                "filter.field-delimiter",
                f"Field delimiter returned an unsafe value for {field.name!r}.",
                "Return a nonempty backend-delimited field identifier.",
            )
        return delimited

    def value(self, value: LiteralValue | Parameter) -> str:
        if isinstance(value, Parameter):
            try:
                resolved = self.parameters[value.name]
            except KeyError as error:
                raise _error(
                    "filter.parameter-missing",
                    f"Filter parameter {value.name!r} was not supplied.",
                    "Supply every named parameter before ArcPy compilation.",
                ) from error
        else:
            resolved = value.value
        return _literal(resolved)

    @staticmethod
    def precedence(expression: Expression) -> int:
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
            rendered = (
                f"{self.field(expression.left)} {expression.operator.value} "
                f"{self.value(expression.right)}"
            )
        elif isinstance(expression, InList):
            operator = "NOT IN" if expression.negated else "IN"
            values = ", ".join(self.value(value) for value in expression.values)
            rendered = f"{self.field(expression.field)} {operator} ({values})"
        elif isinstance(expression, IsNull):
            operator = "IS NOT NULL" if expression.negated else "IS NULL"
            rendered = f"{self.field(expression.field)} {operator}"
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


def _literal(value: object) -> str:
    if value is None:
        raise _error(
            "filter.literal",
            "Null cannot be rendered as an ArcPy comparison literal.",
            "Use IS NULL or IS NOT NULL instead.",
        )
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise _error(
                "filter.literal",
                "ArcPy datetime literals must be timezone-aware.",
                "Add an explicit timezone to the datetime value.",
            )
        normalized = value.astimezone(UTC).isoformat(timespec="seconds")
        return f"TIMESTAMP '{normalized.replace('+00:00', 'Z')}'"
    if isinstance(value, date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, str):
        if "\x00" in value:
            raise _error(
                "filter.literal",
                "ArcPy string literals cannot contain null bytes.",
                "Remove the null byte from the filter value.",
            )
        return f"'{value.replace(chr(39), chr(39) * 2)}'"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return repr(value)
        raise _error(
            "filter.literal",
            "ArcPy numeric literals must be finite.",
            "Replace NaN or infinity with a finite number.",
        )
    if isinstance(value, Decimal):
        if value.is_finite():
            return str(value)
        raise _error(
            "filter.literal",
            "ArcPy decimal literals must be finite.",
            "Replace NaN or infinity with a finite decimal.",
        )
    raise _error(
        "filter.literal",
        f"Unsupported ArcPy literal type: {type(value).__name__}.",
        "Use a string, number, boolean, date, or timezone-aware datetime.",
    )


def compile_arcpy(
    expression: Expression,
    delimit_field: DelimitField,
    parameters: Mapping[str, object] | None = None,
) -> str:
    """Compile an AST to an escaped ArcPy where clause without importing ArcPy."""

    compiler = _Compiler(
        delimit_field,
        parameters if parameters is not None else {},
    )
    return compiler.render(expression)
