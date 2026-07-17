from dataclasses import dataclass

from un_migration.domain.findings import Evidence, Finding, FindingCollection
from un_migration.domain.identity import FindingId, SequenceIdGenerator
from un_migration.domain.schema import DatasetInventory, FieldSchema, FieldType
from un_migration.domain.status import FindingStatus, Severity
from un_migration.mapping.models import DatasetMapping, FieldMapping

_WIDENING = {
    FieldType.INTEGER: frozenset(
        {FieldType.INTEGER, FieldType.FLOAT, FieldType.DECIMAL}
    ),
    FieldType.FLOAT: frozenset({FieldType.FLOAT, FieldType.DECIMAL}),
}


@dataclass(frozen=True, slots=True)
class MappingValidationResult:
    """Deterministic schema-compatibility findings for one dataset mapping."""

    findings: FindingCollection

    @property
    def valid(self) -> bool:
        """Return whether no compatibility rule failed."""

        return not self.findings.failed()


def _compatible(actual: FieldType, expected: FieldType) -> bool:
    return actual == expected or expected in _WIDENING.get(actual, frozenset())


def _finding(
    generator: SequenceIdGenerator,
    mapping: DatasetMapping,
    field_name: str,
    rule_id: str,
    message: str,
    remediation: str,
    *,
    severity: Severity = Severity.ERROR,
    evidence: Evidence | None = None,
) -> Finding:
    return Finding(
        id=FindingId(generator.new("mapping-finding")),
        rule_id=rule_id,
        status=FindingStatus.FAILED,
        severity=severity,
        message=message,
        remediation=remediation,
        evidence=evidence,
        dataset_id=mapping.source_dataset,
        field_name=field_name,
    )


def _type_findings(
    generator: SequenceIdGenerator,
    mapping: DatasetMapping,
    declared: FieldMapping,
    source_field: FieldSchema,
    target_field: FieldSchema | None,
) -> list[Finding]:
    findings: list[Finding] = []
    if not _compatible(source_field.type, declared.target_type):
        findings.append(
            _finding(
                generator,
                mapping,
                declared.source_field,
                "mapping.type",
                f"Source field {declared.source_field!r} cannot be mapped from "
                f"{source_field.type.value} to {declared.target_type.value}.",
                "Add an explicit compatible transformation or change the target type.",
                evidence=Evidence(
                    actual=source_field.type.value,
                    expected=declared.target_type.value,
                ),
            )
        )
    if target_field is not None and target_field.type != declared.target_type:
        findings.append(
            _finding(
                generator,
                mapping,
                declared.target_field,
                "mapping.type",
                f"Target field {declared.target_field!r} has type "
                f"{target_field.type.value}, not {declared.target_type.value}.",
                "Align the declared mapping type with the observed target schema.",
                evidence=Evidence(
                    actual=target_field.type.value,
                    expected=declared.target_type.value,
                ),
            )
        )
    return findings


def _constraint_findings(
    generator: SequenceIdGenerator,
    mapping: DatasetMapping,
    declared: FieldMapping,
    source_field: FieldSchema,
    target_field: FieldSchema | None,
) -> list[Finding]:
    findings: list[Finding] = []
    if (
        target_field is not None
        and source_field.type is FieldType.STRING
        and target_field.type is FieldType.STRING
        and source_field.length is not None
        and target_field.length is not None
        and source_field.length > target_field.length
    ):
        findings.append(
            _finding(
                generator,
                mapping,
                declared.target_field,
                "mapping.length",
                f"Target field {declared.target_field!r} is narrower than its source.",
                "Increase target length or add an explicit truncation policy.",
                severity=Severity.WARNING,
                evidence=Evidence(
                    actual=source_field.length,
                    expected=target_field.length,
                ),
            )
        )
    target_requires_value = declared.required or (
        target_field is not None and not target_field.nullable
    )
    if source_field.nullable and target_requires_value:
        findings.append(
            _finding(
                generator,
                mapping,
                declared.source_field,
                "mapping.nullability",
                f"Nullable source field {declared.source_field!r} maps to a "
                "required target.",
                "Reject null records or configure a deterministic default value.",
                severity=Severity.WARNING,
                evidence=Evidence(actual="nullable", expected="non-null"),
            )
        )
    return findings


def validate_mapping(
    mapping: DatasetMapping,
    source: DatasetInventory,
    target: DatasetInventory | None = None,
) -> MappingValidationResult:
    """Validate a dataset mapping against observed source and target schemas."""

    generator = SequenceIdGenerator()
    findings: list[Finding] = []
    for declared in mapping.fields:
        source_field = source.field(declared.source_field)
        target_field = target.field(declared.target_field) if target else None
        if source_field is None:
            findings.append(
                _finding(
                    generator,
                    mapping,
                    declared.source_field,
                    "mapping.source-field",
                    f"Source field {declared.source_field!r} was not inventoried.",
                    "Correct the source field name or refresh the source inventory.",
                )
            )
        if target is not None and target_field is None:
            findings.append(
                _finding(
                    generator,
                    mapping,
                    declared.target_field,
                    "mapping.target-field",
                    f"Target field {declared.target_field!r} was not inventoried.",
                    "Create the target field or correct the mapped target name.",
                )
            )
        if source_field is None:
            continue
        findings.extend(
            _type_findings(
                generator,
                mapping,
                declared,
                source_field,
                target_field,
            )
        )
        findings.extend(
            _constraint_findings(
                generator,
                mapping,
                declared,
                source_field,
                target_field,
            )
        )
    return MappingValidationResult(FindingCollection(tuple(findings)))
