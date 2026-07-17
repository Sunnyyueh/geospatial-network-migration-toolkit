from datetime import UTC, datetime

import pytest

from un_migration.domain.time import FixedClock, SystemClock


def test_fixed_clock_returns_supplied_utc_instant() -> None:
    instant = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)

    assert FixedClock(instant).now() is instant


def test_fixed_clock_rejects_naive_instant() -> None:
    instant = datetime(2026, 7, 16, 12, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(instant)


def test_system_clock_returns_timezone_aware_utc() -> None:
    instant = SystemClock().now()

    assert instant.tzinfo is UTC
