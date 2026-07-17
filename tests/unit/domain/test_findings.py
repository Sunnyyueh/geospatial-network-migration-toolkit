from dataclasses import FrozenInstanceError

import pytest

from un_migration.domain.findings import (
    Evidence,
    Finding,
    FindingCollection,
    RuleScope,
    ValidationRule,
)
from un_migration.domain.identity import FindingId
from un_migration.domain.status import FindingStatus, Severity


def test_collection_counts_failed_findings_by_severity() -> None:
    failed = Finding(
        id=FindingId("finding-1"),
        rule_id="required.asset-id",
        status=FindingStatus.FAILED,
        severity=Severity.ERROR,
        message="asset_id is missing",
        remediation="Populate a stable asset identifier.",
        evidence=Evidence(actual=None, expected="non-null"),
    )
    passed = Finding(
        id=FindingId("finding-2"),
        rule_id="geometry.present",
        status=FindingStatus.PASSED,
        severity=Severity.ERROR,
        message="geometry is present",
    )

    collection = FindingCollection((failed, passed))

    assert collection.count_by_severity() == {"error": 1}
    assert collection.failed() == (failed,)
    assert collection.highest_severity() is Severity.ERROR


def test_skipped_finding_requires_reason() -> None:
    with pytest.raises(ValueError, match="skip_reason"):
        Finding(
            id=FindingId("finding-1"),
            rule_id="geometry.valid",
            status=FindingStatus.SKIPPED,
            severity=Severity.WARNING,
            message="geometry check skipped",
        )


def test_failed_finding_requires_remediation() -> None:
    with pytest.raises(ValueError, match="remediation"):
        Finding(
            id=FindingId("finding-1"),
            rule_id="required.asset-id",
            status=FindingStatus.FAILED,
            severity=Severity.ERROR,
            message="asset_id is missing",
        )


def test_validation_rule_parameters_are_defensively_immutable() -> None:
    parameters: dict[str, object] = {"threshold": 0.95}
    rule = ValidationRule(
        id="completeness.minimum",
        title="Minimum completeness",
        scope=RuleScope.DATASET,
        severity=Severity.ERROR,
        remediation="Review excluded and rejected source records.",
        parameters=parameters,
    )
    parameters["threshold"] = 0.5

    assert rule.parameters["threshold"] == 0.95
    with pytest.raises(TypeError):
        rule.parameters["threshold"] = 0.5  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        rule.title = "Changed"  # type: ignore[misc]


def test_empty_collection_has_no_highest_severity() -> None:
    assert FindingCollection().highest_severity() is None
