import json
from pathlib import Path

from un_migration.config.models import ProjectConfig
from un_migration.config.render import (
    project_config_schema,
    render_config,
    render_schema,
)


def project_with_secret() -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "config_version": 1,
            "project_name": "Synthetic water migration",
            "source": {
                "adapter": {
                    "kind": "csv",
                    "options": {"token": "source-secret", "encoding": "utf-8"},
                },
                "workspace": "examples/data",
                "datasets": [{"id": "water-mains", "path": "water_mains.csv"}],
            },
            "target": {
                "adapter": {
                    "kind": "filesystem",
                    "options": {"client_secret": "target-secret"},
                },
                "workspace": "outputs/staging",
            },
        }
    )


def test_schema_forbids_unknown_properties_and_fixes_version() -> None:
    schema = project_config_schema()

    assert schema["additionalProperties"] is False
    assert "config_version" in schema["required"]
    properties = schema["properties"]
    assert properties["config_version"]["const"] == 1


def test_checked_in_schema_matches_generated_text() -> None:
    path = Path("schemas/project-config.schema.json")

    assert path.read_text(encoding="utf-8") == render_schema()


def test_render_config_redacts_default_secret_keys() -> None:
    rendered = json.loads(render_config(project_with_secret()))

    assert rendered["source"]["adapter"]["options"] == {
        "encoding": "utf-8",
        "token": "***REDACTED***",
    }
    assert rendered["target"]["adapter"]["options"]["client_secret"] == (
        "***REDACTED***"
    )
    assert "source-secret" not in json.dumps(rendered)
    assert "target-secret" not in json.dumps(rendered)


def test_render_config_is_canonical_and_ends_without_newline() -> None:
    rendered = render_config(project_with_secret())

    assert rendered.startswith('{"config_version":1,')
    assert not rendered.endswith("\n")
