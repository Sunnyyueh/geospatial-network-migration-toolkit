from collections.abc import Mapping

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


def _error(code: str, message: str, guidance: str) -> FilterSyntaxError:
    return FilterSyntaxError(code=code, message=message, guidance=guidance)


def _field(field: Field, record: Mapping[str, object]) -> object:
    candidates = (field.name, field.name.rsplit(".", maxsplit=1)[-1])
    for name in candidates:
        if name in record:
            return record[name]
    normalized = {name.casefold() for name in candidates}
    for name, value in record.items():
        if name.casefold() in normalized:
            return value
    raise _error(
        "filter.field-missing",
        f"Filter field {field.name!r} is absent from the current record.",
        "Inventory the source again or correct the filter field name.",
    )


def _value(
    value: LiteralValue | Parameter,
    parameters: Mapping[str, object],
) -> object:
    if isinstance(value, LiteralValue):
        return value.value
    try:
        return parameters[value.name]
    except KeyError as error:
        raise _error(
            "filter.parameter-missing",
            f"Filter parameter {value.name!r} was not supplied.",
            "Supply every named filter parameter before evaluation.",
        ) from error


def _compare(operator: CompareOperator, left: object, right: object) -> bool:
    if operator is CompareOperator.EQUAL:
        return left == right
    if operator is CompareOperator.NOT_EQUAL:
        return left != right
    if left is None or right is None:
        return False
    try:
        if operator is CompareOperator.LESS:
            return bool(left < right)  # type: ignore[operator]
        if operator is CompareOperator.LESS_EQUAL:
            return bool(left <= right)  # type: ignore[operator]
        if operator is CompareOperator.GREATER:
            return bool(left > right)  # type: ignore[operator]
        return bool(left >= right)  # type: ignore[operator]
    except TypeError as error:
        raise _error(
            "filter.incomparable",
            "Filter attempted an ordered comparison between incompatible values.",
            "Use a literal or parameter compatible with the record field type.",
        ) from error


def evaluate(
    expression: Expression,
    record: Mapping[str, object],
    parameters: Mapping[str, object] | None = None,
) -> bool:
    """Evaluate a typed filter expression against one record."""

    resolved_parameters = parameters or {}
    if isinstance(expression, Compare):
        return _compare(
            expression.operator,
            _field(expression.left, record),
            _value(expression.right, resolved_parameters),
        )
    if isinstance(expression, InList):
        actual = _field(expression.field, record)
        values = tuple(
            _value(value, resolved_parameters) for value in expression.values
        )
        contained = actual in values
        return not contained if expression.negated else contained
    if isinstance(expression, IsNull):
        is_null = _field(expression.field, record) is None
        return not is_null if expression.negated else is_null
    if isinstance(expression, Not):
        return not evaluate(expression.expression, record, resolved_parameters)
    if isinstance(expression, And):
        return all(
            evaluate(item, record, resolved_parameters)
            for item in expression.expressions
        )
    if isinstance(expression, Or):
        return any(
            evaluate(item, record, resolved_parameters)
            for item in expression.expressions
        )
    raise TypeError(f"Unsupported filter node: {type(expression).__name__}")
