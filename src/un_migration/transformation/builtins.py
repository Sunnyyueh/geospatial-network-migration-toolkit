import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from un_migration.domain.errors import ErrorContext, TransformationError
from un_migration.domain.findings import Evidence, Finding, FindingCollection
from un_migration.domain.identity import FindingId, SequenceIdGenerator
from un_migration.domain.schema import FieldType
from un_migration.domain.status import FindingStatus, Severity
from un_migration.mapping.models import DatasetMapping, NullPolicy
from un_migration.transformation.registry import (
    TransformContext,
    TransformRegistry,
    TransformResult,
)

_MISSING = object()


def _error(code: str, message: str, guidance: str) -> TransformationError:
    return TransformationError(code=code, message=message, guidance=guidance)


def _parameter(
    parameters: Mapping[str, object],
    name: str,
) -> object:
    if name not in parameters:
        raise _error(
            "transform.parameters",
            f"Transformation parameter {name!r} is required.",
            "Add the required parameter to the mapping reference table.",
        )
    return parameters[name]


def _identity(value: object, parameters: Mapping[str, object]) -> object:
    del parameters
    return value


def _trim(value: object, parameters: Mapping[str, object]) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _error(
            "transform.type",
            "Trim requires a string value.",
            "Cast the source value to string before trimming.",
        )
    trimmed = value.strip()
    if parameters.get("collapse", False):
        return " ".join(trimmed.split())
    return trimmed


def _uppercase(value: object, parameters: Mapping[str, object]) -> object:
    del parameters
    if value is None:
        return None
    if not isinstance(value, str):
        raise _error(
            "transform.type",
            "Uppercase requires a string value.",
            "Cast the source value to string before changing case.",
        )
    return value.upper()


def _lowercase(value: object, parameters: Mapping[str, object]) -> object:
    del parameters
    if value is None:
        return None
    if not isinstance(value, str):
        raise _error(
            "transform.type",
            "Lowercase requires a string value.",
            "Cast the source value to string before changing case.",
        )
    return value.lower()


def cast_value(value: object, target: FieldType) -> object:
    """Cast a value to one portable non-geometry field type."""

    if value is None:
        return None
    if target is FieldType.STRING:
        return str(value)
    if target is FieldType.INTEGER:
        if isinstance(value, bool):
            raise ValueError("boolean cannot be cast to integer")
        return int(str(value).strip())
    if target is FieldType.FLOAT:
        converted = float(str(value).strip())
        if not math.isfinite(converted):
            raise ValueError("float must be finite")
        return converted
    if target is FieldType.DECIMAL:
        converted_decimal = Decimal(str(value).strip())
        if not converted_decimal.is_finite():
            raise ValueError("decimal must be finite")
        return converted_decimal
    if target is FieldType.BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "yes", "y", "1"}:
                return True
            if normalized in {"false", "no", "n", "0"}:
                return False
        raise ValueError("boolean value is invalid")
    if target is FieldType.DATE:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value).strip())
    if target is FieldType.DATETIME:
        if isinstance(value, datetime):
            converted_datetime = value
        else:
            converted_datetime = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
        if converted_datetime.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return converted_datetime.astimezone(UTC)
    if target is FieldType.UUID:
        return str(UUID(str(value)))
    if target is FieldType.JSON:
        if isinstance(value, str):
            return json.loads(value)
        return json.loads(json.dumps(value, allow_nan=False))
    raise ValueError("geometry values require a backend-specific transformation")


def _cast(value: object, parameters: Mapping[str, object]) -> object:
    target = FieldType(str(_parameter(parameters, "to")).strip().casefold())
    return cast_value(value, target)


def _parse_date(value: object, parameters: Mapping[str, object]) -> object:
    if value is None or isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise _error(
            "transform.type",
            "Date parsing requires a string value.",
            "Cast the source value to string before parsing a date.",
        )
    format_value = parameters.get("format")
    if format_value is None:
        return date.fromisoformat(value)
    if not isinstance(format_value, str) or not format_value:
        raise _error(
            "transform.parameters",
            "Date format must be a nonempty string.",
            "Use a valid datetime.strptime format string.",
        )
    return datetime.strptime(value, format_value).date()


def _constant(value: object, parameters: Mapping[str, object]) -> object:
    del value
    return _parameter(parameters, "value")


def _default(value: object, parameters: Mapping[str, object]) -> object:
    replacement = _parameter(parameters, "value")
    empty = parameters.get("empty", False)
    return replacement if value is None or (empty is True and value == "") else value


def _lookup(value: object, parameters: Mapping[str, object]) -> object:
    values = _parameter(parameters, "values")
    if not isinstance(values, Mapping):
        raise _error(
            "transform.parameters",
            "Lookup values must be a mapping.",
            "Provide a JSON object in the values parameter.",
        )
    try:
        if value in values:
            return values[value]
    except TypeError as error:
        raise _error(
            "transform.type",
            "Lookup source values must be hashable.",
            "Transform the source into a scalar lookup key first.",
        ) from error
    policy = parameters.get("on_missing", "error")
    if policy == "keep":
        return value
    if policy == "null":
        return None
    if policy != "error":
        raise _error(
            "transform.parameters",
            "Lookup on_missing must be error, keep, or null.",
            "Correct the lookup miss policy.",
        )
    raise _error(
        "transform.lookup-missing",
        "Lookup table does not contain the source value.",
        "Add the source value to the lookup or select an explicit miss policy.",
    )


def _concatenate(value: object, parameters: Mapping[str, object]) -> object:
    parts = _parameter(parameters, "parts")
    separator = parameters.get("separator", "")
    if (
        not isinstance(parts, Sequence)
        or isinstance(parts, str | bytes)
        or not isinstance(separator, str)
    ):
        raise _error(
            "transform.parameters",
            "Concatenate requires a parts sequence and string separator.",
            "Provide parts as a JSON array and separator as text.",
        )
    rendered = [value if item == "$value" else item for item in parts]
    return separator.join("" if item is None else str(item) for item in rendered)


def _coalesce(value: object, parameters: Mapping[str, object]) -> object:
    if value not in {None, ""}:
        return value
    values = _parameter(parameters, "values")
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        raise _error(
            "transform.parameters",
            "Coalesce values must be a sequence.",
            "Provide fallback values as a JSON array.",
        )
    return next((item for item in values if item not in {None, ""}), None)


def default_registry() -> TransformRegistry:
    """Build a fresh registry containing deterministic portable transforms."""

    registry = TransformRegistry()
    for name, transform in (
        ("identity", _identity),
        ("cast", _cast),
        ("trim", _trim),
        ("uppercase", _uppercase),
        ("upper", _uppercase),
        ("lowercase", _lowercase),
        ("lower", _lowercase),
        ("parse_date", _parse_date),
        ("constant", _constant),
        ("default", _default),
        ("lookup", _lookup),
        ("concatenate", _concatenate),
        ("concat", _concatenate),
        ("coalesce", _coalesce),
    ):
        registry.register(name, transform)
    return registry


def _source_value(record: Mapping[str, object], field_name: str) -> object:
    if field_name in record:
        return record[field_name]
    normalized = field_name.casefold()
    for name, value in record.items():
        if name.casefold() == normalized:
            return value
    return _MISSING


def _cast_for_mapping(
    value: object,
    target_type: FieldType,
    context: TransformContext,
) -> object:
    try:
        return cast_value(value, target_type)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise TransformationError(
            code="transform.cast",
            message=(
                f"Value for target field {context.target_field!r} could not be cast."
            ),
            guidance=f"Supply a value compatible with {target_type.value}.",
            context=ErrorContext(dataset_id=str(context.dataset_id)),
        ) from error


def transform_record(
    record: Mapping[str, object],
    mapping: DatasetMapping,
    registry: TransformRegistry,
    *,
    record_id: str | None = None,
) -> TransformResult:
    """Project and transform one source record without mutating it."""

    output: dict[str, object] = {}
    findings: list[Finding] = []
    generator = SequenceIdGenerator()
    for field_mapping in mapping.fields:
        context = TransformContext(
            dataset_id=mapping.source_dataset,
            source_field=field_mapping.source_field,
            target_field=field_mapping.target_field,
            record_id=record_id,
        )
        value = _source_value(record, field_mapping.source_field)
        if value is _MISSING:
            raise TransformationError(
                code="transform.source-field",
                message=f"Source field {field_mapping.source_field!r} is absent.",
                guidance="Correct the mapping or source record schema.",
                context=ErrorContext(dataset_id=str(mapping.source_dataset)),
            )
        if value is None and field_mapping.null_policy is NullPolicy.DEFAULT:
            value = field_mapping.default
        elif value is None and field_mapping.null_policy is NullPolicy.REJECT:
            output[field_mapping.target_field] = None
            findings.append(
                Finding(
                    id=FindingId(generator.new("transform-finding")),
                    rule_id="transform.null",
                    status=FindingStatus.FAILED,
                    severity=Severity.ERROR,
                    message=f"Source field {field_mapping.source_field!r} is null.",
                    remediation="Populate the required value or configure a default.",
                    evidence=Evidence(
                        actual=None,
                        expected="non-null",
                        record_id=record_id,
                    ),
                    dataset_id=mapping.source_dataset,
                    field_name=field_mapping.target_field,
                )
            )
            continue
        if value is None:
            output[field_mapping.target_field] = None
            continue
        transformed = registry.apply(field_mapping.transform, value, context)
        output[field_mapping.target_field] = _cast_for_mapping(
            transformed,
            field_mapping.target_type,
            context,
        )
    return TransformResult(output, FindingCollection(tuple(findings)))
