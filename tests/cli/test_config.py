import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from un_migration.cli import app

runner = CliRunner()


def valid_project(*, include_secret: bool = False) -> dict[str, object]:
    options = {"token": "source-secret"} if include_secret else {}
    return {
        "config_version": 1,
        "project_name": "Synthetic water migration",
        "source": {
            "adapter": {"kind": "csv", "options": options},
            "workspace": "examples/data",
            "datasets": [{"id": "water-mains", "path": "water_mains.csv"}],
        },
        "target": {
            "adapter": {"kind": "filesystem", "options": {}},
            "workspace": "outputs/staging",
        },
    }


def write_project(directory: Path, value: dict[str, object]) -> Path:
    path = directory / "project.yml"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    return path


def test_config_validate_emits_machine_readable_success(tmp_path: Path) -> None:
    path = write_project(tmp_path, valid_project())
    result = runner.invoke(app, ["config", "validate", str(path), "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "project_name": "Synthetic water migration",
        "valid": True,
    }


def test_config_validate_emits_safe_error_and_exit_two(tmp_path: Path) -> None:
    path = write_project(tmp_path, {"config_version": 1})
    result = runner.invoke(app, ["config", "validate", str(path), "--json"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["error"]["code"] == "config.invalid"
    assert "Traceback" not in result.stdout


def test_config_render_emits_canonical_redacted_json(tmp_path: Path) -> None:
    path = write_project(tmp_path, valid_project(include_secret=True))
    result = runner.invoke(app, ["config", "render", str(path)])

    assert result.exit_code == 0
    assert "source-secret" not in result.stdout
    assert "***REDACTED***" in result.stdout
    assert result.stdout.startswith('{"config_version":1,')


def test_config_schema_supports_compact_json() -> None:
    result = runner.invoke(app, ["config", "schema", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["title"] == "ProjectConfig"
    assert payload["additionalProperties"] is False
