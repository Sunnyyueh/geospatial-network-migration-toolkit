# Foundation and Domain Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox '- [ ]' syntax for tracking.

**Goal:** Build an installable, typed Python package with stable domain
primitives, serialization, adapter protocols, and a working version and doctor
CLI as the first executable vertical slice of the migration toolkit.

**Architecture:** Use a Python 3.11+ src layout. Domain objects are immutable and
dependency-light; Pydantic is reserved for validated boundary models. Ports are
typing protocols, serialization is canonical and deterministic, and the CLI
depends on the public API rather than internal implementations.

**Tech Stack:** Python 3.11+, Hatchling, Pydantic 2, Typer, PyYAML, pytest,
pytest-cov, Hypothesis, Ruff, and mypy.

## Global Constraints

- Core modules never import ArcPy.
- Public fixtures and examples contain only synthetic information.
- The base package must work without proprietary software.
- Python source uses complete type annotations and immutable domain values.
- Tests use deterministic clocks and identifiers.
- Every task follows red-green-refactor and ends with one coherent commit.
- Empty commits, scaffold-only modules, and history padding are prohibited.

---

## File Responsibility Map

| Path | Responsibility |
| --- | --- |
| pyproject.toml | Build metadata, dependencies, entry point, and tool settings. |
| src/un_migration/_version.py | Single source of package version. |
| src/un_migration/__init__.py | Deliberate stable public exports. |
| src/un_migration/domain/errors.py | Typed operational error hierarchy. |
| src/un_migration/domain/identity.py | Validated stable identifiers. |
| src/un_migration/domain/time.py | Clock protocol and UTC system clock. |
| src/un_migration/domain/status.py | Run states, severity, and acceptance enums. |
| src/un_migration/domain/schema.py | Dataset, field, geometry, and inventory values. |
| src/un_migration/domain/findings.py | Validation rules, evidence, and findings. |
| src/un_migration/domain/artifacts.py | Artifact metadata and integrity values. |
| src/un_migration/domain/runs.py | Plans, steps, checkpoints, runs, and summaries. |
| src/un_migration/domain/serialization.py | Canonical primitive conversion and hashing. |
| src/un_migration/ports/source.py | SourceReader protocol. |
| src/un_migration/ports/staging.py | StagingWriter protocol. |
| src/un_migration/ports/services.py | Artifact, checkpoint, notification, and deployment ports. |
| src/un_migration/api.py | Supported Python facade for package information. |
| src/un_migration/cli.py | Typer application with version and doctor commands. |
| tests/unit | Focused tests for each domain module. |
| tests/contract | Runtime protocol-shape tests. |
| tests/cli | CLI behavior and exit-code tests. |

---

### Task 1: Package and Tooling Foundation

**Files:**

- Create: pyproject.toml
- Create: .gitignore
- Create: src/un_migration/__init__.py
- Create: src/un_migration/_version.py
- Create: tests/unit/test_package.py

**Interfaces:**

- Consumes: no earlier application interfaces.
- Produces: un_migration.__version__: str and an installable un-migrate entry
  point targeting un_migration.cli:app.

- [ ] **Step 1: Write the failing package metadata test**

~~~python
from importlib.metadata import version

import un_migration


def test_public_version_matches_installed_metadata() -> None:
    assert un_migration.__version__ == version(
        'geospatial-network-migration-toolkit'
    )
    major, minor, patch = un_migration.__version__.split('.')
    assert all(part.isdigit() for part in (major, minor, patch))
~~~

- [ ] **Step 2: Run the test and verify the missing package failure**

Run:

    python -m pytest tests/unit/test_package.py -q

Expected: collection fails with ModuleNotFoundError for un_migration.

- [ ] **Step 3: Add build metadata and the minimal public package**

Create pyproject.toml with this exact baseline:

~~~toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "geospatial-network-migration-toolkit"
dynamic = ["version"]
description = "Plan, run, validate, and document geospatial network migrations."
readme = "README.md"
requires-python = ">=3.11"
license = {file = "LICENSE"}
authors = [{name = "Sunny Yueh"}]
dependencies = [
  "jinja2>=3.1,<4",
  "pydantic>=2.7,<3",
  "PyYAML>=6,<7",
  "typer>=0.12,<1",
]

[project.optional-dependencies]
dev = [
  "build>=1.2,<2",
  "hypothesis>=6.100,<7",
  "mypy>=1.10,<2",
  "pytest>=8.2,<9",
  "pytest-cov>=5,<7",
  "ruff>=0.5,<1",
  "twine>=5,<7",
]

[project.scripts]
un-migrate = "un_migration.cli:app"

[tool.hatch.version]
path = "src/un_migration/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["src/un_migration"]

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src/un_migration"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-config --strict-markers"

[tool.coverage.run]
source = ["un_migration"]
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 85
~~~

~~~python
# src/un_migration/_version.py
__version__ = '0.1.0'
~~~

~~~python
# src/un_migration/__init__.py
from un_migration._version import __version__

__all__ = ['__version__']
~~~

Create .gitignore with:

~~~gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.hypothesis/
.coverage
htmlcov/
build/
dist/
*.egg-info/
.DS_Store
.idea/
.vscode/
.env
.env.*
*.sde
*.gdb/
outputs/
~~~

- [ ] **Step 4: Install editable development dependencies and run checks**

Run:

    python -m pip install -e '.[dev]'
    python -m pytest tests/unit/test_package.py -q
    python -m build
    python -m twine check dist/*

Expected: one test passes; wheel and source distribution build; Twine reports
both distributions PASSED.

- [ ] **Step 5: Commit**

    git add pyproject.toml .gitignore src tests/unit/test_package.py
    git commit -m "build: establish installable Python package"

---

### Task 2: Typed Error Model

**Files:**

- Create: src/un_migration/domain/__init__.py
- Create: src/un_migration/domain/errors.py
- Create: tests/unit/domain/test_errors.py

**Interfaces:**

- Consumes: Python exception semantics.
- Produces: ErrorContext, MigrationError, ConfigurationError,
  CapabilityError, InventoryError, MappingError, FilterSyntaxError,
  TransformationError, StagingError, ValidationExecutionError,
  DeploymentError, NotificationError, and IntegrityError.

- [ ] **Step 1: Write failing tests for stable safe diagnostics**

~~~python
from un_migration.domain.errors import ConfigurationError, ErrorContext


def test_error_exposes_safe_structured_diagnostic() -> None:
    error = ConfigurationError(
        code='config.missing',
        message='Required source path is missing.',
        guidance='Set source.workspace in the project file.',
        retryable=False,
        context=ErrorContext(run_id='run-1', step_id='configure'),
    )

    assert str(error) == 'config.missing: Required source path is missing.'
    assert error.to_dict() == {
        'code': 'config.missing',
        'message': 'Required source path is missing.',
        'guidance': 'Set source.workspace in the project file.',
        'retryable': False,
        'context': {'run_id': 'run-1', 'step_id': 'configure'},
    }
~~~

- [ ] **Step 2: Run the test and verify the import failure**

    python -m pytest tests/unit/domain/test_errors.py -q

Expected: collection fails because domain.errors does not exist.

- [ ] **Step 3: Implement immutable context and error subclasses**

~~~python
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorContext:
    run_id: str | None = None
    step_id: str | None = None
    dataset_id: str | None = None


class MigrationError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        guidance: str,
        retryable: bool = False,
        context: ErrorContext | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.guidance = guidance
        self.retryable = retryable
        self.context = context or ErrorContext()

    def __str__(self) -> str:
        return f'{self.code}: {self.message}'

    def to_dict(self) -> dict[str, Any]:
        context = {
            key: value
            for key, value in asdict(self.context).items()
            if value is not None
        }
        return {
            'code': self.code,
            'message': self.message,
            'guidance': self.guidance,
            'retryable': self.retryable,
            'context': context,
        }
~~~

Each named subclass directly extends MigrationError:

~~~python
class ConfigurationError(MigrationError):
    pass


class CapabilityError(MigrationError):
    pass


class InventoryError(MigrationError):
    pass


class MappingError(MigrationError):
    pass


class FilterSyntaxError(MigrationError):
    pass


class TransformationError(MigrationError):
    pass


class StagingError(MigrationError):
    pass


class ValidationExecutionError(MigrationError):
    pass


class DeploymentError(MigrationError):
    pass


class NotificationError(MigrationError):
    pass


class IntegrityError(MigrationError):
    pass
~~~

- [ ] **Step 4: Run focused tests and static checks**

    python -m pytest tests/unit/domain/test_errors.py -q
    python -m mypy src/un_migration/domain/errors.py

Expected: tests pass and mypy reports success.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain tests/unit/domain/test_errors.py
    git commit -m "feat: add structured migration errors"

---

### Task 3: Stable Identity Values

**Files:**

- Create: src/un_migration/domain/identity.py
- Create: tests/unit/domain/test_identity.py

**Interfaces:**

- Consumes: ConfigurationError from Task 2.
- Produces: StableId, RunId, DatasetId, StepId, FindingId, ArtifactId,
  IdGenerator, and Uuid7LikeGenerator.new(prefix: str) -> str.

- [ ] **Step 1: Write failing validation and generator tests**

~~~python
from un_migration.domain.identity import DatasetId, SequenceIdGenerator


def test_dataset_id_normalizes_safe_value() -> None:
    assert str(DatasetId(' Water Mains ')) == 'water-mains'


def test_sequence_generator_is_deterministic() -> None:
    generator = SequenceIdGenerator(start=7)
    assert generator.new('run') == 'run-000007'
    assert generator.new('step') == 'step-000008'
~~~

- [ ] **Step 2: Run the test and verify the missing module failure**

    python -m pytest tests/unit/domain/test_identity.py -q

Expected: collection fails because identity.py does not exist.

- [ ] **Step 3: Implement validated string values and generators**

StableId subclasses str, strips input, lowercases it, replaces internal
whitespace and underscores with hyphens, and rejects values outside
[a-z0-9][a-z0-9.-]{0,127}. Implement:

~~~python
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol

_SAFE_ID = re.compile(r'^[a-z0-9][a-z0-9.-]{0,127}$')


class StableId(str):
    def __new__(cls, value: str) -> 'StableId':
        normalized = re.sub(r'[\s_]+', '-', value.strip().casefold())
        if not _SAFE_ID.fullmatch(normalized):
            raise ValueError(f'Invalid {cls.__name__}: {value!r}')
        return super().__new__(cls, normalized)


class RunId(StableId):
    pass


class DatasetId(StableId):
    pass


class StepId(StableId):
    pass


class FindingId(StableId):
    pass


class ArtifactId(StableId):
    pass


class IdGenerator(Protocol):
    def new(self, prefix: str) -> str: ...


@dataclass
class SequenceIdGenerator:
    start: int = 1
    _next: int = field(init=False)

    def __post_init__(self) -> None:
        self._next = self.start

    def new(self, prefix: str) -> str:
        value = f'{prefix}-{self._next:06d}'
        self._next += 1
        return value


class Uuid7LikeGenerator:
    def new(self, prefix: str) -> str:
        millis = int(time.time() * 1000)
        suffix = uuid.uuid4().hex[:16]
        return f'{prefix}-{millis:013d}-{suffix}'
~~~

Uuid7LikeGenerator combines a UTC millisecond timestamp with UUID4 randomness
without claiming strict UUIDv7 conformance.

- [ ] **Step 4: Run focused tests**

    python -m pytest tests/unit/domain/test_identity.py -q

Expected: normalization, rejection, and deterministic generation tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/identity.py tests/unit/domain/test_identity.py
    git commit -m "feat: introduce stable domain identifiers"

---

### Task 4: Deterministic Time Abstraction

**Files:**

- Create: src/un_migration/domain/time.py
- Create: tests/unit/domain/test_time.py

**Interfaces:**

- Consumes: timezone-aware datetime values.
- Produces: Clock.now() -> datetime, SystemClock, and FixedClock.

- [ ] **Step 1: Write failing UTC behavior tests**

~~~python
from datetime import datetime, timezone

from un_migration.domain.time import FixedClock, SystemClock


def test_fixed_clock_returns_supplied_utc_instant() -> None:
    instant = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    assert FixedClock(instant).now() is instant


def test_system_clock_is_timezone_aware() -> None:
    assert SystemClock().now().utcoffset() == timezone.utc.utcoffset(None)
~~~

- [ ] **Step 2: Run the test and verify the missing module failure**

    python -m pytest tests/unit/domain/test_time.py -q

Expected: collection fails because time.py does not exist.

- [ ] **Step 3: Implement the clock protocol**

~~~python
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class FixedClock:
    instant: datetime

    def __post_init__(self) -> None:
        if self.instant.tzinfo is None:
            raise ValueError('FixedClock requires a timezone-aware instant.')

    def now(self) -> datetime:
        return self.instant


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
~~~

- [ ] **Step 4: Run tests and type checks**

    python -m pytest tests/unit/domain/test_time.py -q
    python -m mypy src/un_migration/domain/time.py

Expected: all checks pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/time.py tests/unit/domain/test_time.py
    git commit -m "feat: add deterministic clock abstraction"

---

### Task 5: Run Status and Acceptance Policies

**Files:**

- Create: src/un_migration/domain/status.py
- Create: tests/unit/domain/test_status.py

**Interfaces:**

- Consumes: no earlier domain types.
- Produces: RunState, Severity, FindingStatus, AcceptanceStatus,
  can_transition(current, target) -> bool, and highest_severity(values).

- [ ] **Step 1: Write failing state-machine tests**

~~~python
import pytest

from un_migration.domain.status import RunState, Severity, can_transition


@pytest.mark.parametrize(
    ('current', 'target'),
    [
        (RunState.CREATED, RunState.CONFIGURED),
        (RunState.VALIDATED, RunState.ACCEPTED),
        (RunState.ACCEPTED, RunState.DEPLOYED),
        (RunState.STAGED, RunState.FAILED),
    ],
)
def test_allowed_transitions(current: RunState, target: RunState) -> None:
    assert can_transition(current, target)


def test_severity_order_matches_acceptance_semantics() -> None:
    assert Severity.CRITICAL > Severity.ERROR > Severity.WARNING > Severity.INFO
~~~

- [ ] **Step 2: Run and observe the missing module failure**

    python -m pytest tests/unit/domain/test_status.py -q

Expected: collection fails because status.py does not exist.

- [ ] **Step 3: Implement string and ordered severity enums**

Implement the complete enums and transition table:

~~~python
from enum import Enum, IntEnum
from typing import Iterable


class RunState(str, Enum):
    CREATED = 'created'
    CONFIGURED = 'configured'
    PLANNED = 'planned'
    INVENTORIED = 'inventoried'
    EXTRACTED = 'extracted'
    TRANSFORMED = 'transformed'
    STAGED = 'staged'
    VALIDATED = 'validated'
    ACCEPTED = 'accepted'
    DEPLOYED = 'deployed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'


class Severity(IntEnum):
    INFO = 10
    WARNING = 20
    ERROR = 30
    CRITICAL = 40


class FindingStatus(str, Enum):
    PASSED = 'passed'
    FAILED = 'failed'
    SKIPPED = 'skipped'


class AcceptanceStatus(str, Enum):
    ACCEPTED = 'accepted'
    ACCEPTED_WITH_WARNINGS = 'accepted_with_warnings'
    REJECTED = 'rejected'
    INCOMPLETE = 'incomplete'


_NEXT: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({RunState.CONFIGURED}),
    RunState.CONFIGURED: frozenset({RunState.PLANNED}),
    RunState.PLANNED: frozenset({RunState.INVENTORIED}),
    RunState.INVENTORIED: frozenset({RunState.EXTRACTED}),
    RunState.EXTRACTED: frozenset({RunState.TRANSFORMED}),
    RunState.TRANSFORMED: frozenset({RunState.STAGED}),
    RunState.STAGED: frozenset({RunState.VALIDATED}),
    RunState.VALIDATED: frozenset({RunState.ACCEPTED}),
    RunState.ACCEPTED: frozenset({RunState.DEPLOYED}),
    RunState.DEPLOYED: frozenset(),
    RunState.CANCELLED: frozenset(),
    RunState.FAILED: frozenset(),
}


def can_transition(current: RunState, target: RunState) -> bool:
    if target in {RunState.CANCELLED, RunState.FAILED}:
        return current not in {
            RunState.DEPLOYED,
            RunState.CANCELLED,
            RunState.FAILED,
        }
    return target in _NEXT[current]


def highest_severity(values: Iterable[Severity]) -> Severity | None:
    return max(values, default=None)
~~~

- [ ] **Step 4: Run focused and property tests**

    python -m pytest tests/unit/domain/test_status.py -q

Expected: transitions, terminal-state rejection, and severity ordering pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/status.py tests/unit/domain/test_status.py
    git commit -m "feat: model migration run state transitions"

---

### Task 6: Dataset Schema and Inventory Models

**Files:**

- Create: src/un_migration/domain/schema.py
- Create: tests/unit/domain/test_schema.py

**Interfaces:**

- Consumes: DatasetId from Task 3.
- Produces: FieldType, GeometryType, FieldSchema, DomainValue, CodedDomain,
  GeometrySchema, DatasetRef, and DatasetInventory.

- [ ] **Step 1: Write failing immutable schema tests**

~~~python
import pytest

from un_migration.domain.identity import DatasetId
from un_migration.domain.schema import (
    DatasetInventory,
    DatasetRef,
    FieldSchema,
    FieldType,
)


def test_inventory_rejects_duplicate_field_names() -> None:
    field = FieldSchema(name='asset_id', type=FieldType.STRING, nullable=False)

    with pytest.raises(ValueError, match='duplicate field'):
        DatasetInventory(
            dataset=DatasetRef(DatasetId('water-mains'), 'WaterMains'),
            fields=(field, field),
            feature_count=2,
        )
~~~

- [ ] **Step 2: Run and observe the missing schema module**

    python -m pytest tests/unit/domain/test_schema.py -q

Expected: collection fails because schema.py does not exist.

- [ ] **Step 3: Implement schema values and invariants**

Implement the schema values:

~~~python
from dataclasses import dataclass
from enum import Enum

from un_migration.domain.identity import DatasetId


class FieldType(str, Enum):
    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float'
    DECIMAL = 'decimal'
    BOOLEAN = 'boolean'
    DATE = 'date'
    DATETIME = 'datetime'
    UUID = 'uuid'
    JSON = 'json'
    GEOMETRY = 'geometry'


class GeometryType(str, Enum):
    POINT = 'point'
    MULTIPOINT = 'multipoint'
    POLYLINE = 'polyline'
    POLYGON = 'polygon'
    UNKNOWN = 'unknown'


@dataclass(frozen=True, slots=True)
class DomainValue:
    code: str | int
    label: str


@dataclass(frozen=True, slots=True)
class CodedDomain:
    name: str
    values: tuple[DomainValue, ...]

    def __post_init__(self) -> None:
        codes = [value.code for value in self.values]
        if len(codes) != len(set(codes)):
            raise ValueError(f'duplicate domain code in {self.name!r}')


@dataclass(frozen=True, slots=True)
class FieldSchema:
    name: str
    type: FieldType
    nullable: bool = True
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    domain: CodedDomain | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError('field name must not be empty')
        for label, value in (
            ('length', self.length),
            ('precision', self.precision),
            ('scale', self.scale),
        ):
            if value is not None and value < 0:
                raise ValueError(f'{label} must be nonnegative')


@dataclass(frozen=True, slots=True)
class GeometrySchema:
    type: GeometryType
    spatial_reference: str | None = None
    has_z: bool = False
    has_m: bool = False


@dataclass(frozen=True, slots=True)
class DatasetRef:
    id: DatasetId
    physical_name: str


@dataclass(frozen=True, slots=True)
class DatasetInventory:
    dataset: DatasetRef
    fields: tuple[FieldSchema, ...]
    feature_count: int
    geometry: GeometrySchema | None = None

    def __post_init__(self) -> None:
        if self.feature_count < 0:
            raise ValueError('feature_count must be nonnegative')
        names = [field.name.casefold() for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError('duplicate field name')

    def field(self, name: str) -> FieldSchema | None:
        normalized = name.casefold()
        return next(
            (
                field
                for field in self.fields
                if field.name.casefold() == normalized
            ),
            None,
        )
~~~

- [ ] **Step 4: Run schema tests**

    python -m pytest tests/unit/domain/test_schema.py -q

Expected: valid construction, invariant failures, and lookup tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/schema.py tests/unit/domain/test_schema.py
    git commit -m "feat: define dataset schema inventory model"

---

### Task 7: Validation Rules and Findings

**Files:**

- Create: src/un_migration/domain/findings.py
- Create: tests/unit/domain/test_findings.py

**Interfaces:**

- Consumes: DatasetId and FindingId from Task 3; Severity and FindingStatus from
  Task 5.
- Produces: RuleScope, ValidationRule, Evidence, Finding, FindingCollection,
  and FindingCollection.count_by_severity().

- [ ] **Step 1: Write failing finding aggregation tests**

~~~python
from un_migration.domain.findings import Evidence, Finding, FindingCollection
from un_migration.domain.identity import FindingId
from un_migration.domain.status import FindingStatus, Severity


def test_collection_counts_failed_findings_by_severity() -> None:
    finding = Finding(
        id=FindingId('finding-1'),
        rule_id='required.asset-id',
        status=FindingStatus.FAILED,
        severity=Severity.ERROR,
        message='asset_id is missing',
        remediation='Populate a stable asset identifier.',
        evidence=Evidence(actual=None, expected='non-null'),
    )

    assert FindingCollection((finding,)).count_by_severity() == {'error': 1}
~~~

- [ ] **Step 2: Run and verify missing module failure**

    python -m pytest tests/unit/domain/test_findings.py -q

Expected: collection fails because findings.py does not exist.

- [ ] **Step 3: Implement rule and finding values**

Implement the rule, evidence, finding, and collection values:

~~~python
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum

from un_migration.domain.identity import DatasetId, FindingId
from un_migration.domain.status import FindingStatus, Severity


class RuleScope(str, Enum):
    RUN = 'run'
    DATASET = 'dataset'
    FIELD = 'field'
    RECORD = 'record'


@dataclass(frozen=True, slots=True)
class ValidationRule:
    id: str
    title: str
    scope: RuleScope
    severity: Severity
    remediation: str
    parameters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Evidence:
    actual: object
    expected: object
    record_id: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    id: FindingId
    rule_id: str
    status: FindingStatus
    severity: Severity
    message: str
    remediation: str | None = None
    evidence: Evidence | None = None
    dataset_id: DatasetId | None = None
    field_name: str | None = None
    skip_reason: str | None = None

    def __post_init__(self) -> None:
        if self.status is FindingStatus.SKIPPED and not self.skip_reason:
            raise ValueError('skipped finding requires skip_reason')
        if self.status is FindingStatus.FAILED and not self.remediation:
            raise ValueError('failed finding requires remediation')


@dataclass(frozen=True, slots=True)
class FindingCollection:
    items: tuple[Finding, ...] = ()

    def __iter__(self) -> Iterator[Finding]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def failed(self) -> tuple[Finding, ...]:
        return tuple(
            item for item in self.items if item.status is FindingStatus.FAILED
        )

    def skipped(self) -> tuple[Finding, ...]:
        return tuple(
            item for item in self.items if item.status is FindingStatus.SKIPPED
        )

    def highest_severity(self) -> Severity | None:
        return max((item.severity for item in self.failed()), default=None)

    def count_by_severity(self) -> dict[str, int]:
        counts = Counter(item.severity.name.lower() for item in self.failed())
        return dict(sorted(counts.items()))
~~~

- [ ] **Step 4: Run focused tests**

    python -m pytest tests/unit/domain/test_findings.py -q

Expected: construction, invariant, filtering, and aggregation tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/findings.py tests/unit/domain/test_findings.py
    git commit -m "feat: add validation finding domain model"

---

### Task 8: Artifacts and Integrity Metadata

**Files:**

- Create: src/un_migration/domain/artifacts.py
- Create: tests/unit/domain/test_artifacts.py

**Interfaces:**

- Consumes: ArtifactId from Task 3.
- Produces: ArtifactKind, Checksum, Artifact and Artifact.verify(bytes) -> bool.

- [ ] **Step 1: Write failing checksum verification tests**

~~~python
from un_migration.domain.artifacts import Artifact, ArtifactKind, Checksum
from un_migration.domain.identity import ArtifactId


def test_artifact_verifies_sha256_payload() -> None:
    payload = b'canonical report'
    artifact = Artifact(
        id=ArtifactId('artifact-report'),
        kind=ArtifactKind.REPORT,
        path='report.json',
        media_type='application/json',
        size=len(payload),
        checksum=Checksum.sha256(payload),
    )

    assert artifact.verify(payload)
    assert not artifact.verify(b'changed')
~~~

- [ ] **Step 2: Run and verify missing module failure**

    python -m pytest tests/unit/domain/test_artifacts.py -q

Expected: collection fails because artifacts.py does not exist.

- [ ] **Step 3: Implement artifacts and checksums**

~~~python
import hashlib
import re
import secrets
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

from un_migration.domain.identity import ArtifactId


class ArtifactKind(str, Enum):
    CONFIGURATION = 'configuration'
    PLAN = 'plan'
    INVENTORY = 'inventory'
    STAGING = 'staging'
    FINDINGS = 'findings'
    REPORT = 'report'
    LOG = 'log'
    MANIFEST = 'manifest'
    DEPLOYMENT = 'deployment'


@dataclass(frozen=True, slots=True)
class Checksum:
    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if self.algorithm != 'sha256':
            raise ValueError('only sha256 checksums are supported')
        if not re.fullmatch(r'[0-9a-f]{64}', self.digest):
            raise ValueError('sha256 digest must be 64 lowercase hex characters')

    @classmethod
    def sha256(cls, payload: bytes) -> 'Checksum':
        return cls('sha256', hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True, slots=True)
class Artifact:
    id: ArtifactId
    kind: ArtifactKind
    path: str
    media_type: str
    size: int
    checksum: Checksum

    def __post_init__(self) -> None:
        path = PurePosixPath(self.path)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('artifact path must be managed and relative')
        if self.size < 0:
            raise ValueError('artifact size must be nonnegative')
        if not self.media_type.strip():
            raise ValueError('artifact media_type must not be empty')

    def verify(self, payload: bytes) -> bool:
        return self.size == len(payload) and secrets.compare_digest(
            self.checksum.digest,
            Checksum.sha256(payload).digest,
        )
~~~

- [ ] **Step 4: Run integrity tests**

    python -m pytest tests/unit/domain/test_artifacts.py -q

Expected: digest, verification, and unsafe-path tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/artifacts.py tests/unit/domain/test_artifacts.py
    git commit -m "feat: model migration artifacts and checksums"

---

### Task 9: Plans, Checkpoints, Runs, and Summaries

**Files:**

- Create: src/un_migration/domain/runs.py
- Create: tests/unit/domain/test_runs.py

**Interfaces:**

- Consumes: Artifact, FindingCollection, RunId, StepId, RunState,
  AcceptanceStatus, and timezone-aware datetime.
- Produces: StepKind, PlanStep, MigrationPlan, Checkpoint, MigrationRun,
  RunMetrics, and RunSummary.

- [ ] **Step 1: Write failing plan dependency tests**

~~~python
from dataclasses import replace

from un_migration.domain.identity import StepId
from un_migration.domain.runs import MigrationPlan, PlanStep, StepKind


def test_plan_orders_steps_by_dependencies() -> None:
    inventory = PlanStep(StepId('inventory'), StepKind.INVENTORY)
    configure = PlanStep(StepId('configure'), StepKind.CONFIGURE)
    inventory = replace(inventory, prerequisites=(configure.id,))

    plan = MigrationPlan((inventory, configure))

    assert [str(step.id) for step in plan.ordered_steps()] == [
        'configure',
        'inventory',
    ]
~~~

- [ ] **Step 2: Run and verify missing module failure**

    python -m pytest tests/unit/domain/test_runs.py -q

Expected: collection fails because runs.py does not exist.

- [ ] **Step 3: Implement execution domain models**

Implement the execution models, using an internal topological-sort helper that
raises ValueError for duplicate IDs, missing prerequisites, or cycles:

~~~python
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from un_migration.domain.artifacts import Artifact, Checksum
from un_migration.domain.errors import ErrorContext, IntegrityError
from un_migration.domain.findings import FindingCollection
from un_migration.domain.identity import RunId, StepId
from un_migration.domain.status import (
    AcceptanceStatus,
    RunState,
    can_transition,
)


class StepKind(str, Enum):
    CONFIGURE = 'configure'
    PLAN = 'plan'
    INVENTORY = 'inventory'
    EXTRACT = 'extract'
    TRANSFORM = 'transform'
    STAGE = 'stage'
    VALIDATE = 'validate'
    REPORT = 'report'
    DEPLOY = 'deploy'
    NOTIFY = 'notify'


@dataclass(frozen=True, slots=True)
class PlanStep:
    id: StepId
    kind: StepKind
    prerequisites: tuple[StepId, ...] = ()
    idempotent: bool = True


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    steps: tuple[PlanStep, ...]

    def ordered_steps(self) -> tuple[PlanStep, ...]:
        by_id = {step.id: step for step in self.steps}
        if len(by_id) != len(self.steps):
            raise ValueError('plan contains duplicate step IDs')
        indegree = {step.id: 0 for step in self.steps}
        dependents: dict[StepId, list[StepId]] = defaultdict(list)
        for step in self.steps:
            for prerequisite in step.prerequisites:
                if prerequisite not in by_id:
                    raise ValueError(f'unknown prerequisite: {prerequisite}')
                indegree[step.id] += 1
                dependents[prerequisite].append(step.id)
        ready = deque(
            step.id for step in self.steps if indegree[step.id] == 0
        )
        ordered: list[PlanStep] = []
        while ready:
            current = ready.popleft()
            ordered.append(by_id[current])
            for dependent in dependents[current]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        if len(ordered) != len(self.steps):
            raise ValueError('plan contains a dependency cycle')
        return tuple(ordered)


@dataclass(frozen=True, slots=True)
class Checkpoint:
    run_id: RunId
    step_id: StepId
    input_checksum: Checksum
    output_checksum: Checksum
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class MigrationRun:
    id: RunId
    state: RunState
    started_at: datetime

    def transition(self, target: RunState) -> 'MigrationRun':
        if not can_transition(self.state, target):
            raise IntegrityError(
                code='run.invalid-transition',
                message=f'Cannot move from {self.state.value} to {target.value}.',
                guidance='Follow the migration plan state order.',
                context=ErrorContext(run_id=str(self.id)),
            )
        return replace(self, state=target)


@dataclass(frozen=True, slots=True)
class RunMetrics:
    selected: int = 0
    transformed: int = 0
    staged: int = 0
    rejected: int = 0
    validated: int = 0
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        if any(value < 0 for value in (
            self.selected,
            self.transformed,
            self.staged,
            self.rejected,
            self.validated,
            self.duration_seconds,
        )):
            raise ValueError('run metrics must be nonnegative')


@dataclass(frozen=True, slots=True)
class RunSummary:
    run: MigrationRun
    acceptance: AcceptanceStatus
    findings: FindingCollection
    artifacts: tuple[Artifact, ...]
    metrics: RunMetrics
~~~

- [ ] **Step 4: Run execution model tests**

    python -m pytest tests/unit/domain/test_runs.py -q

Expected: dependency order, cycle detection, transitions, and counter invariants
pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/runs.py tests/unit/domain/test_runs.py
    git commit -m "feat: define migration plans and run summaries"

---

### Task 10: Canonical Serialization and Fingerprints

**Files:**

- Create: src/un_migration/domain/serialization.py
- Create: tests/unit/domain/test_serialization.py

**Interfaces:**

- Consumes: dataclasses, enums, dates, datetimes, decimals, paths, mappings, and
  sequences from earlier tasks.
- Produces: to_primitive(value) -> JSONValue,
  canonical_json(value) -> str, and fingerprint(value) -> Checksum.

- [ ] **Step 1: Write failing deterministic serialization tests**

~~~python
from datetime import datetime, timezone
from decimal import Decimal

from un_migration.domain.serialization import canonical_json, fingerprint


def test_canonical_json_is_ordered_and_normalized() -> None:
    value = {
        'when': datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
        'amount': Decimal('12.500'),
        'tags': {'b', 'a'},
    }

    assert canonical_json(value) == (
        '{"amount":"12.500","tags":["a","b"],'
        '"when":"2026-07-16T12:00:00Z"}'
    )
    assert fingerprint(value) == fingerprint(dict(reversed(value.items())))
~~~

- [ ] **Step 2: Run and verify missing module failure**

    python -m pytest tests/unit/domain/test_serialization.py -q

Expected: collection fails because serialization.py does not exist.

- [ ] **Step 3: Implement recursive primitive conversion**

Implement recursive conversion, canonical JSON, and fingerprints:

~~~python
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import TypeAlias

from un_migration.domain.artifacts import Checksum

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list['JSONValue'] | dict[str, 'JSONValue']


def to_primitive(value: object) -> JSONValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Enum):
        return to_primitive(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError('datetime must be timezone-aware')
        utc = value.astimezone(timezone.utc).isoformat(timespec='seconds')
        return utc.replace('+00:00', 'Z')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return value.as_posix()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_primitive(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): to_primitive(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, set | frozenset):
        converted = [to_primitive(item) for item in value]
        return sorted(converted, key=canonical_json)
    if isinstance(value, tuple | list):
        return [to_primitive(item) for item in value]
    raise TypeError(f'Unsupported canonical value: {type(value).__name__}')


def canonical_json(value: object) -> str:
    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(',', ':'),
    )


def fingerprint(value: object) -> Checksum:
    return Checksum.sha256(canonical_json(value).encode('utf-8'))
~~~

- [ ] **Step 4: Run unit and property tests**

    python -m pytest tests/unit/domain/test_serialization.py -q

Expected: normalization, stable ordering, round-trip-safe primitives, and
unsupported-type tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/domain/serialization.py tests/unit/domain/test_serialization.py
    git commit -m "feat: add canonical serialization fingerprints"

---

### Task 11: Adapter Port Protocols

**Files:**

- Create: src/un_migration/ports/__init__.py
- Create: src/un_migration/ports/source.py
- Create: src/un_migration/ports/staging.py
- Create: src/un_migration/ports/services.py
- Create: tests/contract/test_port_shapes.py

**Interfaces:**

- Consumes: domain types from Tasks 3 through 10.
- Produces: AdapterCapabilities, Record, RecordBatch, SourceReader,
  StagingWriter, ArtifactStore, CheckpointStore, DeploymentTarget, Notifier,
  Notification, and DeliveryReceipt protocols.

- [ ] **Step 1: Write failing runtime protocol tests**

~~~python
from un_migration.ports.source import SourceReader


class IncompleteSource:
    pass


def test_source_protocol_rejects_incomplete_adapter() -> None:
    assert not isinstance(IncompleteSource(), SourceReader)
~~~

Also define a CompleteSource test double implementing capabilities, inventory,
count, and read_batches and assert isinstance returns true.

- [ ] **Step 2: Run and verify missing ports failure**

    python -m pytest tests/contract/test_port_shapes.py -q

Expected: collection fails because the ports package does not exist.

- [ ] **Step 3: Implement focused runtime-checkable protocols**

~~~python
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from un_migration.domain.schema import DatasetInventory, DatasetRef

Record = Mapping[str, object]
RecordBatch = tuple[Record, ...]


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    adapter_name: str
    operations: frozenset[str]

    def supports(self, operation: str) -> bool:
        return operation in self.operations


@runtime_checkable
class SourceReader(Protocol):
    def capabilities(self) -> AdapterCapabilities: ...
    def inventory(self, dataset: DatasetRef) -> DatasetInventory: ...
    def count(self, dataset: DatasetRef, filter_expression: object | None) -> int: ...
    def read_batches(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
        batch_size: int,
    ) -> Iterator[RecordBatch]: ...
~~~

Define StagingWriter in staging.py:

~~~python
from typing import Protocol, runtime_checkable

from un_migration.domain.artifacts import Artifact
from un_migration.domain.identity import DatasetId, RunId
from un_migration.ports.source import AdapterCapabilities, RecordBatch


@runtime_checkable
class StagingWriter(Protocol):
    def capabilities(self) -> AdapterCapabilities: ...
    def initialize(self, run_id: RunId) -> None: ...
    def write_batch(self, dataset_id: DatasetId, records: RecordBatch) -> int: ...
    def finalize(self) -> tuple[Artifact, ...]: ...
    def abort(self, reason: str) -> None: ...
~~~

Define immutable requests, responses, and service protocols in services.py:

~~~python
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from un_migration.domain.artifacts import Artifact
from un_migration.domain.identity import RunId, StepId
from un_migration.domain.runs import Checkpoint, RunSummary
from un_migration.ports.source import AdapterCapabilities


@dataclass(frozen=True, slots=True)
class Notification:
    subject: str
    message: str
    artifact_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    provider: str
    message_id: str
    accepted: bool


@runtime_checkable
class ArtifactStore(Protocol):
    def write(self, path: str, payload: bytes, media_type: str) -> Artifact: ...
    def read(self, path: str) -> bytes: ...
    def list(self) -> tuple[Artifact, ...]: ...
    def verify(self, artifact: Artifact) -> bool: ...


@runtime_checkable
class CheckpointStore(Protocol):
    def save(self, checkpoint: Checkpoint) -> None: ...
    def load(self, run_id: RunId, step_id: StepId) -> Checkpoint | None: ...


@runtime_checkable
class DeploymentTarget(Protocol):
    def capabilities(self) -> AdapterCapabilities: ...
    def preflight(self, summary: RunSummary) -> tuple[str, ...]: ...
    def deploy(self, summary: RunSummary) -> tuple[Artifact, ...]: ...


@runtime_checkable
class Notifier(Protocol):
    def deliver(self, notification: Notification) -> DeliveryReceipt: ...
~~~

- [ ] **Step 4: Run contract and type checks**

    python -m pytest tests/contract/test_port_shapes.py -q
    python -m mypy src/un_migration/ports

Expected: protocol shape tests and mypy pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/ports tests/contract/test_port_shapes.py
    git commit -m "feat: define migration adapter protocols"

---

### Task 12: Public API and Diagnostic CLI Slice

**Files:**

- Create: src/un_migration/api.py
- Create: src/un_migration/cli.py
- Modify: src/un_migration/__init__.py
- Create: tests/cli/test_version.py
- Create: tests/cli/test_doctor.py

**Interfaces:**

- Consumes: package version and SystemClock.
- Produces: PackageInfo, package_info() -> PackageInfo, Typer app,
  un-migrate version, and un-migrate doctor.

- [ ] **Step 1: Write failing CLI tests**

~~~python
import json

from typer.testing import CliRunner

from un_migration.cli import app

runner = CliRunner()


def test_version_json_is_machine_readable() -> None:
    result = runner.invoke(app, ['version', '--json'])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['name'] == 'geospatial-network-migration-toolkit'
    assert payload['version'] == '0.1.0'


def test_doctor_reports_arcpy_as_optional() -> None:
    result = runner.invoke(app, ['doctor', '--json'])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['python']['supported'] is True
    assert payload['arcpy']['required'] is False
~~~

- [ ] **Step 2: Run and verify missing CLI failure**

    python -m pytest tests/cli/test_version.py tests/cli/test_doctor.py -q

Expected: collection fails because cli.py does not exist.

- [ ] **Step 3: Implement package information and diagnostics**

Implement api.py:

~~~python
import platform
from dataclasses import dataclass

from un_migration._version import __version__


@dataclass(frozen=True, slots=True)
class PackageInfo:
    name: str
    version: str
    python: str
    platform: str

    def to_dict(self) -> dict[str, str]:
        return {
            'name': self.name,
            'version': self.version,
            'python': self.python,
            'platform': self.platform,
        }


def package_info() -> PackageInfo:
    return PackageInfo(
        name='geospatial-network-migration-toolkit',
        version=__version__,
        python=platform.python_version(),
        platform=platform.platform(),
    )
~~~

Implement cli.py with one shared JSON writer and local diagnostics:

~~~python
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from typing import Annotated

import typer

from un_migration.api import package_info

app = typer.Typer(
    no_args_is_help=True,
    help='Plan, run, validate, and document geospatial network migrations.',
)


def _write(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, sort_keys=True))
        return
    for key, value in payload.items():
        typer.echo(f'{key}: {value}')


@app.command()
def version(
    as_json: Annotated[
        bool,
        typer.Option('--json', help='Emit machine-readable JSON.'),
    ] = False,
) -> None:
    _write(package_info().to_dict(), as_json)


@app.command()
def doctor(
    as_json: Annotated[
        bool,
        typer.Option('--json', help='Emit machine-readable JSON.'),
    ] = False,
) -> None:
    python_supported = sys.version_info >= (3, 11)
    arcpy_available = importlib.util.find_spec('arcpy') is not None
    writable = os.access(Path.cwd(), os.W_OK)
    payload: dict[str, object] = {
        'python': {
            'version': platform.python_version(),
            'supported': python_supported,
        },
        'working_directory': {'writable': writable},
        'arcpy': {'available': arcpy_available, 'required': False},
    }
    _write(payload, as_json)
    if not python_supported or not writable:
        raise typer.Exit(code=1)
~~~

Add PackageInfo and package_info to the deliberate exports in __init__.py.

- [ ] **Step 4: Run the whole foundation quality gate**

    python -m ruff format --check .
    python -m ruff check .
    python -m mypy src/un_migration
    python -m pytest -q
    un-migrate version --json
    un-migrate doctor --json
    python -m build
    python -m twine check dist/*

Expected: all checks pass; version and doctor emit valid JSON; both package
artifacts pass Twine validation.

- [ ] **Step 5: Commit**

    git add src/un_migration tests/cli
    git commit -m "feat: expose package diagnostics CLI"

---

## Plan Completion Evidence

This subproject is complete only when:

- the editable package installs in a clean virtual environment
- the full test suite passes
- Ruff format and lint checks pass
- strict mypy passes
- wheel and source distribution build and pass Twine
- un-migrate version and doctor work in human and JSON modes
- git history contains one coherent commit for each of the 12 tasks
- the worktree is clean

The next subplan will cover typed configuration, environment interpolation,
JSON Schema generation, in-memory adapters, dataset inventory, and schema
fingerprinting.
