from un_migration.domain.schema import DatasetRef
from un_migration.ports.source import SourceReader


def assert_source_reader_contract(
    reader: SourceReader,
    dataset: DatasetRef,
) -> None:
    capabilities = reader.capabilities()
    assert capabilities.supports("inventory")
    assert capabilities.supports("count")
    assert capabilities.supports("read")
    assert reader.inventory(dataset).dataset.id == dataset.id
    expected = reader.count(dataset, None)
    batches = tuple(reader.read_batches(dataset, None, batch_size=2))
    assert all(0 < len(batch) <= 2 for batch in batches)
    assert sum(len(batch) for batch in batches) == expected
