import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from un_migration.cli import app

runner = CliRunner()


def write_project(tmp_path: Path, adapter: str = "csv") -> Path:
    data = tmp_path / "data"
    data.mkdir()
    (data / "water_mains.csv").write_text(
        "asset_id,diameter\nWM-001,12\nWM-002,8\n",
        encoding="utf-8",
    )
    project = {
        "config_version": 1,
        "project_name": "Synthetic water migration",
        "source": {
            "adapter": {"kind": adapter, "options": {}},
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


def test_inventory_source_emits_complete_json(tmp_path: Path) -> None:
    project = write_project(tmp_path)

    result = runner.invoke(
        app,
        ["inventory", "source", str(project), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["adapter"]["name"] == "csv"
    assert payload["adapter"]["operations"] == ["count", "filter", "inventory", "read"]
    dataset = payload["datasets"][0]
    assert dataset["dataset"]["id"] == "water-mains"
    assert dataset["feature_count"] == 2
    assert dataset["fields"][1]["name"] == "diameter"
    assert dataset["fields"][1]["type"] == "integer"
    assert len(dataset["fingerprint"]["digest"]) == 64


def test_inventory_source_rejects_unsupported_adapter(tmp_path: Path) -> None:
    project = write_project(tmp_path, adapter="arcpy")

    result = runner.invoke(
        app,
        ["inventory", "source", str(project), "--json"],
    )

    assert result.exit_code == 4
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "adapter.unsupported"
