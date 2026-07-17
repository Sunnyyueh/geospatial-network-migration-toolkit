import pytest

from un_migration.domain.artifacts import Artifact, ArtifactKind, Checksum
from un_migration.domain.identity import ArtifactId


def test_artifact_verifies_sha256_payload() -> None:
    payload = b"canonical report"
    artifact = Artifact(
        id=ArtifactId("artifact-report"),
        kind=ArtifactKind.REPORT,
        path="reports/report.json",
        media_type="application/json",
        size=len(payload),
        checksum=Checksum.sha256(payload),
    )

    assert artifact.verify(payload)
    assert not artifact.verify(b"changed")


@pytest.mark.parametrize(
    ("algorithm", "digest"),
    [
        ("md5", "0" * 64),
        ("sha256", "ABC"),
        ("sha256", "g" * 64),
    ],
)
def test_checksum_rejects_unsupported_or_invalid_values(
    algorithm: str,
    digest: str,
) -> None:
    with pytest.raises(ValueError):
        Checksum(algorithm, digest)


@pytest.mark.parametrize(
    "path",
    ["/tmp/report.json", "../report.json", "reports/../../report.json", ""],
)
def test_artifact_rejects_unmanaged_paths(path: str) -> None:
    with pytest.raises(ValueError, match="path"):
        Artifact(
            id=ArtifactId("artifact-report"),
            kind=ArtifactKind.REPORT,
            path=path,
            media_type="application/json",
            size=2,
            checksum=Checksum.sha256(b"{}"),
        )


def test_artifact_rejects_negative_size_and_empty_media_type() -> None:
    checksum = Checksum.sha256(b"")

    with pytest.raises(ValueError, match="size"):
        Artifact(
            id=ArtifactId("artifact-report"),
            kind=ArtifactKind.REPORT,
            path="report.json",
            media_type="application/json",
            size=-1,
            checksum=checksum,
        )
    with pytest.raises(ValueError, match="media_type"):
        Artifact(
            id=ArtifactId("artifact-report"),
            kind=ArtifactKind.REPORT,
            path="report.json",
            media_type=" ",
            size=0,
            checksum=checksum,
        )
