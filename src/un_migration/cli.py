import importlib.util
import json
import os
import platform
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, cast

import typer

from un_migration.adapters.filesystem import CsvSourceReader
from un_migration.api import package_info
from un_migration.config.loader import load_config
from un_migration.config.models import ProjectConfig
from un_migration.config.render import (
    project_config_schema,
    render_config,
    render_schema,
)
from un_migration.domain.errors import (
    CapabilityError,
    ConfigurationError,
    FilterSyntaxError,
    MappingError,
    MigrationError,
)
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import DatasetInventory, DatasetRef
from un_migration.domain.serialization import canonical_json
from un_migration.filters import (
    SqlDialect,
    compile_arcpy,
    compile_sql,
    normalize,
    parse_filter,
    validate_filter_fields,
)
from un_migration.inventory import InventoryService
from un_migration.mapping import load_reference, normalize_reference

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Plan, run, validate, and document geospatial network migrations.",
)
config_app = typer.Typer(
    no_args_is_help=True,
    help="Validate and inspect project configuration.",
)
app.add_typer(config_app, name="config")
inventory_app = typer.Typer(
    no_args_is_help=True,
    help="Inspect and compare dataset inventories.",
)
app.add_typer(inventory_app, name="inventory")
reference_app = typer.Typer(
    no_args_is_help=True,
    help="Validate and normalize source-to-target reference tables.",
)
app.add_typer(reference_app, name="reference")
filter_app = typer.Typer(
    no_args_is_help=True,
    help="Validate and explain safe source filters.",
)
app.add_typer(filter_app, name="filter")

JsonOption = Annotated[
    bool,
    typer.Option("--json", help="Emit machine-readable JSON."),
]
OutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Write normalized output to this path."),
]
ConfigOption = Annotated[
    Path,
    typer.Option("--config", help="Project configuration used for inventory."),
]
DatasetOption = Annotated[
    str | None,
    typer.Option("--dataset", help="Configured source dataset ID."),
]
ParametersOption = Annotated[
    str,
    typer.Option(
        "--parameters-json",
        help="JSON object containing named filter parameter values.",
    ),
]


def _write(payload: Mapping[str, object], as_json: bool) -> None:
    if as_json:
        typer.echo(canonical_json(payload))
        return
    for key, value in payload.items():
        typer.echo(f"{key}: {value}")


def _load_or_exit(path: Path, as_json: bool) -> ProjectConfig:
    try:
        return load_config(path)
    except ConfigurationError as error:
        _write({"valid": False, "error": error.to_dict()}, as_json)
        raise typer.Exit(code=2) from None


def _exit_error(
    error: MigrationError,
    as_json: bool,
    *,
    valid: bool | None = None,
    code: int = 2,
) -> None:
    payload: dict[str, object] = {"error": error.to_dict()}
    if valid is not None:
        payload["valid"] = valid
    _write(payload, as_json)
    raise typer.Exit(code=code)


@app.callback()
def main(context: typer.Context) -> None:
    """Plan, run, validate, and document geospatial network migrations."""

    if context.invoked_subcommand is None:
        typer.echo(context.get_help())


@app.command()
def version(as_json: JsonOption = False) -> None:
    """Show package and Python runtime information."""

    _write(package_info().to_dict(), as_json)


@app.command()
def doctor(as_json: JsonOption = False) -> None:
    """Check portable runtime requirements and optional ArcPy availability."""

    python_supported = sys.version_info >= (3, 11)
    working_directory_writable = os.access(Path.cwd(), os.W_OK)
    arcpy_available = importlib.util.find_spec("arcpy") is not None
    payload: dict[str, object] = {
        "python": {
            "version": platform.python_version(),
            "supported": python_supported,
        },
        "working_directory": {"writable": working_directory_writable},
        "arcpy": {"available": arcpy_available, "required": False},
    }
    _write(payload, as_json)
    if not python_supported or not working_directory_writable:
        raise typer.Exit(code=1)


@config_app.command("validate")
def config_validate(
    path: Path,
    as_json: JsonOption = False,
) -> None:
    """Validate a YAML or JSON project configuration."""

    config = _load_or_exit(path, as_json)
    _write(
        {
            "valid": True,
            "project_name": config.project_name,
        },
        as_json,
    )


@config_app.command("render")
def config_render(path: Path) -> None:
    """Render a resolved project configuration with secrets redacted."""

    config = _load_or_exit(path, True)
    typer.echo(render_config(config))


@config_app.command("schema")
def config_schema(as_json: JsonOption = False) -> None:
    """Print the generated ProjectConfig JSON Schema."""

    if as_json:
        typer.echo(canonical_json(project_config_schema()))
        return
    typer.echo(render_schema(), nl=False)


def _inventory_payload(
    inventory: DatasetInventory,
    checksum_algorithm: str,
    checksum_digest: str,
) -> dict[str, object]:
    geometry: dict[str, object] | None = None
    if inventory.geometry is not None:
        geometry = {
            "type": inventory.geometry.type.value,
            "spatial_reference": inventory.geometry.spatial_reference,
            "has_z": inventory.geometry.has_z,
            "has_m": inventory.geometry.has_m,
        }
    return {
        "dataset": {
            "id": str(inventory.dataset.id),
            "physical_name": inventory.dataset.physical_name,
        },
        "fields": [
            {
                "name": field.name,
                "type": field.type.value,
                "nullable": field.nullable,
                "length": field.length,
                "precision": field.precision,
                "scale": field.scale,
            }
            for field in inventory.fields
        ],
        "feature_count": inventory.feature_count,
        "geometry": geometry,
        "fingerprint": {
            "algorithm": checksum_algorithm,
            "digest": checksum_digest,
        },
    }


@inventory_app.command("source")
def inventory_source(
    path: Path,
    as_json: JsonOption = False,
) -> None:
    """Collect deterministic source dataset inventory."""

    config = _load_or_exit(path, as_json)
    if config.source.adapter.kind != "csv":
        error = CapabilityError(
            code="adapter.unsupported",
            message=(f"Source adapter is not available: {config.source.adapter.kind}"),
            guidance="Use the csv adapter for this release slice.",
        )
        _write({"error": error.to_dict()}, as_json)
        raise typer.Exit(code=4)

    source = CsvSourceReader(
        config.source.workspace,
        config.source.datasets,
    )
    datasets = tuple(
        DatasetRef(DatasetId(item.id), item.path.as_posix())
        for item in config.source.datasets
    )
    result = InventoryService(source).collect(datasets)
    payload = {
        "adapter": {
            "name": result.adapter.adapter_name,
            "operations": sorted(result.adapter.operations),
        },
        "datasets": [
            _inventory_payload(
                inventory,
                result.fingerprints[inventory.dataset.id].algorithm,
                result.fingerprints[inventory.dataset.id].digest,
            )
            for inventory in result.inventories
        ],
    }
    _write(payload, as_json)


@reference_app.command("validate")
def reference_validate(
    path: Path,
    as_json: JsonOption = False,
) -> None:
    """Validate a version 1 source-to-target reference table."""

    try:
        table = load_reference(path)
    except MappingError as error:
        _exit_error(error, as_json, valid=False)
        return
    _write(
        {
            "valid": True,
            "schema_version": table.schema_version,
            "dataset_count": len(table.datasets),
            "field_count": sum(len(dataset.fields) for dataset in table.datasets),
        },
        as_json,
    )


@reference_app.command("normalize")
def reference_normalize(
    path: Path,
    output: OutputOption = None,
) -> None:
    """Render a reference table as deterministic version 1 CSV."""

    try:
        normalized = normalize_reference(load_reference(path))
        if output is None:
            typer.echo(normalized, nl=False)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(normalized, encoding="utf-8")
    except MappingError as error:
        _exit_error(error, False, valid=False)
        return
    except OSError:
        _exit_error(
            MappingError(
                code="reference.write",
                message=f"Normalized reference table could not be written: {output}.",
                guidance="Select a writable managed output path.",
            ),
            False,
            valid=False,
        )
        return
    _write({"normalized": str(output)}, False)


def _configured_inventory(
    config_path: Path,
    dataset_name: str | None,
    as_json: bool,
) -> DatasetInventory:
    config = _load_or_exit(config_path, as_json)
    if config.source.adapter.kind != "csv":
        raise CapabilityError(
            code="adapter.unsupported",
            message=f"Source adapter is not available: {config.source.adapter.kind}",
            guidance="Use the csv adapter for portable filter validation.",
        )
    if dataset_name is None:
        if len(config.source.datasets) != 1:
            raise FilterSyntaxError(
                code="filter.dataset-required",
                message="A source dataset must be selected for filter validation.",
                guidance="Pass --dataset with one configured source dataset ID.",
            )
        selected = config.source.datasets[0]
    else:
        try:
            normalized_id = DatasetId(dataset_name)
        except ValueError as error:
            raise FilterSyntaxError(
                code="filter.dataset",
                message=f"Invalid source dataset ID: {dataset_name!r}.",
                guidance="Use a normalized configured source dataset ID.",
            ) from error
        selected_candidate = next(
            (
                item
                for item in config.source.datasets
                if DatasetId(item.id) == normalized_id
            ),
            None,
        )
        if selected_candidate is None:
            raise FilterSyntaxError(
                code="filter.dataset",
                message=f"Source dataset is not configured: {normalized_id}.",
                guidance="Select a dataset listed in source.datasets.",
            )
        selected = selected_candidate
    reader = CsvSourceReader(config.source.workspace, config.source.datasets)
    reference = DatasetRef(DatasetId(selected.id), selected.path.as_posix())
    return reader.inventory(reference)


@filter_app.command("validate")
def filter_validate(
    expression: str,
    config_path: ConfigOption,
    dataset: DatasetOption = None,
    as_json: JsonOption = False,
) -> None:
    """Parse a filter and validate it against configured source inventory."""

    try:
        parsed = parse_filter(expression)
        inventory = _configured_inventory(config_path, dataset, as_json)
        validate_filter_fields(parsed, inventory)
    except MigrationError as error:
        _exit_error(error, as_json, valid=False)
        return
    _write(
        {
            "valid": True,
            "dataset": str(inventory.dataset.id),
            "normalized": normalize(parsed),
        },
        as_json,
    )


def _parameters(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise FilterSyntaxError(
            code="filter.parameters",
            message="Filter parameters are not valid JSON.",
            guidance="Provide a JSON object with string keys.",
        ) from error
    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise FilterSyntaxError(
            code="filter.parameters",
            message="Filter parameters must be a JSON object.",
            guidance="Provide named parameter values under string keys.",
        )
    return cast(dict[str, object], parsed)


@filter_app.command("explain")
def filter_explain(
    expression: str,
    parameters_json: ParametersOption = "{}",
    as_json: JsonOption = False,
) -> None:
    """Explain portable, SQL, and ArcPy representations of one filter."""

    try:
        parameters = _parameters(parameters_json)
        parsed = parse_filter(expression)
        sql = compile_sql(parsed, SqlDialect(), parameters)
        arcpy = compile_arcpy(parsed, lambda name: f"[{name}]", parameters)
    except MigrationError as error:
        _exit_error(error, as_json, valid=False)
        return
    _write(
        {
            "normalized": normalize(parsed),
            "sql": {
                "text": sql.text,
                "parameters": sql.parameters,
            },
            "arcpy": {
                "text": arcpy,
                "preview": True,
            },
        },
        as_json,
    )


if __name__ == "__main__":
    app()
