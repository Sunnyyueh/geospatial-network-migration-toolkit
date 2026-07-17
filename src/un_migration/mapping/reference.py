import csv
import io
import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from un_migration.domain.errors import MappingError
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import FieldType
from un_migration.mapping.models import (
    DatasetMapping,
    FieldMapping,
    NullPolicy,
    ReferenceTable,
    TransformSpec,
)

REFERENCE_HEADERS = (
    "schema_version",
    "source_dataset",
    "target_dataset",
    "source_field",
    "target_field",
    "target_type",
    "required",
    "null_policy",
    "default",
    "transform",
    "transform_parameters",
)


def _error(code: str, message: str, guidance: str) -> MappingError:
    return MappingError(code=code, message=message, guidance=guidance)


def _parse_required(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise ValueError("required must be true or false")
    return normalized == "true"


def _parse_parameters(value: str) -> Mapping[str, object]:
    parsed = json.loads(value or "{}")
    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise ValueError("transform_parameters must be a JSON object")
    return cast(dict[str, object], parsed)


def _parse_row(row: dict[str, str | None], line: int) -> FieldMapping:
    if any(row.get(header) is None for header in REFERENCE_HEADERS):
        raise ValueError(f"row {line} has missing columns")
    try:
        return FieldMapping(
            source_field=cast(str, row["source_field"]),
            target_field=cast(str, row["target_field"]),
            target_type=FieldType(cast(str, row["target_type"]).strip().casefold()),
            required=_parse_required(cast(str, row["required"])),
            null_policy=NullPolicy(cast(str, row["null_policy"]).strip().casefold()),
            default=cast(str, row["default"]) or None,
            transform=TransformSpec(
                name=cast(str, row["transform"]) or "identity",
                parameters=_parse_parameters(cast(str, row["transform_parameters"])),
            ),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError(f"row {line} is invalid") from error


def load_reference(path: str | Path) -> ReferenceTable:
    """Load a strict, versioned CSV reference table."""

    reference_path = Path(path)
    if not reference_path.is_file():
        raise _error(
            "reference.not-found",
            f"Reference table does not exist: {reference_path}",
            "Provide an existing CSV reference table.",
        )

    try:
        with reference_path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames is None:
                raise _error(
                    "reference.empty",
                    "Reference table is empty.",
                    "Add the required header and at least one mapping row.",
                )
            missing = set(REFERENCE_HEADERS) - set(reader.fieldnames)
            if missing:
                raise _error(
                    "reference.header",
                    "Reference table is missing required columns: "
                    f"{', '.join(sorted(missing))}.",
                    "Add every required version 1 reference-table column.",
                )
            rows = list(reader)
    except MappingError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise _error(
            "reference.row",
            "Reference table could not be read as strict UTF-8 CSV.",
            "Correct the CSV encoding, quoting, and row structure.",
        ) from error

    if not rows:
        raise _error(
            "reference.empty",
            "Reference table has no mapping rows.",
            "Add at least one source-to-target field mapping.",
        )

    grouped: dict[tuple[DatasetId, DatasetId], list[FieldMapping]] = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        version = (row.get("schema_version") or "").strip()
        if version != "1":
            raise _error(
                "reference.version",
                f"Reference row {line} uses unsupported schema version {version!r}.",
                "Set schema_version to 1 on every row.",
            )
        try:
            source = DatasetId(row["source_dataset"] or "")
            target = DatasetId(row["target_dataset"] or "")
            mapping = _parse_row(row, line)
        except (KeyError, TypeError, ValueError) as error:
            raise _error(
                "reference.row",
                f"Reference row {line} is invalid.",
                "Correct identifiers, enum values, booleans, defaults, and "
                "JSON parameters.",
            ) from error
        grouped[(source, target)].append(mapping)

    try:
        datasets = tuple(
            DatasetMapping(
                source_dataset=source,
                target_dataset=target,
                fields=tuple(fields),
            )
            for (source, target), fields in grouped.items()
        )
        return ReferenceTable(schema_version=1, datasets=datasets)
    except ValueError as error:
        raise _error(
            "reference.row",
            "Reference table contains conflicting or duplicate mappings.",
            "Ensure each source dataset and target field is mapped only once.",
        ) from error


def normalize_reference(table: ReferenceTable) -> str:
    """Serialize a reference table to canonical version 1 CSV."""

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=REFERENCE_HEADERS,
        lineterminator="\n",
    )
    writer.writeheader()
    for dataset in table.datasets:
        for mapping in dataset.fields:
            writer.writerow(
                {
                    "schema_version": "1",
                    "source_dataset": dataset.source_dataset,
                    "target_dataset": dataset.target_dataset,
                    "source_field": mapping.source_field,
                    "target_field": mapping.target_field,
                    "target_type": mapping.target_type.value,
                    "required": str(mapping.required).casefold(),
                    "null_policy": mapping.null_policy.value,
                    "default": "" if mapping.default is None else mapping.default,
                    "transform": mapping.transform.name,
                    "transform_parameters": json.dumps(
                        dict(mapping.transform.parameters),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
    return stream.getvalue()
