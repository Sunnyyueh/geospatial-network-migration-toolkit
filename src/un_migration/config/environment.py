import re
from collections.abc import Mapping
from dataclasses import dataclass

from un_migration.domain.errors import ConfigurationError

_VARIABLE = re.compile(r"^\$\{(?P<name>[A-Z_][A-Z0-9_]*)(?::-(?P<default>[^}]*))?\}$")
_REDACTED = "***REDACTED***"


@dataclass(frozen=True, slots=True)
class SecretRegistry:
    """Case-insensitive registry of configuration keys to redact."""

    keys: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "keys",
            frozenset(key.casefold() for key in self.keys),
        )

    def is_secret(self, key: str) -> bool:
        return key.casefold() in self.keys


def _resolve(text: str, environ: Mapping[str, str]) -> str:
    match = _VARIABLE.fullmatch(text)
    if match is None:
        return text
    name = match.group("name")
    if name in environ:
        return environ[name]
    default = match.group("default")
    if default is not None:
        return default
    raise ConfigurationError(
        code="environment.missing",
        message=f"Required environment variable {name} is not set.",
        guidance=f"Set {name} before loading this project.",
    )


def interpolate_environment(
    value: object,
    environ: Mapping[str, str],
) -> object:
    """Resolve complete environment expressions in nested configuration data."""

    if isinstance(value, str):
        return _resolve(value, environ)
    if isinstance(value, Mapping):
        return {
            key: interpolate_environment(item, environ) for key, item in value.items()
        }
    if isinstance(value, list):
        return [interpolate_environment(item, environ) for item in value]
    if isinstance(value, tuple):
        return tuple(interpolate_environment(item, environ) for item in value)
    return value


def _redact(value: object, registry: SecretRegistry) -> object:
    if isinstance(value, Mapping):
        return {
            key: (
                _REDACTED
                if isinstance(key, str) and registry.is_secret(key)
                else _redact(item, registry)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, registry) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, registry) for item in value)
    return value


def redact_secrets(
    value: object,
    secret_keys: frozenset[str],
) -> object:
    """Return a recursively redacted copy of configuration data."""

    return _redact(value, SecretRegistry(secret_keys))
