from types import SimpleNamespace

import pytest

from un_migration.adapters.arcpy import (
    ArcPyCapabilityStatus,
    LazyArcPyFacade,
    probe_arcpy,
)
from un_migration.domain.errors import CapabilityError


def test_probe_reports_unavailable_without_loading_version() -> None:
    called = False

    def version() -> str:
        nonlocal called
        called = True
        return "3.3"

    capability = probe_arcpy(lambda _: None, version)

    assert capability.status is ArcPyCapabilityStatus.UNAVAILABLE
    assert capability.version is None
    assert not called


def test_probe_reports_compatible_and_incompatible_versions() -> None:
    available = probe_arcpy(lambda _: object(), lambda: "3.3.1")
    incompatible = probe_arcpy(lambda _: object(), lambda: "2.9.5")

    assert available.status is ArcPyCapabilityStatus.AVAILABLE
    assert available.version == "3.3.1"
    assert incompatible.status is ArcPyCapabilityStatus.INCOMPATIBLE
    assert "3.1" in incompatible.reason


def test_probe_handles_invalid_version_as_incompatible() -> None:
    capability = probe_arcpy(lambda _: object(), lambda: "unknown")

    assert capability.status is ArcPyCapabilityStatus.INCOMPATIBLE


def test_lazy_facade_does_not_import_until_backend_operation() -> None:
    imported = 0
    fake = SimpleNamespace(
        AddFieldDelimiters=lambda workspace, field: f"[{workspace}:{field}]"
    )

    def importer(name: str) -> object:
        nonlocal imported
        assert name == "arcpy"
        imported += 1
        return fake

    facade = LazyArcPyFacade(
        lambda: probe_arcpy(lambda _: object(), lambda: "3.3"),
        importer,
    )

    assert imported == 0
    assert facade.capabilities().supports("filter")
    assert imported == 0
    assert facade.delimit_field("workspace.gdb", "asset_id") == (
        "[workspace.gdb:asset_id]"
    )
    assert imported == 1
    facade.delimit_field("workspace.gdb", "material")
    assert imported == 1


def test_lazy_facade_rejects_unavailable_backend() -> None:
    facade = LazyArcPyFacade(
        lambda: probe_arcpy(lambda _: None, lambda: "3.3"),
        lambda _: object(),
    )

    with pytest.raises(CapabilityError) as raised:
        facade.capabilities()

    assert raised.value.code == "arcpy.unavailable"
