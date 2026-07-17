import pytest

from un_migration.config.merge import (
    apply_overrides,
    deep_merge,
    parse_override,
)
from un_migration.domain.errors import ConfigurationError


def test_deep_merge_combines_mappings_and_replaces_other_values() -> None:
    base = {
        "runtime": {"batch_size": 1000, "mode": "safe"},
        "formats": ["json"],
    }
    overlay = {
        "runtime": {"batch_size": 250},
        "formats": ["json", "html"],
    }

    result = deep_merge(base, overlay)

    assert result == {
        "runtime": {"batch_size": 250, "mode": "safe"},
        "formats": ["json", "html"],
    }
    assert base["runtime"] == {"batch_size": 1000, "mode": "safe"}
    assert overlay["runtime"] == {"batch_size": 250}


@pytest.mark.parametrize(
    ("text", "path", "value"),
    [
        ("runtime.batch_size=250", ("runtime", "batch_size"), 250),
        ("deployment.enabled=true", ("deployment", "enabled"), True),
        ("profile.name=water", ("profile", "name"), "water"),
        (
            "filters.values=[active, proposed]",
            ("filters", "values"),
            ["active", "proposed"],
        ),
    ],
)
def test_parse_override_preserves_scalar_types(
    text: str,
    path: tuple[str, ...],
    value: object,
) -> None:
    assert parse_override(text) == (path, value)


def test_apply_overrides_updates_existing_leaf_without_mutation() -> None:
    value = {"runtime": {"batch_size": 1000}, "project_name": "water"}

    result = apply_overrides(value, ("runtime.batch_size=250",))

    assert result["runtime"] == {"batch_size": 250}
    assert value["runtime"] == {"batch_size": 1000}


@pytest.mark.parametrize(
    "override",
    [
        "runtime.missing=1",
        "runtime..batch_size=1",
        "runtime.batch_size",
        "=1",
    ],
)
def test_invalid_override_uses_stable_error(override: str) -> None:
    with pytest.raises(ConfigurationError) as raised:
        apply_overrides({"runtime": {"batch_size": 1000}}, (override,))

    assert raised.value.code == "config.override"
