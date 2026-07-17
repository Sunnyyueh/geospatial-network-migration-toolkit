from un_migration.domain.findings import Evidence, Finding, FindingCollection
from un_migration.domain.identity import DatasetId, FindingId
from un_migration.domain.runs import RunMetrics
from un_migration.domain.status import AcceptanceStatus, FindingStatus, Severity
from un_migration.validation.engine import ValidationPolicy, validate_records
from un_migration.validation.policy import AcceptancePolicy, decide_acceptance


def policy(**overrides: object) -> ValidationPolicy:
    values: dict[str, object] = {
        "required_fields": ("asset_id", "material"),
        "key_field": "asset_id",
        "allowed_values": {"material": frozenset({"PVC", "DI"})},
        "minimum_completeness": 1.0,
    }
    values.update(overrides)
    return ValidationPolicy(**values)  # type: ignore[arg-type]


def test_validation_accepts_complete_unique_allowed_records() -> None:
    result = validate_records(
        (
            {"asset_id": "A-1", "material": "PVC"},
            {"asset_id": "A-2", "material": "DI"},
        ),
        selected_count=2,
        dataset_id=DatasetId("utility-lines"),
        policy=policy(),
    )

    assert result.valid
    assert result.validated_count == 2
    assert result.findings.items == ()


def test_required_duplicate_and_allowed_value_rules_emit_stable_findings() -> None:
    result = validate_records(
        (
            {"asset_id": "A-1", "material": "COPPER"},
            {"asset_id": "A-1", "material": None},
        ),
        selected_count=2,
        dataset_id=DatasetId("utility-lines"),
        policy=policy(),
    )

    assert [item.rule_id for item in result.findings] == [
        "record.allowed-value",
        "record.duplicate-key",
        "record.required",
    ]
    assert [str(item.id) for item in result.findings] == [
        "validation-finding-000001",
        "validation-finding-000002",
        "validation-finding-000003",
    ]


def test_completeness_compares_staged_to_selected_count() -> None:
    result = validate_records(
        ({"asset_id": "A-1", "material": "PVC"},),
        selected_count=2,
        dataset_id=DatasetId("utility-lines"),
        policy=policy(minimum_completeness=0.75),
    )

    finding = result.findings.items[0]
    assert finding.rule_id == "migration.completeness"
    assert finding.evidence == Evidence(actual=0.5, expected=0.75)


def finding(severity: Severity) -> Finding:
    return Finding(
        FindingId(f"finding-{severity.value}"),
        "rule",
        FindingStatus.FAILED,
        severity,
        "validation failed",
        "Correct the source record.",
    )


def test_acceptance_rejects_error_findings() -> None:
    status = decide_acceptance(
        FindingCollection((finding(Severity.ERROR),)),
        RunMetrics(selected=2, transformed=2, staged=2, validated=2),
        AcceptancePolicy(),
    )

    assert status is AcceptanceStatus.REJECTED


def test_acceptance_allows_warning_with_explicit_status() -> None:
    status = decide_acceptance(
        FindingCollection((finding(Severity.WARNING),)),
        RunMetrics(selected=2, transformed=2, staged=2, validated=2),
        AcceptancePolicy(),
    )

    assert status is AcceptanceStatus.ACCEPTED_WITH_WARNINGS


def test_acceptance_marks_unaccounted_records_incomplete() -> None:
    status = decide_acceptance(
        FindingCollection(),
        RunMetrics(selected=3, transformed=2, staged=2, validated=1),
        AcceptancePolicy(),
    )

    assert status is AcceptanceStatus.INCOMPLETE


def test_acceptance_accepts_fully_validated_run() -> None:
    status = decide_acceptance(
        FindingCollection(),
        RunMetrics(selected=2, transformed=2, staged=2, validated=2),
        AcceptancePolicy(),
    )

    assert status is AcceptanceStatus.ACCEPTED
