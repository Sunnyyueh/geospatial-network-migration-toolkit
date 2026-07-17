import pytest

from un_migration.domain.errors import (
    ConfigurationError,
    ErrorContext,
    MigrationError,
)


def test_error_exposes_safe_structured_diagnostic() -> None:
    error = ConfigurationError(
        code="config.missing",
        message="Required source path is missing.",
        guidance="Set source.workspace in the project file.",
        retryable=False,
        context=ErrorContext(run_id="run-1", step_id="configure"),
    )

    assert str(error) == "config.missing: Required source path is missing."
    assert error.to_dict() == {
        "code": "config.missing",
        "message": "Required source path is missing.",
        "guidance": "Set source.workspace in the project file.",
        "retryable": False,
        "context": {"run_id": "run-1", "step_id": "configure"},
    }


def test_error_omits_unset_context_values() -> None:
    error = MigrationError(
        code="migration.failed",
        message="Migration stopped.",
        guidance="Review the run log.",
    )

    assert error.to_dict()["context"] == {}


def test_typed_errors_remain_standard_exceptions() -> None:
    error = ConfigurationError(
        code="config.invalid",
        message="Configuration is invalid.",
        guidance="Run un-migrate config validate.",
    )

    with pytest.raises(MigrationError, match="Configuration is invalid"):
        raise error
