from dataclasses import dataclass

from un_migration.adapters.filesystem import ManagedArtifactStore
from un_migration.domain.artifacts import Artifact
from un_migration.domain.runs import RunSummary
from un_migration.domain.serialization import canonical_json
from un_migration.domain.status import AcceptanceStatus
from un_migration.ports.services import Notification


@dataclass(frozen=True, slots=True)
class ReviewBundle:
    index: Artifact
    notification: Notification


def prepare_review_bundle(
    store: ManagedArtifactStore,
    summary: RunSummary,
    artifacts: tuple[Artifact, ...],
) -> ReviewBundle:
    """Write reviewer-safe handoff metadata without authorizing deployment."""

    ordered = tuple(sorted(artifacts, key=lambda item: item.path))
    payload = {
        "bundle_version": 1,
        "run_id": str(summary.run.id),
        "acceptance": summary.acceptance.value,
        "deployment_authorized": False,
        "metrics": {
            "selected": summary.metrics.selected,
            "staged": summary.metrics.staged,
            "rejected": summary.metrics.rejected,
            "validated": summary.metrics.validated,
        },
        "artifacts": [
            {
                "path": artifact.path,
                "kind": artifact.kind.value,
                "checksum": artifact.checksum.digest,
            }
            for artifact in ordered
        ],
    }
    index = store.write(
        f"{summary.run.id}/review/index.json",
        (canonical_json(payload) + "\n").encode("utf-8"),
        "application/json",
    )
    rejected = summary.acceptance in {
        AcceptanceStatus.REJECTED,
        AcceptanceStatus.INCOMPLETE,
    }
    decision = summary.acceptance.value.upper()
    message = f"Migration run {summary.run.id} is {decision}. " + (
        "This run must not be deployed; correct findings and rerun."
        if rejected
        else "Review the attached evidence before any separately authorized deployment."
    )
    notification = Notification(
        subject=f"Migration review {summary.run.id}: {decision}",
        message=message,
        artifact_paths=(index.path, *(artifact.path for artifact in ordered)),
    )
    return ReviewBundle(index, notification)
