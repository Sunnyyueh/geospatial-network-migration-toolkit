from dataclasses import dataclass
from enum import StrEnum

from un_migration.domain.identity import DatasetId


class FieldType(StrEnum):
    """Portable field types used by inventories and mappings."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    JSON = "json"
    GEOMETRY = "geometry"


class GeometryType(StrEnum):
    """Portable geometry categories."""

    POINT = "point"
    MULTIPOINT = "multipoint"
    POLYLINE = "polyline"
    POLYGON = "polygon"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DomainValue:
    """One coded value and its display label."""

    code: str | int
    label: str

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("domain value label must not be empty")


@dataclass(frozen=True, slots=True)
class CodedDomain:
    """A named set of unique coded values."""

    name: str
    values: tuple[DomainValue, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("domain name must not be empty")
        codes = [value.code for value in self.values]
        if len(codes) != len(set(codes)):
            raise ValueError(f"duplicate domain code in {self.name!r}")


@dataclass(frozen=True, slots=True)
class FieldSchema:
    """Portable field metadata."""

    name: str
    type: FieldType
    nullable: bool = True
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    domain: CodedDomain | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("field name must not be empty")
        for label, value in (
            ("length", self.length),
            ("precision", self.precision),
            ("scale", self.scale),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} must be nonnegative")
        if (
            self.scale is not None
            and self.precision is not None
            and self.scale > self.precision
        ):
            raise ValueError("scale must not exceed precision")


@dataclass(frozen=True, slots=True)
class GeometrySchema:
    """Portable geometry metadata."""

    type: GeometryType
    spatial_reference: str | None = None
    has_z: bool = False
    has_m: bool = False

    def __post_init__(self) -> None:
        if self.spatial_reference is not None and not self.spatial_reference.strip():
            raise ValueError("spatial_reference must not be empty")


@dataclass(frozen=True, slots=True)
class DatasetRef:
    """Logical and physical identity for a dataset."""

    id: DatasetId
    physical_name: str

    def __post_init__(self) -> None:
        if not self.physical_name.strip():
            raise ValueError("physical_name must not be empty")


@dataclass(frozen=True, slots=True)
class DatasetInventory:
    """Observed portable schema and record count for one dataset."""

    dataset: DatasetRef
    fields: tuple[FieldSchema, ...]
    feature_count: int
    geometry: GeometrySchema | None = None

    def __post_init__(self) -> None:
        if self.feature_count < 0:
            raise ValueError("feature_count must be nonnegative")
        names = [field.name.casefold() for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("duplicate field name")

    def field(self, name: str) -> FieldSchema | None:
        """Look up a field by case-insensitive name."""

        normalized = name.casefold()
        return next(
            (field for field in self.fields if field.name.casefold() == normalized),
            None,
        )
