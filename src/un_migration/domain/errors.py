from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Safe identifiers that locate an operational failure."""

    run_id: str | None = None
    step_id: str | None = None
    dataset_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        values = {
            "run_id": self.run_id,
            "step_id": self.step_id,
            "dataset_id": self.dataset_id,
        }
        return {key: value for key, value in values.items() if value is not None}


class MigrationError(Exception):
    """Base class for safe, actionable toolkit failures."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        guidance: str,
        retryable: bool = False,
        context: ErrorContext | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.guidance = guidance
        self.retryable = retryable
        self.context = context or ErrorContext()

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "guidance": self.guidance,
            "retryable": self.retryable,
            "context": self.context.to_dict(),
        }


class ConfigurationError(MigrationError):
    """Configuration could not be resolved or validated."""


class CapabilityError(MigrationError):
    """An adapter cannot perform a requested operation."""


class InventoryError(MigrationError):
    """Dataset inventory could not be created."""


class MappingError(MigrationError):
    """A source-to-target mapping is invalid."""


class FilterSyntaxError(MigrationError):
    """A filter expression is invalid or unsafe."""


class TransformationError(MigrationError):
    """A record transformation failed."""


class StagingError(MigrationError):
    """A staging operation failed."""


class ValidationExecutionError(MigrationError):
    """A validator could not complete its operation."""


class DeploymentError(MigrationError):
    """A deployment operation failed."""


class NotificationError(MigrationError):
    """A reviewer notification could not be delivered."""


class IntegrityError(MigrationError):
    """A checksum, checkpoint, or state invariant failed."""
