import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from typing import TypeAlias, cast

from un_migration.domain.artifacts import Checksum

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def to_primitive(value: object) -> JSONValue:
    """Convert supported domain values to deterministic JSON primitives."""

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Enum):
        return to_primitive(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        normalized = value.astimezone(UTC).isoformat(timespec="auto")
        return normalized.replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, PurePath):
        return value.as_posix()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_primitive(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        if any(not isinstance(key, str) for key in mapping):
            raise TypeError("canonical mapping keys must be strings")
        return {
            cast(str, key): to_primitive(item)
            for key, item in sorted(
                mapping.items(),
                key=lambda pair: cast(str, pair[0]),
            )
        }
    if isinstance(value, set | frozenset):
        converted = [to_primitive(item) for item in value]
        return sorted(converted, key=canonical_json)
    if isinstance(value, tuple | list):
        return [to_primitive(item) for item in value]
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Serialize a supported value using stable, compact JSON."""

    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint(value: object) -> Checksum:
    """Return the SHA-256 checksum of a value's canonical JSON."""

    return Checksum.sha256(canonical_json(value).encode("utf-8"))
