import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias

from un_migration.domain.errors import ErrorContext, TransformationError
from un_migration.domain.findings import FindingCollection
from un_migration.domain.identity import DatasetId
from un_migration.mapping.models import TransformSpec

Transform: TypeAlias = Callable[[object, Mapping[str, object]], object]
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class TransformContext:
    """Safe record location supplied when applying a transformation."""

    dataset_id: DatasetId
    source_field: str
    target_field: str
    record_id: str | None = None

    def __post_init__(self) -> None:
        for attribute in ("source_field", "target_field"):
            if not getattr(self, attribute).strip():
                raise ValueError(f"{attribute} must not be empty")
        if self.record_id is not None and not self.record_id.strip():
            raise ValueError("record_id must not be empty")


@dataclass(frozen=True, slots=True)
class TransformResult:
    """One immutable transformed record and its validation findings."""

    record: Mapping[str, object]
    findings: FindingCollection = field(default_factory=FindingCollection)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record", MappingProxyType(dict(self.record)))


class TransformRegistry:
    """Explicit allowlist of deterministic transformation callables."""

    def __init__(self) -> None:
        self._transforms: dict[str, Transform] = {}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._transforms))

    def register(self, name: str, transform: Transform) -> None:
        normalized = name.strip().casefold()
        if not _NAME.fullmatch(normalized):
            raise ValueError("invalid transformation name")
        if normalized in self._transforms:
            raise ValueError(f"transformation already registered: {normalized}")
        self._transforms[normalized] = transform

    @staticmethod
    def _context(context: TransformContext | None) -> ErrorContext:
        return ErrorContext(
            dataset_id=str(context.dataset_id) if context is not None else None
        )

    def apply(
        self,
        spec: TransformSpec,
        value: object,
        context: TransformContext | None = None,
    ) -> object:
        try:
            transform = self._transforms[spec.name]
        except KeyError as error:
            raise TransformationError(
                code="transform.unknown",
                message=f"Unknown transformation: {spec.name}.",
                guidance="Register the transformation before running migration.",
                context=self._context(context),
            ) from error
        try:
            return transform(value, spec.parameters)
        except TransformationError as error:
            if context is None or error.context.dataset_id is not None:
                raise
            raise TransformationError(
                code=error.code,
                message=error.message,
                guidance=error.guidance,
                retryable=error.retryable,
                context=self._context(context),
            ) from error
        except Exception as error:
            location = (
                f" for target field {context.target_field!r}"
                if context is not None
                else ""
            )
            raise TransformationError(
                code="transform.failed",
                message=f"Transformation {spec.name!r} failed{location}.",
                guidance="Correct the transform parameters or source value.",
                context=self._context(context),
            ) from error
