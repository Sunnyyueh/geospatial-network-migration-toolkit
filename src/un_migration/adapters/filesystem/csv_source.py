import csv
import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType

from un_migration.config.models import DatasetConfig
from un_migration.domain.errors import (
    CapabilityError,
    ConfigurationError,
    ErrorContext,
    InventoryError,
)
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import (
    DatasetInventory,
    DatasetRef,
    FieldSchema,
    FieldType,
)
from un_migration.filters.ast import (
    And,
    Compare,
    Expression,
    InList,
    IsNull,
    Not,
    Or,
)
from un_migration.filters.evaluate import evaluate
from un_migration.ports.source import (
    AdapterCapabilities,
    Record,
    RecordBatch,
)


def _infer_value(value: str) -> FieldType:
    lowered = value.casefold()
    if lowered in {"true", "false"}:
        return FieldType.BOOLEAN
    try:
        int(value)
    except ValueError:
        pass
    else:
        return FieldType.INTEGER
    try:
        number = float(value)
    except ValueError:
        pass
    else:
        if math.isfinite(number):
            return FieldType.FLOAT
    try:
        date.fromisoformat(value)
    except ValueError:
        pass
    else:
        return FieldType.DATE
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return FieldType.STRING
    return FieldType.DATETIME


def _merge_type(
    current: FieldType | None,
    observed: FieldType,
) -> FieldType:
    if current is None or current is observed:
        return observed
    pair = {current, observed}
    if pair == {FieldType.INTEGER, FieldType.FLOAT}:
        return FieldType.FLOAT
    if pair == {FieldType.DATE, FieldType.DATETIME}:
        return FieldType.DATETIME
    return FieldType.STRING


@dataclass
class _ColumnProfile:
    name: str
    type: FieldType | None = None
    nullable: bool = False
    observed_nonblank: bool = False

    def observe(self, value: str) -> None:
        if value == "":
            self.nullable = True
            return
        self.observed_nonblank = True
        self.type = _merge_type(self.type, _infer_value(value))

    def to_field(self) -> FieldSchema:
        return FieldSchema(
            name=self.name,
            type=self.type or FieldType.STRING,
            nullable=self.nullable or not self.observed_nonblank,
        )


class CsvSourceReader:
    """Inventory and stream managed UTF-8 CSV datasets."""

    def __init__(
        self,
        workspace: Path,
        datasets: tuple[DatasetConfig, ...],
    ) -> None:
        self._workspace = workspace.expanduser().resolve()
        self._datasets = {DatasetId(dataset.id): dataset for dataset in datasets}

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_name="csv",
            operations=frozenset({"inventory", "count", "read", "filter"}),
        )

    @staticmethod
    def _filter(filter_expression: object | None) -> Expression | None:
        if filter_expression is None:
            return None
        if isinstance(filter_expression, (Compare, InList, IsNull, Not, And, Or)):
            return filter_expression
        raise CapabilityError(
            code="adapter.filter-unsupported",
            message="CSV source received an unsupported filter object.",
            guidance="Parse filter text into the toolkit filter AST first.",
        )

    def _config(self, dataset_id: DatasetId) -> DatasetConfig:
        try:
            return self._datasets[dataset_id]
        except KeyError as error:
            raise InventoryError(
                code="csv.dataset-not-configured",
                message=f"CSV dataset is not configured: {dataset_id}",
                guidance="Add the dataset to source.datasets.",
                context=ErrorContext(dataset_id=str(dataset_id)),
            ) from error

    def _path(self, dataset_id: DatasetId) -> Path:
        config = self._config(dataset_id)
        path = (self._workspace / config.path).resolve()
        if not path.is_relative_to(self._workspace):
            raise InventoryError(
                code="csv.path",
                message=f"CSV dataset escapes its workspace: {dataset_id}",
                guidance="Use a managed workspace-relative dataset path.",
                context=ErrorContext(dataset_id=str(dataset_id)),
            )
        if not path.is_file():
            raise InventoryError(
                code="csv.not-found",
                message=f"CSV dataset does not exist: {config.path}",
                guidance="Create the source file or correct source.datasets.",
                context=ErrorContext(dataset_id=str(dataset_id)),
            )
        return path

    @staticmethod
    def _raise_csv_error(
        code: str,
        message: str,
        dataset_id: DatasetId,
    ) -> InventoryError:
        return InventoryError(
            code=code,
            message=message,
            guidance="Correct the CSV structure and retry inventory.",
            context=ErrorContext(dataset_id=str(dataset_id)),
        )

    def _raw_rows(
        self,
        dataset_id: DatasetId,
    ) -> Iterator[tuple[int, list[str]]]:
        path = self._path(dataset_id)
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream, strict=True)
                yield from enumerate(reader, start=1)
        except (OSError, UnicodeError, csv.Error) as error:
            raise InventoryError(
                code="csv.read",
                message=f"CSV dataset could not be read: {dataset_id}",
                guidance="Verify UTF-8 encoding and valid CSV quoting.",
                context=ErrorContext(dataset_id=str(dataset_id)),
            ) from error

    def _header_and_rows(
        self,
        dataset_id: DatasetId,
    ) -> tuple[list[str], Iterator[tuple[int, list[str]]]]:
        rows = self._raw_rows(dataset_id)
        try:
            _, header = next(rows)
        except StopIteration:
            raise self._raise_csv_error(
                "csv.header",
                "CSV dataset is empty and has no header.",
                dataset_id,
            ) from None
        names = [name.strip() for name in header]
        folded = [name.casefold() for name in names]
        if (
            not names
            or any(not name for name in names)
            or len(folded) != len(set(folded))
        ):
            raise self._raise_csv_error(
                "csv.header",
                "CSV header names must be nonempty and unique.",
                dataset_id,
            )
        return names, rows

    def inventory(self, dataset: DatasetRef) -> DatasetInventory:
        names, rows = self._header_and_rows(dataset.id)
        profiles = [_ColumnProfile(name) for name in names]
        feature_count = 0
        for row_number, row in rows:
            if len(row) != len(names):
                raise self._raise_csv_error(
                    "csv.row-width",
                    (
                        f"CSV row {row_number} has {len(row)} values; "
                        f"expected {len(names)}."
                    ),
                    dataset.id,
                )
            feature_count += 1
            for profile, value in zip(profiles, row, strict=True):
                profile.observe(value.strip())
        config = self._config(dataset.id)
        return DatasetInventory(
            dataset=DatasetRef(dataset.id, config.path.as_posix()),
            fields=tuple(profile.to_field() for profile in profiles),
            feature_count=feature_count,
        )

    def count(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
    ) -> int:
        return sum(
            len(batch)
            for batch in self.read_batches(dataset, filter_expression, batch_size=1000)
        )

    @staticmethod
    def _convert(value: str, field_type: FieldType) -> object:
        if value == "":
            return None
        if field_type is FieldType.BOOLEAN:
            return value.casefold() == "true"
        if field_type is FieldType.INTEGER:
            return int(value)
        if field_type is FieldType.FLOAT:
            return float(value)
        if field_type is FieldType.DATE:
            return date.fromisoformat(value)
        if field_type is FieldType.DATETIME:
            return datetime.fromisoformat(value)
        return value

    def read_batches(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
        batch_size: int,
    ) -> Iterator[RecordBatch]:
        expression = self._filter(filter_expression)
        if batch_size <= 0:
            raise ConfigurationError(
                code="runtime.batch-size",
                message="Batch size must be positive.",
                guidance="Set runtime.batch_size to a value of at least 1.",
            )

        inventory = self.inventory(dataset)
        names, rows = self._header_and_rows(dataset.id)
        batch: list[Record] = []
        for row_number, row in rows:
            if len(row) != len(names):
                raise self._raise_csv_error(
                    "csv.row-width",
                    (
                        f"CSV row {row_number} has {len(row)} values; "
                        f"expected {len(names)}."
                    ),
                    dataset.id,
                )
            record = {
                field.name: self._convert(value.strip(), field.type)
                for field, value in zip(inventory.fields, row, strict=True)
            }
            if expression is not None and not evaluate(expression, record):
                continue
            batch.append(MappingProxyType(record))
            if len(batch) == batch_size:
                yield tuple(batch)
                batch = []
        if batch:
            yield tuple(batch)
