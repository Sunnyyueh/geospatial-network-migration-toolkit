import json
from typing import cast

from un_migration.config.environment import redact_secrets
from un_migration.config.models import ProjectConfig
from un_migration.domain.serialization import canonical_json

DEFAULT_SECRET_KEYS = frozenset({"token", "password", "api_key", "client_secret"})


def project_config_schema() -> dict[str, object]:
    """Return the generated JSON Schema for ProjectConfig."""

    return cast(dict[str, object], ProjectConfig.model_json_schema())


def render_schema() -> str:
    """Render the generated schema as deterministic checked-in JSON."""

    return (
        json.dumps(
            project_config_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def render_config(
    config: ProjectConfig,
    secret_keys: frozenset[str] = DEFAULT_SECRET_KEYS,
) -> str:
    """Render a resolved configuration without configured secret values."""

    safe = redact_secrets(
        config.model_dump(mode="json"),
        secret_keys,
    )
    return canonical_json(safe)
