from importlib.metadata import version

import un_migration


def test_public_version_matches_installed_metadata() -> None:
    assert un_migration.__version__ == version("geospatial-network-migration-toolkit")
    major, minor, patch = un_migration.__version__.split(".")
    assert all(part.isdigit() for part in (major, minor, patch))
