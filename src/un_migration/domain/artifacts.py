import hashlib
import re
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from un_migration.domain.identity import ArtifactId


class ArtifactKind(StrEnum):
    """Purpose of a generated migration artifact."""

    CONFIGURATION = "configuration"
    PLAN = "plan"
    INVENTORY = "inventory"
    STAGING = "staging"
    FINDINGS = "findings"
    REPORT = "report"
    LOG = "log"
    MANIFEST = "manifest"
    DEPLOYMENT = "deployment"


@dataclass(frozen=True, slots=True)
class Checksum:
    """Validated content checksum."""

    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("only sha256 checksums are supported")
        if not re.fullmatch(r"[0-9a-f]{64}", self.digest):
            raise ValueError(
                "sha256 digest must be 64 lowercase hexadecimal characters"
            )

    @classmethod
    def sha256(cls, payload: bytes) -> "Checksum":
        return cls("sha256", hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True, slots=True)
class Artifact:
    """Managed output with integrity and provenance-ready metadata."""

    id: ArtifactId
    kind: ArtifactKind
    path: str
    media_type: str
    size: int
    checksum: Checksum

    def __post_init__(self) -> None:
        path = PurePosixPath(self.path)
        if (
            not self.path
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in self.path
        ):
            raise ValueError("artifact path must be managed and relative")
        if self.size < 0:
            raise ValueError("artifact size must be nonnegative")
        if not self.media_type.strip():
            raise ValueError("artifact media_type must not be empty")

    def verify(self, payload: bytes) -> bool:
        """Verify payload length and digest without timing-sensitive equality."""

        return self.size == len(payload) and secrets.compare_digest(
            self.checksum.digest,
            Checksum.sha256(payload).digest,
        )
