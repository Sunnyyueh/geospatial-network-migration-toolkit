from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from un_migration.domain.identity import DatasetId, FindingId
from un_migration.domain.status import FindingStatus, Severity


class RuleScope(StrEnum):
    """Granularity at which a validation rule operates."""

    RUN = "run"
    DATASET = "dataset"
    FIELD = "field"
    RECORD = "record"


@dataclass(frozen=True, slots=True)
class ValidationRule:
    """Immutable rule configuration understood by validators."""

    id: str
    title: str
    scope: RuleScope
    severity: Severity
    remediation: str
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("title", self.title),
            ("remediation", self.remediation),
        ):
            if not value.strip():
                raise ValueError(f"rule {name} must not be empty")
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType(dict(self.parameters)),
        )


@dataclass(frozen=True, slots=True)
class Evidence:
    """Safe observed and expected values for a finding."""

    actual: object
    expected: object
    record_id: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    """One explainable validation outcome."""

    id: FindingId
    rule_id: str
    status: FindingStatus
    severity: Severity
    message: str
    remediation: str | None = None
    evidence: Evidence | None = None
    dataset_id: DatasetId | None = None
    field_name: str | None = None
    skip_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("finding rule_id must not be empty")
        if not self.message.strip():
            raise ValueError("finding message must not be empty")
        if self.status is FindingStatus.SKIPPED and not self.skip_reason:
            raise ValueError("skipped finding requires skip_reason")
        if self.status is FindingStatus.FAILED and not self.remediation:
            raise ValueError("failed finding requires remediation")


@dataclass(frozen=True, slots=True)
class FindingCollection:
    """Immutable collection with deterministic finding aggregations."""

    items: tuple[Finding, ...] = ()

    def __iter__(self) -> Iterator[Finding]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def failed(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.items if item.status is FindingStatus.FAILED)

    def skipped(self) -> tuple[Finding, ...]:
        return tuple(
            item for item in self.items if item.status is FindingStatus.SKIPPED
        )

    def highest_severity(self) -> Severity | None:
        return max((item.severity for item in self.failed()), default=None)

    def count_by_severity(self) -> dict[str, int]:
        counts = Counter(item.severity.name.lower() for item in self.failed())
        return dict(sorted(counts.items()))
