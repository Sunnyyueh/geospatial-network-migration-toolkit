from un_migration.domain.errors import ErrorContext, MappingError
from un_migration.domain.identity import DatasetId, StepId
from un_migration.domain.runs import MigrationPlan, PlanStep, StepKind
from un_migration.mapping import DatasetMapping, ReferenceTable


def build_default_plan() -> MigrationPlan:
    """Build the portable migration workflow dependency graph."""

    definitions = (
        ("configure", StepKind.CONFIGURE, ()),
        ("plan", StepKind.PLAN, ("configure",)),
        ("inventory", StepKind.INVENTORY, ("plan",)),
        ("extract", StepKind.EXTRACT, ("inventory",)),
        ("transform", StepKind.TRANSFORM, ("extract",)),
        ("stage", StepKind.STAGE, ("transform",)),
        ("validate", StepKind.VALIDATE, ("stage",)),
        ("report", StepKind.REPORT, ("validate",)),
        ("notify", StepKind.NOTIFY, ("report",)),
    )
    return MigrationPlan(
        tuple(
            PlanStep(
                StepId(step_id),
                kind,
                tuple(StepId(item) for item in prerequisites),
            )
            for step_id, kind, prerequisites in definitions
        )
    )


def select_mapping(
    table: ReferenceTable,
    dataset_id: DatasetId,
) -> DatasetMapping:
    """Select the one mapping for a configured source dataset."""

    mapping = table.dataset(dataset_id)
    if mapping is None:
        raise MappingError(
            code="mapping.dataset-missing",
            message=f"Reference table has no mapping for dataset {dataset_id}.",
            guidance="Add a dataset mapping before planning the run.",
            context=ErrorContext(dataset_id=str(dataset_id)),
        )
    return mapping
