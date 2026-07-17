import json
from pathlib import Path

import pytest
import yaml

from un_migration.config.loader import load_config
from un_migration.domain.errors import ConfigurationError


def valid_project() -> dict[str, object]:
    return {
        "config_version": 1,
        "project_name": "Synthetic water migration",
        "source": {
            "adapter": {"kind": "csv", "options": {}},
            "workspace": "${SOURCE_PATH}",
            "datasets": [{"id": "water-mains", "path": "water_mains.csv"}],
        },
        "target": {
            "adapter": {"kind": "filesystem", "options": {}},
            "workspace": "outputs/staging",
        },
    }


def test_yaml_and_json_load_to_equal_configs(tmp_path: Path) -> None:
    value = valid_project()
    yaml_path = tmp_path / "project.yml"
    json_path = tmp_path / "project.json"
    yaml_path.write_text(yaml.safe_dump(value), encoding="utf-8")
    json_path.write_text(json.dumps(value), encoding="utf-8")
    environ = {"SOURCE_PATH": str(tmp_path / "source")}

    yaml_config = load_config(yaml_path, environ)
    json_config = load_config(json_path, environ)

    assert yaml_config == json_config
    assert yaml_config.source.workspace == tmp_path / "source"


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("project.toml", "config_version = 1", "config.unsupported-format"),
        ("project.yml", "source: [", "config.parse"),
        ("project.json", "[]", "config.root"),
        ("project.yml", "config_version: 1", "config.invalid"),
    ],
)
def test_loader_translates_failures_to_stable_errors(
    tmp_path: Path,
    filename: str,
    content: str,
    code: str,
) -> None:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigurationError) as raised:
        load_config(path, {})

    assert raised.value.code == code


def test_missing_config_uses_not_found_code(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as raised:
        load_config(tmp_path / "missing.yml", {})

    assert raised.value.code == "config.not-found"


def test_missing_environment_value_is_preserved_as_typed_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "project.yml"
    path.write_text(yaml.safe_dump(valid_project()), encoding="utf-8")

    with pytest.raises(ConfigurationError) as raised:
        load_config(path, {})

    assert raised.value.code == "environment.missing"
