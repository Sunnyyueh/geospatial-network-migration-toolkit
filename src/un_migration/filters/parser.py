from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from un_migration.domain.errors import ErrorContext, FilterSyntaxError
from un_migration.domain.schema import DatasetInventory, FieldSchema, FieldType
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
    Scalar,
)


class TokenKind(StrEnum):
    IDENTIFIER = "identifier"
    NUMBER = "number"
    STRING = "string"
    PARAMETER = "parameter"
    OPERATOR = "operator"
    LEFT_PAREN = "left_paren"
    RIGHT_PAREN = "right_paren"
    COMMA = "comma"
    END = "end"


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    position: int


_TOKEN = re.compile(
    r"(?P<whitespace>\s+)"
    r"|(?P<string>'(?:''|[^'])*')"
    r"|(?P<parameter>:[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<number>[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)"
    r"|(?P<operator><=|>=|!=|<>|=|<|>)"
    r"|(?P<left_paren>\()"
    r"|(?P<right_paren>\))"
    r"|(?P<comma>,)"
    r"|(?P<identifier>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)


def _error(
    code: str,
    message: str,
    guidance: str,
    *,
    inventory: DatasetInventory | None = None,
) -> FilterSyntaxError:
    context = ErrorContext(dataset_id=str(inventory.dataset.id)) if inventory else None
    return FilterSyntaxError(
        code=code,
        message=message,
        guidance=guidance,
        context=context,
    )


def _syntax(message: str, position: int) -> FilterSyntaxError:
    return _error(
        "filter.syntax",
        f"{message} at position {position + 1}.",
        "Use comparisons, IN, IS NULL, parentheses, and AND/OR/NOT operators.",
    )


def _tokenize(text: str) -> tuple[Token, ...]:
    tokens: list[Token] = []
    position = 0
    while position < len(text):
        matched = _TOKEN.match(text, position)
        if matched is None:
            raise _syntax(f"Unexpected character {text[position]!r}", position)
        kind_name = matched.lastgroup
        if kind_name is None:
            raise _syntax("Unexpected token", position)
        if kind_name != "whitespace":
            tokens.append(Token(TokenKind(kind_name), matched.group(), position))
        position = matched.end()
    tokens.append(Token(TokenKind.END, "", len(text)))
    return tuple(tokens)


_OPERATORS = {
    "=": CompareOperator.EQUAL,
    "!=": CompareOperator.NOT_EQUAL,
    "<>": CompareOperator.NOT_EQUAL,
    "<": CompareOperator.LESS,
    "<=": CompareOperator.LESS_EQUAL,
    ">": CompareOperator.GREATER,
    ">=": CompareOperator.GREATER_EQUAL,
}


class _Parser:
    def __init__(self, tokens: tuple[Token, ...]) -> None:
        self._tokens = tokens
        self._index = 0

    @property
    def current(self) -> Token:
        return self._tokens[self._index]

    def _advance(self) -> Token:
        token = self.current
        if token.kind is not TokenKind.END:
            self._index += 1
        return token

    def _keyword(self, value: str) -> bool:
        return (
            self.current.kind is TokenKind.IDENTIFIER
            and self.current.text.casefold() == value.casefold()
        )

    def _accept_keyword(self, value: str) -> bool:
        if not self._keyword(value):
            return False
        self._advance()
        return True

    def _expect(self, kind: TokenKind, description: str) -> Token:
        if self.current.kind is not kind:
            raise _syntax(f"Expected {description}", self.current.position)
        return self._advance()

    def parse(self) -> Expression:
        end_index = len(self._tokens) - 1
        if self._index == end_index:
            raise _syntax("Filter expression is empty", self.current.position)
        expression = self._parse_or()
        if self._index != end_index:
            raise _syntax(
                f"Unexpected token {self.current.text!r}", self.current.position
            )
        return expression

    def _parse_or(self) -> Expression:
        expressions = [self._parse_and()]
        while self._accept_keyword("OR"):
            expressions.append(self._parse_and())
        return Or(tuple(expressions)) if len(expressions) > 1 else expressions[0]

    def _parse_and(self) -> Expression:
        expressions = [self._parse_not()]
        while self._accept_keyword("AND"):
            expressions.append(self._parse_not())
        return And(tuple(expressions)) if len(expressions) > 1 else expressions[0]

    def _parse_not(self) -> Expression:
        if self._accept_keyword("NOT"):
            return Not(self._parse_not())
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        if self.current.kind is TokenKind.LEFT_PAREN:
            self._advance()
            expression = self._parse_or()
            self._expect(TokenKind.RIGHT_PAREN, "closing parenthesis")
            return expression
        return self._parse_predicate()

    def _parse_predicate(self) -> Expression:
        token = self._expect(TokenKind.IDENTIFIER, "field name")
        try:
            field = Field(token.text)
        except ValueError as error:
            raise _syntax("Invalid field name", token.position) from error
        if self.current.kind is TokenKind.OPERATOR:
            operator = _OPERATORS[self._advance().text]
            return Compare(field, operator, self._parse_value())
        if self._accept_keyword("IS"):
            negated = self._accept_keyword("NOT")
            if not self._accept_keyword("NULL"):
                raise _syntax("Expected NULL after IS", self.current.position)
            return IsNull(field, negated)
        negated = self._accept_keyword("NOT")
        if self._accept_keyword("IN"):
            return self._parse_in_list(field, negated)
        if negated:
            raise _syntax("Expected IN after NOT", self.current.position)
        raise _syntax("Expected a comparison, IN, or IS NULL", self.current.position)

    def _parse_in_list(self, field: Field, negated: bool) -> InList:
        self._expect(TokenKind.LEFT_PAREN, "opening parenthesis after IN")
        if self.current.kind is TokenKind.RIGHT_PAREN:
            raise _syntax("IN list cannot be empty", self.current.position)
        values = [self._parse_value()]
        while self.current.kind is TokenKind.COMMA:
            self._advance()
            values.append(self._parse_value())
        self._expect(TokenKind.RIGHT_PAREN, "closing parenthesis after IN list")
        return InList(field, tuple(values), negated)

    def _parse_value(self) -> LiteralValue | Parameter:
        token = self.current
        if token.kind is TokenKind.PARAMETER:
            self._advance()
            return Parameter(token.text[1:])
        if token.kind is TokenKind.STRING:
            self._advance()
            return LiteralValue(token.text[1:-1].replace("''", "'"))
        if token.kind is TokenKind.NUMBER:
            self._advance()
            return LiteralValue(_number(token))
        if self._accept_keyword("TRUE"):
            return LiteralValue(True)
        if self._accept_keyword("FALSE"):
            return LiteralValue(False)
        if self._accept_keyword("NULL"):
            return LiteralValue(None)
        if self._accept_keyword("DATE"):
            return LiteralValue(_date_literal(self._string_value("DATE"), token))
        if self._accept_keyword("TIMESTAMP"):
            return LiteralValue(
                _timestamp_literal(self._string_value("TIMESTAMP"), token)
            )
        raise _syntax("Expected a literal or named parameter", token.position)

    def _string_value(self, literal_type: str) -> str:
        token = self._expect(
            TokenKind.STRING,
            f"quoted value after {literal_type}",
        )
        return token.text[1:-1].replace("''", "'")


def _number(token: Token) -> int | Decimal:
    try:
        if any(marker in token.text.casefold() for marker in (".", "e")):
            return Decimal(token.text)
        return int(token.text)
    except (InvalidOperation, ValueError) as error:
        raise _syntax("Invalid numeric literal", token.position) from error


def _date_literal(value: str, token: Token) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _syntax("Invalid DATE literal", token.position) from error


def _timestamp_literal(value: str, token: Token) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed
    except ValueError as error:
        raise _syntax("Invalid TIMESTAMP literal", token.position) from error


def parse_filter(text: str) -> Expression:
    """Parse untrusted filter text into a typed expression tree."""

    return _Parser(_tokenize(text)).parse()


def _field_schema(field: Field, inventory: DatasetInventory) -> FieldSchema:
    name = field.name.rsplit(".", maxsplit=1)[-1]
    schema = inventory.field(name)
    if schema is None:
        raise _error(
            "filter.unknown-field",
            f"Filter field {field.name!r} does not exist in the source inventory.",
            "Use a field name reported by the inventory command.",
            inventory=inventory,
        )
    return schema


def _compatible_literal(field_type: FieldType, value: Scalar) -> bool:
    if value is None:
        return True
    if field_type in {FieldType.STRING, FieldType.UUID, FieldType.JSON}:
        return isinstance(value, str)
    if field_type is FieldType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type in {FieldType.FLOAT, FieldType.DECIMAL}:
        return isinstance(value, int | float | Decimal) and not isinstance(value, bool)
    if field_type is FieldType.BOOLEAN:
        return isinstance(value, bool)
    if field_type is FieldType.DATE:
        return isinstance(value, date) and not isinstance(value, datetime)
    if field_type is FieldType.DATETIME:
        return isinstance(value, datetime)
    return False


def _validate_value(
    field: Field,
    value: LiteralValue | Parameter,
    inventory: DatasetInventory,
) -> None:
    schema = _field_schema(field, inventory)
    if isinstance(value, Parameter):
        return
    if not _compatible_literal(schema.type, value.value):
        raise _error(
            "filter.type",
            f"Literal is incompatible with {field.name!r} ({schema.type.value}).",
            "Use a literal matching the inventoried field type.",
            inventory=inventory,
        )


def validate_filter_fields(
    expression: Expression,
    inventory: DatasetInventory,
) -> None:
    """Validate field existence and literal compatibility before compilation."""

    if isinstance(expression, Compare):
        _validate_value(expression.left, expression.right, inventory)
    elif isinstance(expression, InList):
        for value in expression.values:
            _validate_value(expression.field, value, inventory)
    elif isinstance(expression, IsNull):
        _field_schema(expression.field, inventory)
    elif isinstance(expression, Not):
        validate_filter_fields(expression.expression, inventory)
    else:
        for child in expression.expressions:
            validate_filter_fields(child, inventory)
