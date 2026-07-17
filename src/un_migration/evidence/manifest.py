from collections.abc import Mapping
from datetime import UTC, datetime

from un_migration.adapters.filesystem import ManagedArtifactStore
from un_migration.domain.artifacts import Artifact, Checksum
from un_migration.domain.identity import RunId
from un_migration.domain.runs import MigrationPlan, MigrationRun
from un_migration.domain.serialization import canonical_json
from un_migration.ports.source import AdapterCapabilities


def _checksum(value: Checksum) -> dict[str, str]:
    return {"algorithm": value.algorithm, "digest": value.digest}


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_manifest(
    run: MigrationRun,
    plan: MigrationPlan,
    config_fingerprint: Checksum,
    reference_fingerprint: Checksum,
    adapters: tuple[AdapterCapabilities, ...],
    artifacts: tuple[Artifact, ...],
    *,
    generated_at: datetime,
) -> dict[str, object]:
    """Build deterministic provenance for one migration run."""

    if generated_at.tzinfo is None:
        raise ValueError("manifest generated_at must be timezone-aware")
    return {
        "manifest_version": 1,
        "generated_at": _timestamp(generated_at),
        "run": {
            "id": str(run.id),
            "state": run.state.value,
            "started_at": _timestamp(run.started_at),
        },
        "config_fingerprint": _checksum(config_fingerprint),
        "reference_fingerprint": _checksum(reference_fingerprint),
        "adapters": [
            {
                "name": adapter.adapter_name,
                "operations": sorted(adapter.operations),
            }
            for adapter in sorted(adapters, key=lambda item: item.adapter_name)
        ],
        "plan": [
            {
                "id": str(step.id),
                "kind": step.kind.value,
                "prerequisites": [str(item) for item in step.prerequisites],
                "idempotent": step.idempotent,
            }
            for step in plan.ordered_steps()
        ],
        "artifacts": [
            {
                "id": str(artifact.id),
                "kind": artifact.kind.value,
                "path": artifact.path,
                "media_type": artifact.media_type,
                "size": artifact.size,
                "checksum": _checksum(artifact.checksum),
            }
            for artifact in sorted(artifacts, key=lambda item: item.path)
        ],
    }


def write_manifest(
    store: ManagedArtifactStore,
    run_id: RunId,
    manifest: Mapping[str, object],
) -> Artifact:
    """Persist canonical manifest JSON as a managed artifact."""

    return store.write(
        f"{run_id}/manifests/run.json",
        (canonical_json(manifest) + "\n").encode("utf-8"),
        "application/json",
    )
