import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from un_migration.cli import app

runner = CliRunner()


def write_project(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    (data / "water_mains.csv").write_text(
        "asset_id,diameter,active\nWM-001,12,true\nWM-002,6,false\n",
        encoding="utf-8",
    )
    project = {
        "config_version": 1,
        "project_name": "Filter validation",
        "source": {
            "adapter": {"kind": "csv", "options": {}},
            "workspace": str(data),
            "datasets": [{"id": "water-mains", "path": "water_mains.csv"}],
        },
        "target": {
            "adapter": {"kind": "filesystem", "options": {}},
            "workspace": str(tmp_path / "staging"),
        },
    }
    path = tmp_path / "project.yml"
    path.write_text(yaml.safe_dump(project), encoding="utf-8")
    return path


def test_filter_validate_checks_configured_source_inventory(tmp_path: Path) -> None:
    project = write_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "filter",
            "validate",
            "active = true AND diameter >= 8",
            "--config",
            str(project),
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "dataset": "water-mains",
        "normalized": "active = TRUE AND diameter >= 8",
        "valid": True,
    }


def test_filter_validate_rejects_unknown_inventory_field(tmp_path: Path) -> None:
    project = write_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "filter",
            "validate",
            "missing = 1",
            "--config",
            str(project),
            "--json",
        ],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "filter.unknown-field"


def test_filter_validate_rejects_invalid_syntax(tmp_path: Path) -> None:
    project = write_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "filter",
            "validate",
            "diameter == 8",
            "--config",
            str(project),
            "--json",
        ],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "filter.syntax"


def test_filter_explain_emits_sql_and_arcpy_preview() -> None:
    result = runner.invoke(
        app,
        [
            "filter",
            "explain",
            "active = true AND diameter >= 8",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["normalized"] == "active = TRUE AND diameter >= 8"
    assert payload["sql"] == {
        "text": '"active" = ? AND "diameter" >= ?',
        "parameters": [True, 8],
    }
    assert payload["arcpy"] == {
        "preview": True,
        "text": "[active] = 1 AND [diameter] >= 8",
    }


def test_filter_explain_resolves_json_parameters_without_sql_interpolation() -> None:
    result = runner.invoke(
        app,
        [
            "filter",
            "explain",
            "asset_id = :asset",
            "--parameters-json",
            '{"asset":"O\'Brien"}',
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sql"]["text"] == '"asset_id" = ?'
    assert payload["sql"]["parameters"] == ["O'Brien"]
    assert "O'Brien" not in payload["sql"]["text"]
    assert payload["arcpy"]["text"] == "[asset_id] = 'O''Brien'"


def test_filter_explain_rejects_non_object_parameters() -> None:
    result = runner.invoke(
        app,
        [
            "filter",
            "explain",
            "diameter = :value",
            "--parameters-json",
            "[]",
            "--json",
        ],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "filter.parameters"
