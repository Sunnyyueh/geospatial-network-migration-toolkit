import json
from datetime import UTC, datetime
from pathlib import Path

from un_migration.adapters.filesystem import ManagedArtifactStore
from un_migration.domain.artifacts import ArtifactKind, Checksum
from un_migration.domain.identity import RunId
from un_migration.domain.runs import MigrationRun
from un_migration.domain.status import RunState
from un_migration.evidence.events import RunEvent, render_event_log
from un_migration.evidence.manifest import build_manifest, write_manifest
from un_migration.ports.source import AdapterCapabilities
from un_migration.workflow import build_default_plan


def test_manifest_is_deterministic_and_contains_fingerprints() -> None:
    run = MigrationRun(
        RunId("run-1"),
        RunState.PLANNED,
        datetime(2026, 7, 16, 12, tzinfo=UTC),
    )
    capabilities = AdapterCapabilities("csv", frozenset({"read", "inventory"}))

    manifest = build_manifest(
        run,
        build_default_plan(),
        Checksum.sha256(b"config"),
        Checksum.sha256(b"reference"),
        (capabilities,),
        (),
        generated_at=datetime(2026, 7, 16, 12, 1, tzinfo=UTC),
    )

    assert manifest["run"]["id"] == "run-1"  # type: ignore[index]
    assert manifest["config_fingerprint"]["algorithm"] == "sha256"  # type: ignore[index]
    assert manifest["adapters"] == [
        {"name": "csv", "operations": ["inventory", "read"]}
    ]
    assert manifest["plan"][0]["id"] == "configure"  # type: ignore[index]


def test_write_manifest_creates_verifiable_artifact(tmp_path: Path) -> None:
    store = ManagedArtifactStore(tmp_path)
    manifest = {"run": {"id": "run-1"}, "valid": True}

    artifact = write_manifest(store, RunId("run-1"), manifest)

    assert artifact.kind is ArtifactKind.MANIFEST
    assert artifact.path == "run-1/manifests/run.json"
    assert store.verify(artifact)
    assert json.loads(store.read(artifact.path))["valid"] is True


def test_event_log_preserves_order_and_redacts_nested_secrets() -> None:
    events = (
        RunEvent(
            1,
            datetime(2026, 7, 16, 12, tzinfo=UTC),
            "info",
            "run.started",
            {"token": "abc123", "workspace": "safe"},
        ),
        RunEvent(
            2,
            datetime(2026, 7, 16, 12, 0, 1, tzinfo=UTC),
            "error",
            "run.failed",
            {
                "message": "request with abc123 failed",
                "nested": {"password": "hidden"},
            },
        ),
    )

    payload = render_event_log(events, secrets=("abc123",))
    rows = [json.loads(line) for line in payload.decode().splitlines()]

    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[0]["data"] == {"token": "***REDACTED***", "workspace": "safe"}
    assert rows[1]["data"]["message"] == "request with ***REDACTED*** failed"
    assert rows[1]["data"]["nested"]["password"] == "***REDACTED***"
    assert b"abc123" not in payload


def test_event_rejects_naive_timestamp_and_invalid_sequence() -> None:
    import pytest

    with pytest.raises(ValueError):
        RunEvent(0, datetime(2026, 1, 1, tzinfo=UTC), "info", "event", {})
    with pytest.raises(ValueError):
        RunEvent(1, datetime(2026, 1, 1), "info", "event", {})
