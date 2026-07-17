import json

from typer.testing import CliRunner

from un_migration.cli import app

runner = CliRunner()


def test_doctor_reports_arcpy_as_optional() -> None:
    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["python"]["supported"] is True
    assert payload["working_directory"]["writable"] is True
    assert payload["arcpy"]["required"] is False
    assert isinstance(payload["arcpy"]["available"], bool)


def test_no_command_displays_help() -> None:
    result = runner.invoke(app)

    assert result.exit_code == 0
    assert "Plan, run, validate" in result.stdout
    assert "doctor" in result.stdout
