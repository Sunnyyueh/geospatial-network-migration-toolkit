import importlib.util
import json
import os
import platform
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer

from un_migration.api import package_info
from un_migration.config.loader import load_config
from un_migration.config.models import ProjectConfig
from un_migration.config.render import (
    project_config_schema,
    render_config,
    render_schema,
)
from un_migration.domain.errors import ConfigurationError
from un_migration.domain.serialization import canonical_json

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

JsonOption = Annotated[
    bool,
    typer.Option("--json", help="Emit machine-readable JSON."),
]


def _write(payload: Mapping[str, object], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, sort_keys=True))
        return
    for key, value in payload.items():
        typer.echo(f"{key}: {value}")


def _load_or_exit(path: Path, as_json: bool) -> ProjectConfig:
    try:
        return load_config(path)
    except ConfigurationError as error:
        _write({"valid": False, "error": error.to_dict()}, as_json)
        raise typer.Exit(code=2) from None


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


if __name__ == "__main__":
    app()
