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

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Plan, run, validate, and document geospatial network migrations.",
)

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


if __name__ == "__main__":
    app()
