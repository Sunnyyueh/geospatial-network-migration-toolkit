import re

import pytest

from un_migration.domain.identity import (
    DatasetId,
    SequenceIdGenerator,
    Uuid7LikeGenerator,
)


def test_dataset_id_normalizes_safe_value() -> None:
    assert str(DatasetId(" Water Mains ")) == "water-mains"
    assert str(DatasetId("asset_group.main")) == "asset-group.main"


@pytest.mark.parametrize("value", ["", "../secret", "water/main", "🔥"])
def test_dataset_id_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid DatasetId"):
        DatasetId(value)


def test_sequence_generator_is_deterministic() -> None:
    generator = SequenceIdGenerator(start=7)

    assert generator.new("run") == "run-000007"
    assert generator.new("step") == "step-000008"


def test_sequence_generator_rejects_negative_start() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        SequenceIdGenerator(start=-1)


def test_uuid_like_generator_returns_safe_sortable_shape() -> None:
    value = Uuid7LikeGenerator().new("run")

    assert re.fullmatch(r"run-\d{13}-[0-9a-f]{16}", value)
