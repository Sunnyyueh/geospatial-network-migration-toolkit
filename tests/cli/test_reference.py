import json
from pathlib import Path

from typer.testing import CliRunner

from un_migration.cli import app
from un_migration.mapping.reference import load_reference, normalize_reference

runner = CliRunner()

EXAMPLE = Path("examples/mappings/water_reference.csv")


def test_reference_validate_reports_dataset_and_field_counts() -> None:
    result = runner.invoke(
        app,
        ["reference", "validate", str(EXAMPLE), "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "dataset_count": 1,
        "field_count": 3,
        "schema_version": 1,
        "valid": True,
    }


def test_reference_validate_emits_safe_error_and_exit_two(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.csv"
    invalid.write_text(
        "schema_version,source_dataset\n2,water-mains\n", encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["reference", "validate", str(invalid), "--json"],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["error"]["code"] == "reference.header"
    assert "Traceback" not in result.stdout


def test_reference_normalize_emits_canonical_csv() -> None:
    result = runner.invoke(app, ["reference", "normalize", str(EXAMPLE)])

    assert result.exit_code == 0
    assert result.stdout == normalize_reference(load_reference(EXAMPLE))


def test_reference_normalize_can_write_output_file(tmp_path: Path) -> None:
    output = tmp_path / "normalized.csv"

    result = runner.invoke(
        app,
        [
            "reference",
            "normalize",
            str(EXAMPLE),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == f"normalized: {output}"
    assert normalize_reference(load_reference(output)) == output.read_text(
        encoding="utf-8"
    )
