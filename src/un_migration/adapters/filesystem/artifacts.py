import os
import tempfile
from pathlib import Path, PurePosixPath

from un_migration.domain.artifacts import Artifact, ArtifactKind, Checksum
from un_migration.domain.identity import ArtifactId


class ManagedArtifactStore:
    """Filesystem artifact store constrained to one managed root."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, Artifact] = {}

    def _path(self, path: str) -> Path:
        logical = PurePosixPath(path)
        if not path or logical.is_absolute() or ".." in logical.parts or "\\" in path:
            raise ValueError("artifact path must be managed and relative")
        resolved = (self.root / Path(*logical.parts)).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("artifact path must remain below managed root")
        return resolved

    @staticmethod
    def _kind(path: str) -> ArtifactKind:
        parts = set(PurePosixPath(path).parts)
        if "staging" in parts:
            return ArtifactKind.STAGING
        if "manifests" in parts:
            return ArtifactKind.MANIFEST
        if "logs" in parts:
            return ArtifactKind.LOG
        if "findings" in parts:
            return ArtifactKind.FINDINGS
        return ArtifactKind.REPORT

    @staticmethod
    def _artifact(
        path: str,
        payload: bytes,
        media_type: str,
        kind: ArtifactKind,
    ) -> Artifact:
        identity = Checksum.sha256(path.encode("utf-8") + b"\x00" + payload)
        return Artifact(
            ArtifactId(f"artifact-{identity.digest[:24]}"),
            kind,
            path,
            media_type,
            len(payload),
            Checksum.sha256(payload),
        )

    def write(
        self,
        path: str,
        payload: bytes,
        media_type: str,
    ) -> Artifact:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=target.parent,
                prefix=f".{target.name}.",
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            os.replace(temporary_name, target)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        artifact = self._artifact(path, payload, media_type, self._kind(path))
        self._artifacts[path] = artifact
        return artifact

    def register_existing(
        self,
        path: str,
        media_type: str,
        kind: ArtifactKind,
    ) -> Artifact:
        payload = self._path(path).read_bytes()
        artifact = self._artifact(path, payload, media_type, kind)
        self._artifacts[path] = artifact
        return artifact

    def read(self, path: str) -> bytes:
        return self._path(path).read_bytes()

    def list(self) -> tuple[Artifact, ...]:
        return tuple(self._artifacts[path] for path in sorted(self._artifacts))

    def verify(self, artifact: Artifact) -> bool:
        try:
            return artifact.verify(self.read(artifact.path))
        except OSError:
            return False
