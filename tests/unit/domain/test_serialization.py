from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from un_migration.domain.serialization import (
    canonical_json,
    fingerprint,
    to_primitive,
)


def test_canonical_json_is_ordered_and_normalized() -> None:
    value = {
        "when": datetime(2026, 7, 16, 12, tzinfo=UTC),
        "amount": Decimal("12.500"),
        "tags": {"b", "a"},
    }

    assert canonical_json(value) == (
        '{"amount":"12.500","tags":["a","b"],"when":"2026-07-16T12:00:00Z"}'
    )
    assert fingerprint(value) == fingerprint(dict(reversed(value.items())))


def test_datetime_is_normalized_to_utc() -> None:
    eastern = timezone(-timedelta(hours=4))
    value = datetime(2026, 7, 16, 8, 30, tzinfo=eastern)

    assert to_primitive(value) == "2026-07-16T12:30:00Z"


def test_dataclass_and_path_become_json_primitives() -> None:
    @dataclass(frozen=True)
    class Sample:
        path: Path
        count: int

    assert to_primitive(Sample(Path("reports/run.json"), 2)) == {
        "path": "reports/run.json",
        "count": 2,
    }


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_primitive(datetime(2026, 7, 16))


def test_non_string_mapping_key_is_rejected() -> None:
    with pytest.raises(TypeError, match="mapping keys"):
        to_primitive({1: "value"})


def test_unknown_value_is_rejected() -> None:
    with pytest.raises(TypeError, match="Unsupported canonical value"):
        to_primitive(object())


def test_non_finite_number_is_rejected_by_canonical_json() -> None:
    with pytest.raises(ValueError):
        canonical_json(float("nan"))
