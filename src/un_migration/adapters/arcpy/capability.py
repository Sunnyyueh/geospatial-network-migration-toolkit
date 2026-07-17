import importlib
import importlib.util
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

from un_migration.domain.errors import CapabilityError
from un_migration.ports.source import AdapterCapabilities

FindSpec = Callable[[str], object | None]
VersionProvider = Callable[[], str]
Importer = Callable[[str], object]


class _ArcPyModule(Protocol):
    def GetInstallInfo(self) -> object: ...

    def AddFieldDelimiters(self, workspace: str, field_name: str) -> object: ...


class ArcPyCapabilityStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"
    AVAILABLE = "available"


@dataclass(frozen=True, slots=True)
class ArcPyCapability:
    status: ArcPyCapabilityStatus
    version: str | None
    reason: str

    @property
    def available(self) -> bool:
        return self.status is ArcPyCapabilityStatus.AVAILABLE


def _installed_version() -> str:
    module = cast(_ArcPyModule, importlib.import_module("arcpy"))
    information = module.GetInstallInfo()
    if not isinstance(information, Mapping):
        raise ValueError("ArcPy install information is not a mapping")
    return str(information["Version"])


def _version_tuple(value: str) -> tuple[int, int]:
    matched = re.match(r"^(\d+)\.(\d+)", value)
    if matched is None:
        raise ValueError("unrecognized ArcPy version")
    return int(matched.group(1)), int(matched.group(2))


def probe_arcpy(
    find_spec: FindSpec = importlib.util.find_spec,
    version_provider: VersionProvider = _installed_version,
    *,
    minimum_version: tuple[int, int] = (3, 1),
) -> ArcPyCapability:
    """Explicitly probe optional ArcPy availability and minimum version."""

    if find_spec("arcpy") is None:
        return ArcPyCapability(
            ArcPyCapabilityStatus.UNAVAILABLE,
            None,
            "ArcPy is not installed in this Python environment.",
        )
    try:
        version = version_provider()
        parsed = _version_tuple(version)
    except (KeyError, TypeError, ValueError) as error:
        return ArcPyCapability(
            ArcPyCapabilityStatus.INCOMPATIBLE,
            None,
            f"ArcPy version could not be verified: {type(error).__name__}.",
        )
    if parsed < minimum_version:
        required = ".".join(str(item) for item in minimum_version)
        return ArcPyCapability(
            ArcPyCapabilityStatus.INCOMPATIBLE,
            version,
            f"ArcPy {required} or newer is required.",
        )
    return ArcPyCapability(
        ArcPyCapabilityStatus.AVAILABLE,
        version,
        "ArcPy is available for explicitly selected proprietary operations.",
    )


class LazyArcPyFacade:
    """Import ArcPy only when a verified backend operation is requested."""

    def __init__(
        self,
        probe: Callable[[], ArcPyCapability] = probe_arcpy,
        importer: Importer = importlib.import_module,
    ) -> None:
        self._probe = probe
        self._importer = importer
        self._capability: ArcPyCapability | None = None
        self._module: object | None = None

    def probe(self) -> ArcPyCapability:
        if self._capability is None:
            self._capability = self._probe()
        return self._capability

    def _require(self) -> object:
        capability = self.probe()
        if not capability.available:
            code = (
                "arcpy.unavailable"
                if capability.status is ArcPyCapabilityStatus.UNAVAILABLE
                else "arcpy.incompatible"
            )
            raise CapabilityError(
                code=code,
                message=capability.reason,
                guidance=(
                    "Use the portable adapters or install a compatible "
                    "ArcGIS Pro runtime."
                ),
            )
        if self._module is None:
            self._module = self._importer("arcpy")
        return self._module

    def capabilities(self) -> AdapterCapabilities:
        capability = self.probe()
        if not capability.available:
            self._require()
        return AdapterCapabilities(
            "arcpy",
            frozenset({"inventory", "count", "read", "filter", "delimit-field"}),
        )

    def delimit_field(self, workspace: str, field_name: str) -> str:
        module = cast(_ArcPyModule, self._require())
        value = module.AddFieldDelimiters(workspace, field_name)
        if not isinstance(value, str) or not value:
            raise CapabilityError(
                code="arcpy.delimiter",
                message="ArcPy returned an invalid field delimiter.",
                guidance="Verify the workspace and ArcPy installation.",
            )
        return value
