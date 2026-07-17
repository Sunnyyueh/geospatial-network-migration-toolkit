from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from un_migration.domain.findings import Evidence, Finding, FindingCollection
from un_migration.domain.identity import DatasetId, FindingId, SequenceIdGenerator
from un_migration.domain.status import FindingStatus, Severity
from un_migration.ports.source import Record


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """Portable record validation rules for one staged dataset."""

    required_fields: tuple[str, ...] = ()
    key_field: str | None = None
    allowed_values: Mapping[str, frozenset[object]] = field(default_factory=dict)
    minimum_completeness: float = 1.0

    def __post_init__(self) -> None:
        if len(self.required_fields) != len(set(self.required_fields)):
            raise ValueError("required_fields must be unique")
        if not 0 <= self.minimum_completeness <= 1:
            raise ValueError("minimum_completeness must be between zero and one")
        object.__setattr__(
            self,
            "allowed_values",
            MappingProxyType(
                {
                    name: frozenset(values)
                    for name, values in self.allowed_values.items()
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class ValidationResult:
    findings: FindingCollection
    validated_count: int

    @property
    def valid(self) -> bool:
        return not self.findings.failed()


def _value(record: Record, field_name: str) -> object:
    if field_name in record:
        return record[field_name]
    normalized = field_name.casefold()
    return next(
        (value for name, value in record.items() if name.casefold() == normalized),
        None,
    )


def _finding(
    generator: SequenceIdGenerator,
    dataset_id: DatasetId,
    rule_id: str,
    message: str,
    field_name: str | None,
    evidence: Evidence,
) -> Finding:
    return Finding(
        FindingId(generator.new("validation-finding")),
        rule_id,
        FindingStatus.FAILED,
        Severity.ERROR,
        message,
        "Correct the staged record or validation policy before acceptance.",
        evidence,
        dataset_id,
        field_name,
    )


def validate_records(
    records: tuple[Record, ...],
    *,
    selected_count: int,
    dataset_id: DatasetId,
    policy: ValidationPolicy,
) -> ValidationResult:
    """Execute deterministic completeness and record-level validations."""

    if selected_count < 0 or len(records) > selected_count:
        raise ValueError("selected_count must cover all staged records")
    generator = SequenceIdGenerator()
    findings: list[Finding] = []
    completeness = len(records) / selected_count if selected_count else 1.0
    if completeness < policy.minimum_completeness:
        findings.append(
            _finding(
                generator,
                dataset_id,
                "migration.completeness",
                "Staged record completeness is below the configured threshold.",
                None,
                Evidence(completeness, policy.minimum_completeness),
            )
        )
    seen_keys: set[object] = set()
    for index, record in enumerate(records, start=1):
        record_id = str(_value(record, policy.key_field)) if policy.key_field else None
        if policy.key_field is not None:
            key = _value(record, policy.key_field)
            if key is not None and key in seen_keys:
                findings.append(
                    _finding(
                        generator,
                        dataset_id,
                        "record.duplicate-key",
                        f"Duplicate key found in record {index}.",
                        policy.key_field,
                        Evidence(key, "unique", record_id),
                    )
                )
            elif key is not None:
                seen_keys.add(key)
        for field_name in policy.required_fields:
            value = _value(record, field_name)
            if value is None or value == "":
                findings.append(
                    _finding(
                        generator,
                        dataset_id,
                        "record.required",
                        f"Required field {field_name!r} is empty in record {index}.",
                        field_name,
                        Evidence(value, "non-empty", record_id),
                    )
                )
        for field_name, allowed in policy.allowed_values.items():
            value = _value(record, field_name)
            if value is not None and value not in allowed:
                findings.append(
                    _finding(
                        generator,
                        dataset_id,
                        "record.allowed-value",
                        f"Field {field_name!r} contains a disallowed value.",
                        field_name,
                        Evidence(
                            value, sorted(str(item) for item in allowed), record_id
                        ),
                    )
                )
    return ValidationResult(FindingCollection(tuple(findings)), len(records))
