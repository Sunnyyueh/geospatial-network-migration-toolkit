import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from un_migration.cli import app

runner = CliRunner()

REFERENCE = (
    "schema_version,source_dataset,target_dataset,source_field,target_field,"
    "target_type,required,null_policy,default,transform,transform_parameters\n"
    "1,water-mains,utility-lines,asset_id,asset_identifier,string,true,reject,,"
    "uppercase,{}\n"
    "1,water-mains,utility-lines,diameter,diameter_mm,integer,false,allow,,"
    "identity,{}\n"
)


def inputs(tmp_path: Path, rows: str) -> tuple[Path, Path, Path]:
    data = tmp_path / "data"
    data.mkdir()
    (data / "water.csv").write_text(
        "asset_id,diameter,active\n" + rows,
        encoding="utf-8",
    )
    output = tmp_path / "outputs"
    project = {
        "config_version": 1,
        "project_name": "Portable run test",
        "source": {
            "adapter": {"kind": "csv", "options": {}},
            "workspace": str(data),
            "datasets": [{"id": "water-mains", "path": "water.csv"}],
        },
        "target": {
            "adapter": {"kind": "filesystem", "options": {}},
            "workspace": str(output / "staging"),
        },
        "reporting": {
            "output_directory": str(output),
            "formats": ["json", "csv", "markdown", "html"],
        },
        "runtime": {"batch_size": 1},
    }
    config = tmp_path / "project.yml"
    config.write_text(yaml.safe_dump(project), encoding="utf-8")
    reference = tmp_path / "reference.csv"
    reference.write_text(REFERENCE, encoding="utf-8")
    return config, reference, output


def invoke_run(
    config: Path,
    reference: Path,
    *options: str,
) -> object:
    return runner.invoke(
        app,
        [
            "run",
            "portable",
            str(config),
            str(reference),
            "--run-id",
            "test-run",
            *options,
            "--json",
        ],
    )


def test_portable_run_creates_complete_accepted_artifact_layout(
    tmp_path: Path,
) -> None:
    config, reference, output = inputs(tmp_path, "wm-1,4,true\nwm-2,6,false\n")

    result = invoke_run(config, reference)

    assert result.exit_code == 0  # type: ignore[attr-defined]
    payload = json.loads(result.stdout)  # type: ignore[attr-defined]
    assert payload["acceptance"] == "accepted"
    assert payload["metrics"] == {
        "rejected": 0,
        "selected": 2,
        "staged": 2,
        "transformed": 2,
        "validated": 2,
    }
    paths = set(payload["artifact_paths"])
    assert "test-run/staging/utility-lines.csv" in paths
    assert "test-run/reports/summary.html" in paths
    assert "test-run/manifests/run.json" in paths
    assert "test-run/review/index.json" in paths
    assert (output / "test-run/staging/utility-lines.csv").is_file()
    assert (output / "outbox").is_dir()


def test_portable_run_applies_filter_before_transformation(tmp_path: Path) -> None:
    config, reference, _ = inputs(tmp_path, "wm-1,4,true\nwm-2,6,false\n")

    result = invoke_run(config, reference, "--filter", "active = true")

    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert json.loads(result.stdout)["metrics"]["selected"] == 1  # type: ignore[attr-defined]


def test_portable_run_rejected_null_returns_three_with_evidence(
    tmp_path: Path,
) -> None:
    config, reference, output = inputs(tmp_path, ",4,true\nwm-2,6,false\n")

    result = invoke_run(config, reference)

    assert result.exit_code == 3  # type: ignore[attr-defined]
    payload = json.loads(result.stdout)  # type: ignore[attr-defined]
    assert payload["acceptance"] == "rejected"
    assert payload["metrics"]["rejected"] == 1
    assert (output / "test-run/reports/findings.csv").is_file()


def test_portable_run_refuses_to_overwrite_existing_run(tmp_path: Path) -> None:
    config, reference, _ = inputs(tmp_path, "wm-1,4,true\n")
    first = invoke_run(config, reference)

    second = invoke_run(config, reference)

    assert first.exit_code == 0  # type: ignore[attr-defined]
    assert second.exit_code == 2  # type: ignore[attr-defined]
    assert json.loads(second.stdout)["error"]["code"] == "staging.run-exists"  # type: ignore[attr-defined]
