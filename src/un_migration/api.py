import platform
from dataclasses import dataclass

from un_migration._version import __version__


@dataclass(frozen=True, slots=True)
class PackageInfo:
    """Portable package and runtime information."""

    name: str
    version: str
    python: str
    platform: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "python": self.python,
            "platform": self.platform,
        }


def package_info() -> PackageInfo:
    """Return package information without probing external services."""

    return PackageInfo(
        name="geospatial-network-migration-toolkit",
        version=__version__,
        python=platform.python_version(),
        platform=platform.platform(),
    )
