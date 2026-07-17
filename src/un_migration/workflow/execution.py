from dataclasses import dataclass

from un_migration.domain.findings import Finding, FindingCollection
from un_migration.domain.runs import RunMetrics
from un_migration.domain.schema import DatasetRef
from un_migration.mapping import DatasetMapping
from un_migration.ports.source import Record, RecordBatch, SourceReader
from un_migration.transformation import TransformRegistry, transform_record


@dataclass(frozen=True, slots=True)
class BatchTransformationResult:
    """Transformed batches plus aggregate evidence for one source dataset."""

    batches: tuple[RecordBatch, ...]
    findings: FindingCollection
    metrics: RunMetrics


def _record_id(record: Record, sequence: int) -> str:
    for name in ("asset_id", "objectid", "id"):
        for key, value in record.items():
            if key.casefold() == name and value is not None:
                return str(value)
    return f"row-{sequence}"


def transform_source(
    source: SourceReader,
    dataset: DatasetRef,
    mapping: DatasetMapping,
    registry: TransformRegistry,
    *,
    batch_size: int,
    filter_expression: object | None = None,
) -> BatchTransformationResult:
    """Read bounded source batches and project accepted transformed records."""

    selected = 0
    transformed = 0
    rejected = 0
    output_batches: list[RecordBatch] = []
    pending: list[Record] = []
    findings: list[Finding] = []
    for source_batch in source.read_batches(
        dataset,
        filter_expression,
        batch_size,
    ):
        for record in source_batch:
            selected += 1
            result = transform_record(
                record,
                mapping,
                registry,
                record_id=_record_id(record, selected),
            )
            findings.extend(result.findings.items)
            if result.findings.failed():
                rejected += 1
                continue
            transformed += 1
            pending.append(result.record)
            if len(pending) == batch_size:
                output_batches.append(tuple(pending))
                pending = []
    if pending:
        output_batches.append(tuple(pending))
    return BatchTransformationResult(
        tuple(output_batches),
        FindingCollection(tuple(findings)),
        RunMetrics(
            selected=selected,
            transformed=transformed,
            rejected=rejected,
        ),
    )
