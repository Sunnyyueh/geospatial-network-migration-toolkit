from un_migration.adapters.memory import MemoryDataset, MemorySourceReader
from un_migration.domain.errors import MappingError
from un_migration.domain.identity import DatasetId
from un_migration.domain.runs import StepKind
from un_migration.domain.schema import (
    DatasetInventory,
    DatasetRef,
    FieldSchema,
    FieldType,
)
from un_migration.mapping import (
    DatasetMapping,
    FieldMapping,
    NullPolicy,
    ReferenceTable,
    TransformSpec,
)
from un_migration.transformation import default_registry
from un_migration.workflow.execution import transform_source
from un_migration.workflow.planning import build_default_plan, select_mapping


def fixture() -> tuple[MemorySourceReader, DatasetRef, ReferenceTable]:
    dataset = DatasetRef(DatasetId("water-mains"), "water_mains")
    inventory = DatasetInventory(
        dataset,
        (
            FieldSchema("asset_id", FieldType.STRING, nullable=True),
            FieldSchema("diameter", FieldType.INTEGER),
        ),
        feature_count=3,
    )
    records = (
        {"asset_id": "wm-1", "diameter": 4},
        {"asset_id": None, "diameter": 6},
        {"asset_id": "wm-3", "diameter": 8},
    )
    reader = MemorySourceReader({dataset.id: MemoryDataset(inventory, records)})
    mapping = DatasetMapping(
        dataset.id,
        DatasetId("utility-lines"),
        (
            FieldMapping(
                "asset_id",
                "asset_identifier",
                FieldType.STRING,
                required=True,
                null_policy=NullPolicy.REJECT,
                transform=TransformSpec("uppercase"),
            ),
            FieldMapping("diameter", "diameter_mm", FieldType.INTEGER),
        ),
    )
    return reader, dataset, ReferenceTable(1, (mapping,))


def test_default_plan_has_stable_dependency_order() -> None:
    plan = build_default_plan()

    assert [step.kind for step in plan.ordered_steps()] == [
        StepKind.CONFIGURE,
        StepKind.PLAN,
        StepKind.INVENTORY,
        StepKind.EXTRACT,
        StepKind.TRANSFORM,
        StepKind.STAGE,
        StepKind.VALIDATE,
        StepKind.REPORT,
        StepKind.NOTIFY,
    ]


def test_select_mapping_requires_configured_dataset() -> None:
    _, _, table = fixture()

    try:
        select_mapping(table, DatasetId("missing"))
    except MappingError as error:
        assert error.code == "mapping.dataset-missing"
    else:
        raise AssertionError("missing mapping was accepted")


def test_transform_source_batches_valid_records_and_aggregates_rejections() -> None:
    reader, dataset, table = fixture()
    result = transform_source(
        reader,
        dataset,
        select_mapping(table, dataset.id),
        default_registry(),
        batch_size=1,
    )

    assert result.batches == (
        ({"asset_identifier": "WM-1", "diameter_mm": 4},),
        ({"asset_identifier": "WM-3", "diameter_mm": 8},),
    )
    assert result.metrics.selected == 3
    assert result.metrics.transformed == 2
    assert result.metrics.rejected == 1
    assert len(result.findings.failed()) == 1


def test_transform_source_respects_filter_and_output_batch_size() -> None:
    reader, dataset, table = fixture()
    from un_migration.filters import parse_filter

    result = transform_source(
        reader,
        dataset,
        select_mapping(table, dataset.id),
        default_registry(),
        batch_size=2,
        filter_expression=parse_filter("diameter >= 6"),
    )

    assert result.metrics.selected == 2
    assert result.metrics.transformed == 1
    assert [record["asset_identifier"] for record in result.batches[0]] == ["WM-3"]


def test_transform_source_does_not_mutate_memory_records() -> None:
    reader, dataset, table = fixture()

    transform_source(
        reader,
        dataset,
        select_mapping(table, dataset.id),
        default_registry(),
        batch_size=2,
    )

    original = next(reader.read_batches(dataset, None, 3))
    assert original[0] == {"asset_id": "wm-1", "diameter": 4}
