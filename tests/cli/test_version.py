import json

from typer.testing import CliRunner

from un_migration.cli import app

runner = CliRunner()


def test_version_json_is_machine_readable() -> None:
    result = runner.invoke(app, ["version", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "geospatial-network-migration-toolkit"
    assert payload["version"] == "0.1.0"
    assert payload["python"]
    assert payload["platform"]


def test_version_human_output_is_readable() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "name: geospatial-network-migration-toolkit" in result.stdout
    assert "version: 0.1.0" in result.stdout
