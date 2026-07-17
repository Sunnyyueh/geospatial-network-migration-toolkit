import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError

from un_migration.config.environment import interpolate_environment
from un_migration.config.models import ProjectConfig
from un_migration.domain.errors import ConfigurationError

_YAML_SUFFIXES = frozenset({".yaml", ".yml"})


def _error(code: str, message: str, guidance: str) -> ConfigurationError:
    return ConfigurationError(
        code=code,
        message=message,
        guidance=guidance,
    )


def load_raw_config(
    path: Path,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Parse and interpolate a YAML or JSON project mapping."""

    if not path.is_file():
        raise _error(
            "config.not-found",
            f"Configuration file does not exist: {path}",
            "Provide an existing YAML or JSON project file.",
        )

    suffix = path.suffix.casefold()
    if suffix not in _YAML_SUFFIXES and suffix != ".json":
        raise _error(
            "config.unsupported-format",
            f"Unsupported configuration format: {path.suffix}",
            "Use a .yaml, .yml, or .json project file.",
        )

    try:
        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text) if suffix in _YAML_SUFFIXES else json.loads(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise _error(
            "config.parse",
            "Project configuration could not be parsed.",
            "Correct the YAML or JSON syntax and retry.",
        ) from error

    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise _error(
            "config.root",
            "Project configuration root must be a string-keyed mapping.",
            "Place project fields under a YAML or JSON object.",
        )

    interpolated = interpolate_environment(parsed, environ)
    return cast(dict[str, object], interpolated)


def load_config(
    path: str | Path,
    environ: Mapping[str, str] | None = None,
) -> ProjectConfig:
    """Load and validate one project configuration."""

    effective_environment = os.environ if environ is None else environ
    raw = load_raw_config(Path(path), effective_environment)
    try:
        return ProjectConfig.model_validate(raw)
    except ValidationError as error:
        raise _error(
            "config.invalid",
            f"Project configuration failed validation ({error.error_count()} errors).",
            "Run un-migrate config validate and correct the reported fields.",
        ) from error
