from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from un_migration.domain.artifacts import Checksum
from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import DatasetInventory, DatasetRef
from un_migration.domain.serialization import fingerprint
from un_migration.ports.source import AdapterCapabilities, SourceReader


@dataclass(frozen=True, slots=True)
class InventoryResult:
    """Ordered inventories, adapter evidence, and deterministic fingerprints."""

    adapter: AdapterCapabilities
    inventories: tuple[DatasetInventory, ...]
    fingerprints: Mapping[DatasetId, Checksum]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "fingerprints",
            MappingProxyType(dict(self.fingerprints)),
        )


@dataclass(frozen=True, slots=True)
class InventoryComparison:
    """Portable schema and record-count differences."""

    added_fields: tuple[str, ...]
    removed_fields: tuple[str, ...]
    changed_fields: tuple[str, ...]
    feature_count_delta: int

    @property
    def unchanged(self) -> bool:
        return not (
            self.added_fields
            or self.removed_fields
            or self.changed_fields
            or self.feature_count_delta
        )


class InventoryService:
    """Collect deterministic inventory evidence through a SourceReader port."""

    def __init__(self, source: SourceReader) -> None:
        self._source = source

    def collect(self, datasets: tuple[DatasetRef, ...]) -> InventoryResult:
        inventories = tuple(self._source.inventory(dataset) for dataset in datasets)
        return InventoryResult(
            adapter=self._source.capabilities(),
            inventories=inventories,
            fingerprints={item.dataset.id: fingerprint(item) for item in inventories},
        )


def compare_inventories(
    before: DatasetInventory,
    after: DatasetInventory,
) -> InventoryComparison:
    """Compare two inventories for the same logical dataset."""

    if before.dataset.id != after.dataset.id:
        raise ValueError("inventory comparison requires matching dataset IDs")

    before_fields = {field.name.casefold(): field for field in before.fields}
    after_fields = {field.name.casefold(): field for field in after.fields}
    before_names = set(before_fields)
    after_names = set(after_fields)

    return InventoryComparison(
        added_fields=tuple(
            sorted(after_fields[name].name for name in after_names - before_names)
        ),
        removed_fields=tuple(
            sorted(before_fields[name].name for name in before_names - after_names)
        ),
        changed_fields=tuple(
            sorted(
                after_fields[name].name
                for name in before_names & after_names
                if before_fields[name] != after_fields[name]
            )
        ),
        feature_count_delta=after.feature_count - before.feature_count,
    )
