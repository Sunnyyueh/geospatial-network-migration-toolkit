from pathlib import Path, PurePosixPath

from un_migration.adapters.filesystem.artifacts import ManagedArtifactStore
from un_migration.domain.artifacts import Checksum
from un_migration.domain.errors import NotificationError
from un_migration.domain.serialization import canonical_json
from un_migration.ports.services import DeliveryReceipt, Notification

_REDACTED = "***REDACTED***"


class FilesystemNotifier:
    """Content-addressed local outbox for reviewer notification handoff."""

    def __init__(self, root: Path, secrets: tuple[str, ...] = ()) -> None:
        self.store = ManagedArtifactStore(root)
        self.secrets = tuple(secret for secret in secrets if secret)

    def _redact(self, value: str) -> str:
        for secret in self.secrets:
            value = value.replace(secret, _REDACTED)
        return value

    @staticmethod
    def _validate_path(path: str) -> None:
        logical = PurePosixPath(path)
        if logical.is_absolute() or ".." in logical.parts or "\\" in path:
            raise NotificationError(
                code="notification.path",
                message="Notification contains an unmanaged artifact path.",
                guidance="Reference only managed run artifacts.",
            )

    def deliver(self, notification: Notification) -> DeliveryReceipt:
        for path in notification.artifact_paths:
            self._validate_path(path)
        payload = {
            "subject": self._redact(notification.subject),
            "message": self._redact(notification.message),
            "artifact_paths": list(notification.artifact_paths),
        }
        encoded = (canonical_json(payload) + "\n").encode("utf-8")
        message_id = f"message-{Checksum.sha256(encoded).digest[:24]}"
        self.store.write(
            f"outbox/{message_id}.json",
            encoded,
            "application/json",
        )
        return DeliveryReceipt("filesystem-outbox", message_id, True)
