import pytest

from un_migration.domain.errors import TransformationError
from un_migration.domain.identity import DatasetId
from un_migration.mapping.models import TransformSpec
from un_migration.transformation.registry import (
    TransformContext,
    TransformRegistry,
)


def test_registry_applies_registered_transform() -> None:
    registry = TransformRegistry()
    registry.register("double", lambda value, _: int(str(value)) * 2)

    assert registry.apply(TransformSpec("double"), "4") == 8
    assert registry.names == ("double",)


def test_registry_rejects_duplicate_registration() -> None:
    registry = TransformRegistry()
    registry.register("identity", lambda value, _: value)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("IDENTITY", lambda value, _: value)


@pytest.mark.parametrize("name", ["", "bad-name", "9transform"])
def test_registry_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValueError, match="transformation name"):
        TransformRegistry().register(name, lambda value, _: value)


def test_unknown_transform_uses_stable_error() -> None:
    with pytest.raises(TransformationError) as raised:
        TransformRegistry().apply(TransformSpec("missing"), "value")

    assert raised.value.code == "transform.unknown"


def test_transform_failure_is_wrapped_with_safe_context() -> None:
    registry = TransformRegistry()

    def broken(value: object, parameters: object) -> object:
        del value, parameters
        raise RuntimeError("secret backend details")

    registry.register("broken", broken)  # type: ignore[arg-type]
    context = TransformContext(
        dataset_id=DatasetId("water-mains"),
        source_field="diameter",
        target_field="diameter_mm",
        record_id="WM-001",
    )

    with pytest.raises(TransformationError) as raised:
        registry.apply(TransformSpec("broken"), 4, context)

    assert raised.value.code == "transform.failed"
    assert raised.value.context.dataset_id == "water-mains"
    assert "secret" not in raised.value.message


def test_context_rejects_blank_field_names() -> None:
    with pytest.raises(ValueError, match="source_field"):
        TransformContext(
            dataset_id=DatasetId("water-mains"),
            source_field=" ",
            target_field="diameter_mm",
        )
