import json
from datetime import UTC, datetime
from pathlib import Path

from un_migration.adapters.filesystem import ManagedArtifactStore
from un_migration.adapters.filesystem.notifier import FilesystemNotifier
from un_migration.domain.artifacts import Artifact, ArtifactKind, Checksum
from un_migration.domain.findings import FindingCollection
from un_migration.domain.identity import ArtifactId, RunId
from un_migration.domain.runs import MigrationRun, RunMetrics, RunSummary
from un_migration.domain.status import AcceptanceStatus, RunState
from un_migration.review.bundle import prepare_review_bundle


def summary() -> RunSummary:
    return RunSummary(
        MigrationRun(
            RunId("run-1"),
            RunState.VALIDATED,
            datetime(2026, 7, 16, tzinfo=UTC),
        ),
        AcceptanceStatus.REJECTED,
        FindingCollection(),
        (),
        RunMetrics(selected=2, transformed=1, staged=1, rejected=1, validated=1),
    )


def report_artifact() -> Artifact:
    return Artifact(
        ArtifactId("report-1"),
        ArtifactKind.REPORT,
        "run-1/reports/summary.html",
        "text/html",
        4,
        Checksum.sha256(b"data"),
    )


def test_review_bundle_writes_index_and_rejected_wording(tmp_path: Path) -> None:
    store = ManagedArtifactStore(tmp_path)

    bundle = prepare_review_bundle(store, summary(), (report_artifact(),))

    assert bundle.index.path == "run-1/review/index.json"
    assert store.verify(bundle.index)
    assert "REJECTED" in bundle.notification.subject
    assert "must not be deployed" in bundle.notification.message
    payload = json.loads(store.read(bundle.index.path))
    assert payload["deployment_authorized"] is False
    assert payload["artifacts"][0]["path"] == "run-1/reports/summary.html"


def test_filesystem_notifier_redacts_and_returns_stable_receipt(tmp_path: Path) -> None:
    store = ManagedArtifactStore(tmp_path)
    bundle = prepare_review_bundle(store, summary(), (report_artifact(),))
    notification = type(bundle.notification)(
        bundle.notification.subject,
        bundle.notification.message + " token=abc123",
        bundle.notification.artifact_paths,
    )
    notifier = FilesystemNotifier(tmp_path, secrets=("abc123",))

    receipt = notifier.deliver(notification)

    assert receipt.accepted
    assert receipt.provider == "filesystem-outbox"
    files = list((tmp_path / "outbox").glob("*.json"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "abc123" not in text
    assert "***REDACTED***" in text
    assert receipt.message_id in files[0].name


def test_outbox_delivery_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    store = ManagedArtifactStore(tmp_path)
    notification = prepare_review_bundle(
        store, summary(), (report_artifact(),)
    ).notification
    notifier = FilesystemNotifier(tmp_path)

    first = notifier.deliver(notification)
    second = notifier.deliver(notification)

    assert first == second
    assert len(list((tmp_path / "outbox").glob("*.json"))) == 1
