from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import cast

import yaml

from un_migration.domain.errors import ConfigurationError


def _override_error(text: str) -> ConfigurationError:
    return ConfigurationError(
        code="config.override",
        message=f"Invalid configuration override: {text}",
        guidance="Use an existing dotted.path=value setting.",
    )


def deep_merge(
    base: Mapping[str, object],
    overlay: Mapping[str, object],
) -> dict[str, object]:
    """Recursively merge mappings and replace non-mapping values."""

    result = deepcopy(dict(base))
    for key, value in overlay.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(
                cast(Mapping[str, object], current),
                cast(Mapping[str, object], value),
            )
        else:
            result[key] = deepcopy(value)
    return result


def parse_override(text: str) -> tuple[tuple[str, ...], object]:
    """Parse dotted.path=YAML-value into a typed override."""

    key, separator, raw_value = text.partition("=")
    path = tuple(key.split("."))
    if not separator or any(not segment for segment in path):
        raise _override_error(text)
    try:
        value = yaml.safe_load(raw_value)
    except yaml.YAMLError as error:
        raise _override_error(text) from error
    return path, value


def apply_overrides(
    config: Mapping[str, object],
    overrides: Iterable[str],
) -> dict[str, object]:
    """Apply typed overrides to existing leaves in a copied mapping."""

    result = deepcopy(dict(config))
    for override in overrides:
        path, value = parse_override(override)
        cursor = result
        for segment in path[:-1]:
            child = cursor.get(segment)
            if not isinstance(child, dict):
                raise _override_error(override)
            cursor = cast(dict[str, object], child)
        leaf = path[-1]
        if leaf not in cursor:
            raise _override_error(override)
        cursor[leaf] = deepcopy(value)
    return result
