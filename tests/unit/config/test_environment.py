import pytest

from un_migration.config.environment import (
    SecretRegistry,
    interpolate_environment,
    redact_secrets,
)
from un_migration.domain.errors import ConfigurationError


def test_interpolation_supports_required_and_default_values() -> None:
    value = {
        "workspace": "${SOURCE_PATH}",
        "profile": "${PROFILE:-water}",
        "nested": ["${BATCH_SIZE}", True],
    }

    assert interpolate_environment(
        value,
        {"SOURCE_PATH": "/data", "BATCH_SIZE": "250"},
    ) == {
        "workspace": "/data",
        "profile": "water",
        "nested": ["250", True],
    }


def test_interpolation_preserves_tuple_shape() -> None:
    result = interpolate_environment(("${PROFILE:-water}",), {})

    assert result == ("water",)
    assert isinstance(result, tuple)


def test_missing_required_variable_raises_safe_error() -> None:
    with pytest.raises(ConfigurationError, match=r"environment\.missing"):
        interpolate_environment("${TOKEN}", {})


def test_non_expression_string_is_unchanged() -> None:
    assert interpolate_environment("prefix-${PROFILE}", {"PROFILE": "water"}) == (
        "prefix-${PROFILE}"
    )


def test_redaction_replaces_nested_secret_values_case_insensitively() -> None:
    value = {
        "auth": {"Token": "secret", "nested": [{"password": "hidden"}]},
        "project": "public",
    }

    assert redact_secrets(value, frozenset({"token", "password"})) == {
        "auth": {
            "Token": "***REDACTED***",
            "nested": [{"password": "***REDACTED***"}],
        },
        "project": "public",
    }


def test_secret_registry_normalizes_keys() -> None:
    registry = SecretRegistry(frozenset({"Token", "CLIENT_SECRET"}))

    assert registry.is_secret("token")
    assert registry.is_secret("client_secret")
    assert not registry.is_secret("project_name")
