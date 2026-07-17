from dataclasses import dataclass

from un_migration.adapters.filesystem import (
    CsvSourceReader,
    CsvStagingWriter,
    FilesystemNotifier,
)
from un_migration.config.models import ProjectConfig
from un_migration.domain.artifacts import Artifact
from un_migration.domain.errors import CapabilityError
from un_migration.domain.findings import Finding, FindingCollection
from un_migration.domain.identity import DatasetId, RunId
from un_migration.domain.runs import MigrationRun, RunMetrics, RunSummary
from un_migration.domain.schema import DatasetRef
from un_migration.domain.serialization import fingerprint
from un_migration.domain.status import RunState
from un_migration.domain.time import Clock, SystemClock
from un_migration.evidence import (
    RunEvent,
    build_manifest,
    render_event_log,
    write_manifest,
)
from un_migration.filters import Expression, parse_filter, validate_filter_fields
from un_migration.mapping import DatasetMapping, ReferenceTable, validate_mapping
from un_migration.ports.services import DeliveryReceipt
from un_migration.ports.source import Record
from un_migration.reporting import render_reports
from un_migration.review import prepare_review_bundle
from un_migration.transformation import default_registry
from un_migration.validation import (
    AcceptancePolicy,
    ValidationPolicy,
    decide_acceptance,
    validate_records,
)
from un_migration.workflow.execution import transform_source
from un_migration.workflow.planning import build_default_plan, select_mapping


@dataclass(frozen=True, slots=True)
class PortableRunResult:
    summary: RunSummary
    artifacts: tuple[Artifact, ...]
    notification: DeliveryReceipt


def generate_run_id(config: ProjectConfig, clock: Clock) -> RunId:
    instant = clock.now()
    timestamp = instant.strftime("%Y%m%d-%H%M%S")
    config_value = config.model_dump(mode="json")
    return RunId(f"run-{timestamp}-{fingerprint(config_value).digest[:8]}")


def _require_portable(config: ProjectConfig) -> None:
    if config.source.adapter.kind != "csv":
        raise CapabilityError(
            code="run.source-adapter",
            message="Portable runs require the CSV source adapter.",
            guidance="Set source.adapter.kind to csv or use a backend-specific runner.",
        )
    if config.target.adapter.kind != "filesystem":
        raise CapabilityError(
            code="run.target-adapter",
            message="Portable runs require the filesystem target adapter.",
            guidance="Set target.adapter.kind to filesystem.",
        )


def run_portable(
    config: ProjectConfig,
    reference: ReferenceTable,
    *,
    run_id: RunId | None = None,
    filter_text: str | None = None,
    clock: Clock | None = None,
) -> PortableRunResult:
    """Execute a portable, staged CSV migration and evidence workflow."""

    _require_portable(config)
    effective_clock = clock or SystemClock()
    effective_run_id = run_id or generate_run_id(config, effective_clock)
    started_at = effective_clock.now()
    run = MigrationRun(effective_run_id, RunState.CREATED, started_at)
    run = run.transition(RunState.CONFIGURED).transition(RunState.PLANNED)
    plan = build_default_plan()
    source = CsvSourceReader(config.source.workspace, config.source.datasets)
    parsed_filter: Expression | None = (
        parse_filter(filter_text) if filter_text is not None else None
    )
    contexts: list[tuple[DatasetRef, DatasetMapping]] = []
    findings: list[Finding] = []
    for configured in config.source.datasets:
        dataset = DatasetRef(DatasetId(configured.id), configured.path.as_posix())
        inventory = source.inventory(dataset)
        mapping = select_mapping(reference, dataset.id)
        findings.extend(validate_mapping(mapping, inventory).findings.items)
        if parsed_filter is not None:
            validate_filter_fields(parsed_filter, inventory)
        contexts.append((dataset, mapping))
    run = run.transition(RunState.INVENTORIED)

    writer = CsvStagingWriter(config.reporting.output_directory)
    writer.initialize(effective_run_id)
    selected = transformed = rejected = staged = validated = 0
    staged_records: dict[DatasetId, list[Record]] = {}
    selected_by_target: dict[DatasetId, int] = {}
    for dataset, mapping in contexts:
        transformed_result = transform_source(
            source,
            dataset,
            mapping,
            default_registry(),
            batch_size=config.runtime.batch_size,
            filter_expression=parsed_filter,
        )
        selected += transformed_result.metrics.selected
        selected_by_target[mapping.target_dataset] = (
            selected_by_target.get(mapping.target_dataset, 0)
            + transformed_result.metrics.selected
        )
        transformed += transformed_result.metrics.transformed
        rejected += transformed_result.metrics.rejected
        findings.extend(transformed_result.findings.items)
        dataset_records = staged_records.setdefault(mapping.target_dataset, [])
        for batch in transformed_result.batches:
            staged += writer.write_batch(mapping.target_dataset, batch)
            dataset_records.extend(batch)
    run = run.transition(RunState.EXTRACTED).transition(RunState.TRANSFORMED)
    staging_artifacts = writer.finalize()
    run = run.transition(RunState.STAGED)

    for _, mapping in contexts:
        records = tuple(staged_records.get(mapping.target_dataset, []))
        required = tuple(item.target_field for item in mapping.fields if item.required)
        key_field = required[0] if required else mapping.fields[0].target_field
        result = validate_records(
            records,
            selected_count=selected_by_target.get(mapping.target_dataset, 0),
            dataset_id=mapping.target_dataset,
            policy=ValidationPolicy(
                required_fields=required,
                key_field=key_field,
                minimum_completeness=1.0,
            ),
        )
        validated += result.validated_count
        findings.extend(result.findings.items)
    run = run.transition(RunState.VALIDATED)
    metrics = RunMetrics(
        selected=selected,
        transformed=transformed,
        staged=staged,
        rejected=rejected,
        validated=validated,
        duration_seconds=max(
            0.0,
            (effective_clock.now() - started_at).total_seconds(),
        ),
    )
    finding_collection = FindingCollection(tuple(findings))
    acceptance = decide_acceptance(
        finding_collection,
        metrics,
        AcceptancePolicy(),
    )
    initial_summary = RunSummary(
        run,
        acceptance,
        finding_collection,
        staging_artifacts,
        metrics,
    )
    report_artifacts = tuple(
        writer.store.write(
            f"{effective_run_id}/reports/{report.filename}",
            report.payload,
            report.media_type,
        )
        for report in render_reports(initial_summary, config.reporting.formats)
    )
    events = (
        RunEvent(1, started_at, "info", "run.started", {"run_id": str(run.id)}),
        RunEvent(
            2,
            effective_clock.now(),
            "info" if not finding_collection.failed() else "warning",
            "run.validated",
            {"acceptance": acceptance.value, "staged": staged, "rejected": rejected},
        ),
    )
    log_artifact = writer.store.write(
        f"{effective_run_id}/logs/events.jsonl",
        render_event_log(events),
        "application/x-ndjson",
    )
    manifest = build_manifest(
        run,
        plan,
        fingerprint(config.model_dump(mode="json")),
        fingerprint(reference),
        (source.capabilities(), writer.capabilities()),
        (*staging_artifacts, *report_artifacts, log_artifact),
        generated_at=effective_clock.now(),
    )
    manifest_artifact = write_manifest(writer.store, effective_run_id, manifest)
    evidence_artifacts = (
        *staging_artifacts,
        *report_artifacts,
        log_artifact,
        manifest_artifact,
    )
    review = prepare_review_bundle(
        writer.store,
        initial_summary,
        evidence_artifacts,
    )
    receipt = FilesystemNotifier(config.reporting.output_directory).deliver(
        review.notification
    )
    artifacts = (*evidence_artifacts, review.index)
    final_summary = RunSummary(
        run,
        acceptance,
        finding_collection,
        artifacts,
        metrics,
    )
    return PortableRunResult(final_summary, artifacts, receipt)
