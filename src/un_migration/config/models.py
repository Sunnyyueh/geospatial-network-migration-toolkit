from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    """Frozen boundary model that rejects unknown configuration keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AdapterConfig(StrictModel):
    """Adapter kind and backend-specific JSON options."""

    kind: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    options: dict[str, JsonValue] = Field(default_factory=dict)


class DatasetConfig(StrictModel):
    """One logical source dataset and its managed workspace-relative path."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,127}$")
    path: Path
    geometry_field: str | None = None

    @field_validator("path")
    @classmethod
    def require_relative_path(cls, value: Path) -> Path:
        if value.is_absolute() or ".." in value.parts or value == Path("."):
            raise ValueError("dataset path must be managed and relative")
        return value

    @field_validator("geometry_field")
    @classmethod
    def normalize_geometry_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("geometry_field must not be empty")
        return normalized


class SourceConfig(StrictModel):
    """Source adapter, workspace, and ordered logical datasets."""

    adapter: AdapterConfig
    workspace: Path
    datasets: tuple[DatasetConfig, ...]

    @model_validator(mode="after")
    def unique_dataset_ids(self) -> Self:
        ids = [dataset.id for dataset in self.datasets]
        if not ids:
            raise ValueError("source datasets must not be empty")
        if len(ids) != len(set(ids)):
            raise ValueError("source dataset IDs must be unique")
        return self


class TargetConfig(StrictModel):
    """Target adapter and staging workspace."""

    adapter: AdapterConfig
    workspace: Path


class ReportingConfig(StrictModel):
    """Artifact directory and requested report formats."""

    output_directory: Path = Path("outputs")
    formats: tuple[Literal["json", "csv", "markdown", "html"], ...] = ("json",)

    @field_validator("formats")
    @classmethod
    def require_unique_formats(
        cls,
        value: tuple[Literal["json", "csv", "markdown", "html"], ...],
    ) -> tuple[Literal["json", "csv", "markdown", "html"], ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("reporting formats must be nonempty and unique")
        return value


class RuntimeConfig(StrictModel):
    """Portable execution controls."""

    batch_size: int = Field(default=1000, ge=1, le=100_000)


class ProjectConfig(StrictModel):
    """Fully validated configuration for one migration project."""

    config_version: Literal[1]
    project_name: str
    source: SourceConfig
    target: TargetConfig
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    @field_validator("project_name")
    @classmethod
    def normalize_project_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("project_name must not be empty")
        return normalized
