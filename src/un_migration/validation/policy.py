from dataclasses import dataclass

from un_migration.domain.findings import FindingCollection
from un_migration.domain.runs import RunMetrics
from un_migration.domain.status import AcceptanceStatus, Severity


@dataclass(frozen=True, slots=True)
class AcceptancePolicy:
    """Thresholds that turn validation evidence into a review decision."""

    reject_at: Severity = Severity.ERROR


def decide_acceptance(
    findings: FindingCollection,
    metrics: RunMetrics,
    policy: AcceptancePolicy,
) -> AcceptanceStatus:
    """Derive an explicit acceptance status from evidence and counters."""

    if metrics.validated != metrics.staged:
        return AcceptanceStatus.INCOMPLETE
    failed = findings.failed()
    if any(item.severity >= policy.reject_at for item in failed):
        return AcceptanceStatus.REJECTED
    if any(item.severity is Severity.WARNING for item in failed):
        return AcceptanceStatus.ACCEPTED_WITH_WARNINGS
    return AcceptanceStatus.ACCEPTED
