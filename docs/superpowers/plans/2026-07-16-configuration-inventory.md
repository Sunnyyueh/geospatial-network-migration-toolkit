# Configuration and Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox '- [ ]' syntax for tracking.

**Goal:** Add typed project configuration, secure environment interpolation,
portable source adapters, deterministic schema inventory, and config/inventory
CLI commands that work against real CSV files and in-memory records.

**Architecture:** Pydantic models validate only application-boundary data.
Loading, interpolation, merge, rendering, adapters, and inventory services remain
separate focused modules. Application services depend on SourceReader rather than
concrete adapters, and all serialized output uses canonical domain primitives.

**Tech Stack:** Python 3.11+, Pydantic 2, PyYAML, Typer, standard-library CSV and
JSON, pytest, Hypothesis, Ruff, and strict mypy.

## Global Constraints

- Core configuration and inventory modules never import ArcPy.
- Configuration version is exactly 1 for the 1.0 release line.
- Unknown configuration keys fail validation.
- Environment values are interpolated before Pydantic validation.
- Rendered configuration and errors never reveal configured secret values.
- Source reads are bounded by a positive batch size.
- Inventory output is deterministic and fingerprintable.
- Each task follows test-first red-green-refactor and ends in one commit.

---

## File Responsibility Map

| Path | Responsibility |
| --- | --- |
| src/un_migration/config/models.py | Strict typed project configuration. |
| src/un_migration/config/environment.py | Environment interpolation and redaction. |
| src/un_migration/config/loader.py | YAML/JSON parsing and error translation. |
| src/un_migration/config/merge.py | Deep profile merge and dotted overrides. |
| src/un_migration/config/render.py | JSON Schema and redacted canonical output. |
| src/un_migration/config/__init__.py | Stable configuration exports. |
| src/un_migration/adapters/memory/source.py | Deterministic in-memory SourceReader. |
| src/un_migration/adapters/filesystem/csv_source.py | Streaming CSV SourceReader. |
| src/un_migration/inventory/service.py | Inventory orchestration and comparison. |
| src/un_migration/cli.py | Config and inventory command groups. |
| tests/unit/config | Configuration behavior tests. |
| tests/contract | Reusable source adapter contract tests. |
| tests/integration | Real temporary-file inventory tests. |
| tests/cli | Config and inventory command tests. |

---

### Task 1: Strict Typed Configuration Models

**Files:**

- Create: src/un_migration/config/__init__.py
- Create: src/un_migration/config/models.py
- Create: tests/unit/config/test_models.py

**Interfaces:**

- Consumes: Pydantic 2.
- Produces: AdapterConfig, DatasetConfig, SourceConfig, TargetConfig,
  ReportingConfig, RuntimeConfig, and ProjectConfig.

- [ ] **Step 1: Write failing strict-model tests**

~~~python
from pydantic import ValidationError

from un_migration.config.models import ProjectConfig


def test_project_config_validates_portable_minimum() -> None:
    config = ProjectConfig.model_validate({
        'config_version': 1,
        'project_name': 'Synthetic water migration',
        'source': {
            'adapter': {'kind': 'csv', 'options': {}},
            'workspace': 'examples/data',
            'datasets': [{'id': 'water-mains', 'path': 'water_mains.csv'}],
        },
        'target': {
            'adapter': {'kind': 'filesystem', 'options': {}},
            'workspace': 'outputs/staging',
        },
    })
    assert config.runtime.batch_size == 1000
    assert config.source.datasets[0].id == 'water-mains'


def test_unknown_key_is_rejected() -> None:
    value = {
        'config_version': 1,
        'project_name': 'Synthetic water migration',
        'source': {
            'adapter': {'kind': 'csv', 'options': {}},
            'workspace': 'examples/data',
            'datasets': [{'id': 'water-mains', 'path': 'water_mains.csv'}],
        },
        'target': {
            'adapter': {'kind': 'filesystem', 'options': {}},
            'workspace': 'outputs/staging',
        },
        'mystery': True,
    }
    with pytest.raises(ValidationError, match='extra_forbidden'):
        ProjectConfig.model_validate(value)
~~~

Also test config_version other than 1, blank project names, duplicate dataset
IDs, nonpositive batch sizes, absolute dataset paths, and missing datasets.

- [ ] **Step 2: Run test and confirm missing config package**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_models.py -q

Expected: collection fails because un_migration.config does not exist.

- [ ] **Step 3: Implement frozen strict boundary models**

Use one base model:

~~~python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
~~~

Define exact fields:

~~~python
class AdapterConfig(StrictModel):
    kind: str = Field(min_length=1, pattern=r'^[a-z][a-z0-9_-]*$')
    options: dict[str, JsonValue] = Field(default_factory=dict)


class DatasetConfig(StrictModel):
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9.-]{0,127}$')
    path: Path
    geometry_field: str | None = None

    @field_validator('path')
    @classmethod
    def require_relative_path(cls, value: Path) -> Path:
        if value.is_absolute() or '..' in value.parts:
            raise ValueError('dataset path must be managed and relative')
        return value


class SourceConfig(StrictModel):
    adapter: AdapterConfig
    workspace: Path
    datasets: tuple[DatasetConfig, ...]

    @model_validator(mode='after')
    def unique_dataset_ids(self) -> 'SourceConfig':
        ids = [dataset.id for dataset in self.datasets]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError('source datasets must be nonempty and unique')
        return self


class TargetConfig(StrictModel):
    adapter: AdapterConfig
    workspace: Path


class ReportingConfig(StrictModel):
    output_directory: Path = Path('outputs')
    formats: tuple[Literal['json', 'csv', 'markdown', 'html'], ...] = ('json',)


class RuntimeConfig(StrictModel):
    batch_size: int = Field(default=1000, ge=1, le=100_000)


class ProjectConfig(StrictModel):
    config_version: Literal[1]
    project_name: str = Field(min_length=1)
    source: SourceConfig
    target: TargetConfig
    reporting: ReportingConfig = ReportingConfig()
    runtime: RuntimeConfig = RuntimeConfig()
~~~

- [ ] **Step 4: Run tests and type checks**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_models.py -q
    .venv/bin/python -m mypy src/un_migration/config/models.py

Expected: strict validation and mypy pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/config tests/unit/config/test_models.py
    git commit -m "feat: define strict project configuration"

---

### Task 2: Environment Interpolation and Redaction

**Files:**

- Create: src/un_migration/config/environment.py
- Create: tests/unit/config/test_environment.py

**Interfaces:**

- Consumes: nested JSON-compatible mappings and an environment mapping.
- Produces: interpolate_environment(value, environ) -> object,
  redact_secrets(value, secret_keys) -> object, and SecretRegistry.

- [ ] **Step 1: Write failing interpolation tests**

~~~python
def test_interpolation_supports_required_and_default_values() -> None:
    value = {'workspace': '${SOURCE_PATH}', 'profile': '${PROFILE:-water}'}
    assert interpolate_environment(value, {'SOURCE_PATH': '/data'}) == {
        'workspace': '/data',
        'profile': 'water',
    }


def test_missing_required_variable_raises_safe_error() -> None:
    with pytest.raises(ConfigurationError, match='environment.missing'):
        interpolate_environment('${TOKEN}', {})


def test_redaction_replaces_nested_secret_values() -> None:
    value = {'auth': {'token': 'secret'}, 'project': 'public'}
    assert redact_secrets(value, frozenset({'token'})) == {
        'auth': {'token': '***REDACTED***'},
        'project': 'public',
    }
~~~

- [ ] **Step 2: Run and confirm missing module failure**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_environment.py -q

Expected: import fails for config.environment.

- [ ] **Step 3: Implement recursive interpolation and redaction**

Use a full-match expression for strings containing only one variable:

~~~python
_VARIABLE = re.compile(
    r'^\$\{(?P<name>[A-Z_][A-Z0-9_]*)(?::-(?P<default>[^}]*))?\}$'
)


def _resolve(text: str, environ: Mapping[str, str]) -> str:
    match = _VARIABLE.fullmatch(text)
    if match is None:
        return text
    name = match.group('name')
    if name in environ:
        return environ[name]
    default = match.group('default')
    if default is not None:
        return default
    raise ConfigurationError(
        code='environment.missing',
        message=f'Required environment variable {name} is not set.',
        guidance=f'Set {name} before loading this project.',
    )
~~~

Recursively preserve mapping keys and tuple/list shape. SecretRegistry stores a
frozenset of case-folded keys and has is_secret(key: str) -> bool. Redaction
replaces values for matching keys and never includes the original value in an
exception.

- [ ] **Step 4: Run focused tests**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_environment.py -q

Expected: interpolation, default, nested container, missing-variable, and
redaction tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/config/environment.py tests/unit/config/test_environment.py
    git commit -m "feat: add secure environment interpolation"

---

### Task 3: YAML and JSON Configuration Loader

**Files:**

- Create: src/un_migration/config/loader.py
- Create: tests/unit/config/test_loader.py

**Interfaces:**

- Consumes: ProjectConfig and interpolate_environment.
- Produces: load_raw_config(path, environ) -> dict[str, object] and
  load_config(path, environ=None) -> ProjectConfig.

- [ ] **Step 1: Write failing temporary-file tests**

Write a YAML file and an equivalent JSON file in tmp_path, load both, and assert
they create equal ProjectConfig values. Add tests for missing file, unsupported
extension, malformed YAML, non-mapping root, and Pydantic validation errors.
Assert all failures are ConfigurationError with stable codes:
config.not-found, config.unsupported-format, config.parse, config.root, and
config.invalid.

- [ ] **Step 2: Run and confirm missing loader**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_loader.py -q

Expected: import fails for config.loader.

- [ ] **Step 3: Implement format dispatch and error translation**

~~~python
def load_raw_config(
    path: Path,
    environ: Mapping[str, str],
) -> dict[str, object]:
    if not path.is_file():
        raise ConfigurationError(
            code='config.not-found',
            message=f'Configuration file does not exist: {path}',
            guidance='Provide an existing YAML or JSON project file.',
        )
    try:
        if path.suffix.casefold() in {'.yaml', '.yml'}:
            parsed = yaml.safe_load(path.read_text(encoding='utf-8'))
        elif path.suffix.casefold() == '.json':
            parsed = json.loads(path.read_text(encoding='utf-8'))
        else:
            raise ConfigurationError(
                code='config.unsupported-format',
                message=f'Unsupported configuration format: {path.suffix}',
                guidance='Use a .yaml, .yml, or .json project file.',
            )
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(
            code='config.parse',
            message='Project configuration could not be parsed.',
            guidance='Correct the YAML or JSON syntax and retry.',
        ) from error
    if not isinstance(parsed, dict):
        raise ConfigurationError(
            code='config.root',
            message='Project configuration root must be a mapping.',
            guidance='Place project fields under a YAML or JSON object.',
        )
    return cast(dict[str, object], interpolate_environment(parsed, environ))


def load_config(
    path: str | Path,
    environ: Mapping[str, str] | None = None,
) -> ProjectConfig:
    try:
        return ProjectConfig.model_validate(
            load_raw_config(Path(path), environ or os.environ)
        )
    except ValidationError as error:
        raise ConfigurationError(
            code='config.invalid',
            message='Project configuration failed validation.',
            guidance='Run un-migrate config validate for field details.',
        ) from error
~~~

- [ ] **Step 4: Run tests and full config checks**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config -q
    .venv/bin/python -m mypy src/un_migration/config

Expected: all configuration tests and strict mypy pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/config tests/unit/config/test_loader.py
    git commit -m "feat: load YAML and JSON project configs"

---

### Task 4: Profile Merge and Dotted Overrides

**Files:**

- Create: src/un_migration/config/merge.py
- Create: tests/unit/config/test_merge.py

**Interfaces:**

- Consumes: nested mapping data.
- Produces: deep_merge(base, overlay) -> dict[str, object],
  parse_override(text) -> tuple[tuple[str, ...], object], and
  apply_overrides(config, overrides) -> dict[str, object].

- [ ] **Step 1: Write failing deterministic merge tests**

Verify nested mappings merge recursively, scalar/list values replace, inputs are
not mutated, runtime.batch_size=250 parses as an integer, deployment.enabled=true
parses as a boolean, and unknown/empty dotted segments raise ConfigurationError
with code config.override.

- [ ] **Step 2: Run and confirm missing merge module**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_merge.py -q

Expected: import fails for config.merge.

- [ ] **Step 3: Implement copy-safe merge and override parsing**

~~~python
def deep_merge(
    base: Mapping[str, object],
    overlay: Mapping[str, object],
) -> dict[str, object]:
    result = deepcopy(dict(base))
    for key, value in overlay.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(current, value)
        else:
            result[key] = deepcopy(value)
    return result


def parse_override(text: str) -> tuple[tuple[str, ...], object]:
    key, separator, raw_value = text.partition('=')
    path = tuple(key.split('.'))
    if not separator or any(not segment for segment in path):
        raise ConfigurationError(
            code='config.override',
            message=f'Invalid configuration override: {text}',
            guidance='Use dotted.path=value syntax.',
        )
    return path, yaml.safe_load(raw_value)
~~~

apply_overrides deep-copies input, rejects paths that do not already exist, and
sets only the leaf value.

- [ ] **Step 4: Run focused tests**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_merge.py -q

Expected: all merge, immutability, parsing, and path validation tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/config/merge.py tests/unit/config/test_merge.py
    git commit -m "feat: support config profiles and overrides"

---

### Task 5: JSON Schema and Redacted Rendering

**Files:**

- Create: src/un_migration/config/render.py
- Create: schemas/project-config.schema.json
- Create: tests/unit/config/test_render.py

**Interfaces:**

- Consumes: ProjectConfig, canonical JSON, and secret redaction.
- Produces: project_config_schema() -> dict[str, object],
  render_config(config, secret_keys) -> str, and a checked-in schema artifact.

- [ ] **Step 1: Write failing schema and redaction tests**

Assert generated schema forbids additional properties, requires config_version,
contains the constant 1, and matches the checked-in JSON file byte-for-byte
after canonical formatting. Assert render_config omits secret option values
when keys token, password, api_key, and client_secret are supplied.

- [ ] **Step 2: Run and confirm missing renderer**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config/test_render.py -q

Expected: import fails for config.render.

- [ ] **Step 3: Implement generated schema and canonical rendering**

~~~python
DEFAULT_SECRET_KEYS = frozenset(
    {'token', 'password', 'api_key', 'client_secret'}
)


def project_config_schema() -> dict[str, object]:
    return cast(dict[str, object], ProjectConfig.model_json_schema())


def render_config(
    config: ProjectConfig,
    secret_keys: frozenset[str] = DEFAULT_SECRET_KEYS,
) -> str:
    safe = redact_secrets(
        config.model_dump(mode='json'),
        secret_keys,
    )
    return canonical_json(safe)
~~~

Generate schemas/project-config.schema.json through the implementation and commit
the deterministic artifact.

- [ ] **Step 4: Run config tests**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/config -q
    .venv/bin/python -m mypy src/un_migration/config

Expected: config suite and strict mypy pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/config schemas tests/unit/config/test_render.py
    git commit -m "feat: publish project config JSON schema"

---

### Task 6: Config CLI Commands

**Files:**

- Modify: src/un_migration/cli.py
- Create: tests/cli/test_config.py

**Interfaces:**

- Consumes: load_config, project_config_schema, and render_config.
- Produces: un-migrate config validate, config render, and config schema.

- [ ] **Step 1: Write failing CLI tests**

Use CliRunner isolated_filesystem to create a valid YAML project. Verify:

- config validate exits 0 and JSON contains valid=true and project_name
- invalid config exits 2 with code config.invalid and no traceback
- config render emits canonical redacted JSON
- config schema writes JSON to stdout and includes ProjectConfig title

- [ ] **Step 2: Run and confirm missing config command**

    PYTHONPATH=src .venv/bin/python -m pytest tests/cli/test_config.py -q

Expected: config command is not recognized.

- [ ] **Step 3: Implement nested Typer command group**

~~~python
config_app = typer.Typer(help='Validate and inspect project configuration.')
app.add_typer(config_app, name='config')


@config_app.command('validate')
def config_validate(path: Path, as_json: JsonOption = False) -> None:
    try:
        config = load_config(path)
    except ConfigurationError as error:
        _write({'valid': False, 'error': error.to_dict()}, as_json)
        raise typer.Exit(code=2) from None
    _write({'valid': True, 'project_name': config.project_name}, as_json)
~~~

render and schema follow the same deterministic output path. Human errors contain
code, message, and guidance but no stack trace.

- [ ] **Step 4: Run CLI and full checks**

    PYTHONPATH=src .venv/bin/python -m pytest tests/cli/test_config.py -q
    PYTHONPATH=src .venv/bin/python -m pytest -q

Expected: all CLI and existing tests pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/cli.py tests/cli/test_config.py
    git commit -m "feat: add project configuration CLI"

---

### Task 7: In-Memory Source Adapter

**Files:**

- Create: src/un_migration/adapters/__init__.py
- Create: src/un_migration/adapters/memory/__init__.py
- Create: src/un_migration/adapters/memory/source.py
- Create: tests/contract/source_contract.py
- Create: tests/contract/test_memory_source.py

**Interfaces:**

- Consumes: SourceReader, DatasetInventory, DatasetRef, and record mappings.
- Produces: MemoryDataset and MemorySourceReader.

- [ ] **Step 1: Write reusable contract and failing adapter tests**

The contract factory returns one reader and DatasetRef. Assert capabilities,
inventory, count, bounded batches, empty dataset behavior, unknown dataset
InventoryError, nonpositive batch-size ConfigurationError, and defensive copying
of input records.

- [ ] **Step 2: Run and confirm missing adapter**

    PYTHONPATH=src .venv/bin/python -m pytest tests/contract/test_memory_source.py -q

Expected: import fails for adapters.memory.source.

- [ ] **Step 3: Implement immutable memory dataset and reader**

~~~python
@dataclass(frozen=True, slots=True)
class MemoryDataset:
    inventory: DatasetInventory
    records: tuple[Mapping[str, object], ...]


class MemorySourceReader:
    def __init__(self, datasets: Mapping[DatasetId, MemoryDataset]) -> None:
        self._datasets = {
            key: MemoryDataset(
                value.inventory,
                tuple(MappingProxyType(dict(record)) for record in value.records),
            )
            for key, value in datasets.items()
        }

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities('memory', frozenset({'inventory', 'count', 'read'}))

    def inventory(self, dataset: DatasetRef) -> DatasetInventory:
        return self._get(dataset.id).inventory

    def count(self, dataset: DatasetRef, filter_expression: object | None) -> int:
        self._require_no_filter(filter_expression)
        return len(self._get(dataset.id).records)

    def read_batches(
        self,
        dataset: DatasetRef,
        filter_expression: object | None,
        batch_size: int,
    ) -> Iterator[RecordBatch]:
        self._require_no_filter(filter_expression)
        if batch_size <= 0:
            raise ConfigurationError(
                code='runtime.batch-size',
                message='Batch size must be positive.',
                guidance='Set runtime.batch_size to a value of at least 1.',
            )
        records = self._get(dataset.id).records
        for offset in range(0, len(records), batch_size):
            yield records[offset:offset + batch_size]
~~~

Filters are rejected until the filter AST subplan adds the shared expression
protocol.

- [ ] **Step 4: Run contract, unit, and type checks**

    PYTHONPATH=src .venv/bin/python -m pytest tests/contract/test_memory_source.py -q
    .venv/bin/python -m mypy src/un_migration/adapters/memory

Expected: reusable source contract and strict mypy pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/adapters tests/contract
    git commit -m "feat: add in-memory source adapter"

---

### Task 8: Streaming CSV Source Adapter

**Files:**

- Create: src/un_migration/adapters/filesystem/__init__.py
- Create: src/un_migration/adapters/filesystem/csv_source.py
- Create: tests/integration/test_csv_source.py

**Interfaces:**

- Consumes: SourceReader, SourceConfig, DatasetRef, and portable schema models.
- Produces: CsvSourceReader with bounded reads and deterministic type inference.

- [ ] **Step 1: Write failing real-file integration tests**

Create a temporary CSV containing asset_id, diameter, active, and installed_on.
Assert inventory field order and inferred string/integer/boolean/date types,
feature_count excluding header, count, two-record batches, empty CSV behavior,
UTF-8 BOM handling, duplicate headers, inconsistent row width, missing file, and
unsupported filters.

- [ ] **Step 2: Run and confirm missing CSV adapter**

    PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_csv_source.py -q

Expected: import fails for adapters.filesystem.csv_source.

- [ ] **Step 3: Implement safe workspace resolution and streaming**

CsvSourceReader receives workspace: Path and tuple[DatasetConfig, ...]. Resolve
each path, require resolved path to remain under workspace, and cache only
inventory metadata, never full records.

Infer a column using all nonblank values with precedence:
boolean, integer, float, ISO date, ISO datetime, string. Mixed types fall back to
string. Blank values set nullable true. csv.DictReader reads with utf-8-sig and
newline=''. Convert values according to inventory type when yielding batches.
Raise InventoryError with stable codes csv.not-found, csv.header, csv.row-width,
and csv.read.

- [ ] **Step 4: Run integration and type checks**

    PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_csv_source.py -q
    .venv/bin/python -m mypy src/un_migration/adapters/filesystem

Expected: real-file CSV tests and strict mypy pass.

- [ ] **Step 5: Commit**

    git add src/un_migration/adapters/filesystem tests/integration/test_csv_source.py
    git commit -m "feat: inventory and stream CSV sources"

---

### Task 9: Inventory Service and CLI

**Files:**

- Create: src/un_migration/inventory/__init__.py
- Create: src/un_migration/inventory/service.py
- Create: tests/unit/inventory/test_service.py
- Create: tests/cli/test_inventory.py
- Modify: src/un_migration/cli.py

**Interfaces:**

- Consumes: ProjectConfig, SourceReader, DatasetInventory, and fingerprint.
- Produces: InventoryResult, InventoryComparison,
  InventoryService.collect(), compare_inventories(), and
  un-migrate inventory source.

- [ ] **Step 1: Write failing service and CLI tests**

Assert collect preserves configured dataset order, includes one checksum per
inventory, and reports adapter capabilities. Compare identical inventories as
unchanged; detect added/removed/changed fields and feature-count deltas.
The CLI reads a real CSV project and emits JSON with dataset ID, physical name,
feature count, field metadata, geometry, and fingerprint.

- [ ] **Step 2: Run and confirm missing inventory service**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/inventory/test_service.py tests/cli/test_inventory.py -q

Expected: imports or command fail because inventory service is absent.

- [ ] **Step 3: Implement orchestration and deterministic comparison**

~~~python
@dataclass(frozen=True, slots=True)
class InventoryResult:
    adapter: AdapterCapabilities
    inventories: tuple[DatasetInventory, ...]
    fingerprints: Mapping[DatasetId, Checksum]


class InventoryService:
    def __init__(self, source: SourceReader) -> None:
        self._source = source

    def collect(self, datasets: tuple[DatasetRef, ...]) -> InventoryResult:
        inventories = tuple(self._source.inventory(item) for item in datasets)
        return InventoryResult(
            adapter=self._source.capabilities(),
            inventories=inventories,
            fingerprints=MappingProxyType({
                item.dataset.id: fingerprint(item) for item in inventories
            }),
        )
~~~

InventoryComparison contains added_fields, removed_fields, changed_fields, and
feature_count_delta. CLI adapter selection supports csv in this subplan and
returns capability exit code 4 for unsupported adapter kinds.

- [ ] **Step 4: Run complete subplan quality gate**

    .venv/bin/python -m ruff format --check .
    .venv/bin/python -m ruff check .
    .venv/bin/python -m mypy src/un_migration
    PYTHONPATH=src .venv/bin/python -m pytest -q
    PYTHONPATH=src .venv/bin/un-migrate config schema --json
    .venv/bin/python -m build
    .venv/bin/python -m twine check dist/*

Expected: all checks pass, commands emit valid JSON, and distributions pass
Twine.

- [ ] **Step 5: Commit**

    git add src/un_migration/inventory src/un_migration/cli.py tests
    git commit -m "feat: expose deterministic source inventory"

---

## Plan Completion Evidence

This subproject is complete only when:

- YAML and JSON projects produce equal typed ProjectConfig values
- secrets are redacted from rendered configuration and safe errors
- checked-in JSON Schema matches generated output
- config validate, render, and schema commands work in JSON and human modes
- memory and CSV readers satisfy the source adapter contract
- CSV inventory and reads operate on real temporary files in bounded batches
- inventory fingerprints are deterministic
- source inventory CLI emits complete machine-readable metadata
- Ruff, strict mypy, all tests, build, and Twine pass
- every task has one coherent commit and the worktree is clean

The next subplan covers reference-table mapping, the safe filter AST and
compilers, and the transformation registry.
