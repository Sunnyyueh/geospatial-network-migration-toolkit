import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import FieldType

_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TRANSFORM_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class NullPolicy(StrEnum):
    """How a mapped target handles a null source value."""

    ALLOW = "allow"
    REJECT = "reject"
    DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class TransformSpec:
    """A named, data-only transformation invocation."""

    name: str = "identity"
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = self.name.strip().casefold()
        if not _TRANSFORM_NAME.fullmatch(normalized):
            raise ValueError("invalid transformation name")
        object.__setattr__(self, "name", normalized)
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType(dict(self.parameters)),
        )


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """One source field projected into a typed target field."""

    source_field: str
    target_field: str
    target_type: FieldType
    required: bool = False
    null_policy: NullPolicy = NullPolicy.ALLOW
    default: object | None = None
    transform: TransformSpec = field(default_factory=TransformSpec)

    def __post_init__(self) -> None:
        for attribute in ("source_field", "target_field"):
            normalized = getattr(self, attribute).strip()
            if not _FIELD_NAME.fullmatch(normalized):
                raise ValueError(f"invalid {attribute}")
            object.__setattr__(self, attribute, normalized)
        if self.required and self.null_policy is NullPolicy.ALLOW:
            raise ValueError("required field cannot allow null values")
        if self.null_policy is NullPolicy.DEFAULT and self.default is None:
            raise ValueError("default null policy requires a default value")


@dataclass(frozen=True, slots=True)
class DatasetMapping:
    """Complete field projection for one source and target dataset pair."""

    source_dataset: DatasetId
    target_dataset: DatasetId
    fields: tuple[FieldMapping, ...]

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("dataset mapping must contain at least one field")
        target_fields = [mapping.target_field.casefold() for mapping in self.fields]
        if len(target_fields) != len(set(target_fields)):
            raise ValueError("duplicate target field")


@dataclass(frozen=True, slots=True)
class ReferenceTable:
    """A versioned, immutable collection of dataset mappings."""

    schema_version: Literal[1]
    datasets: tuple[DatasetMapping, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not self.datasets:
            raise ValueError("reference table must contain at least one dataset")
        sources = [str(mapping.source_dataset).casefold() for mapping in self.datasets]
        if len(sources) != len(set(sources)):
            raise ValueError("duplicate source dataset")

    def dataset(self, source_dataset: DatasetId | str) -> DatasetMapping | None:
        """Find a dataset mapping by normalized source identifier."""

        normalized = DatasetId(str(source_dataset))
        return next(
            (
                mapping
                for mapping in self.datasets
                if mapping.source_dataset == normalized
            ),
            None,
        )
