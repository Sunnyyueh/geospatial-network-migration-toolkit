from pathlib import Path

import pytest
from pydantic import ValidationError

from un_migration.config.models import ProjectConfig


def valid_project() -> dict[str, object]:
    return {
        "config_version": 1,
        "project_name": "Synthetic water migration",
        "source": {
            "adapter": {"kind": "csv", "options": {}},
            "workspace": "examples/data",
            "datasets": [{"id": "water-mains", "path": "water_mains.csv"}],
        },
        "target": {
            "adapter": {"kind": "filesystem", "options": {}},
            "workspace": "outputs/staging",
        },
    }


def test_project_config_validates_portable_minimum() -> None:
    config = ProjectConfig.model_validate(valid_project())

    assert config.config_version == 1
    assert config.project_name == "Synthetic water migration"
    assert config.runtime.batch_size == 1000
    assert config.reporting.formats == ("json",)
    assert config.source.datasets[0].id == "water-mains"
    assert config.source.datasets[0].path == Path("water_mains.csv")


def test_unknown_key_is_rejected() -> None:
    value = valid_project()
    value["mystery"] = True

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProjectConfig.model_validate(value)


def test_configuration_version_is_exact() -> None:
    value = valid_project()
    value["config_version"] = 2

    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(value)


def test_source_dataset_ids_must_be_unique() -> None:
    value = valid_project()
    source = value["source"]
    assert isinstance(source, dict)
    source["datasets"] = [
        {"id": "water-mains", "path": "water_mains.csv"},
        {"id": "water-mains", "path": "water_mains_2.csv"},
    ]

    with pytest.raises(ValidationError, match="unique"):
        ProjectConfig.model_validate(value)


@pytest.mark.parametrize("path", ["/private/data.csv", "../private/data.csv"])
def test_dataset_path_must_be_managed_and_relative(path: str) -> None:
    value = valid_project()
    source = value["source"]
    assert isinstance(source, dict)
    source["datasets"] = [{"id": "water-mains", "path": path}]

    with pytest.raises(ValidationError, match="managed and relative"):
        ProjectConfig.model_validate(value)


def test_runtime_batch_size_must_be_positive() -> None:
    value = valid_project()
    value["runtime"] = {"batch_size": 0}

    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(value)


def test_project_name_is_trimmed_and_nonempty() -> None:
    value = valid_project()
    value["project_name"] = "  Water migration  "

    assert ProjectConfig.model_validate(value).project_name == "Water migration"

    value["project_name"] = " "
    with pytest.raises(ValidationError, match="project_name"):
        ProjectConfig.model_validate(value)
