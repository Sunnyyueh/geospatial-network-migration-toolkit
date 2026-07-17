# Reference Mapping, Filter, and Transformation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox '- [ ]' syntax for tracking.

**Goal:** Parse and validate versioned source-to-target mappings, safely parse
filter expressions into a typed AST, compile filters for portable and ArcPy
backends, and apply a registry of deterministic record transformations.

**Architecture:** Mapping, filtering, and transformation remain independent
packages joined by application services. Filter text is never evaluated as
Python; all backends consume one immutable AST. Transformations are registered
callables selected by validated names, not arbitrary code from configuration.

**Tech Stack:** Python 3.11+, standard-library CSV, Decimal, datetime, regex,
pytest, Hypothesis, Ruff, and strict mypy.

## Global Constraints

- Filter input is parsed, never passed to eval or exec.
- SQL output uses placeholders and separately returned parameters.
- ArcPy output escapes literals and requires a backend field delimiter function.
- Reference tables have an explicit schema_version column fixed at 1.
- Mapping validation runs before any source records are read.
- Transformations never mutate input records.
- Every error has a stable code, safe message, and remediation guidance.
- Every task uses a failing test first and ends with one coherent commit.

---

### Task 1: Mapping Domain Models

**Files:**

- Create: src/un_migration/mapping/__init__.py
- Create: src/un_migration/mapping/models.py
- Create: tests/unit/mapping/test_models.py

**Interfaces:**

- Produces: NullPolicy, TransformSpec, FieldMapping, DatasetMapping, and
  ReferenceTable.

- [ ] **Step 1: Write failing immutable-model tests**

Test normalized field names, schema_version=1, unique target fields, unique
dataset mappings, required-target/null-policy conflicts, frozen transform
parameters, and rejection of blank identifiers.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/mapping/test_models.py -q

Expected: import fails because mapping package does not exist.

- [ ] **Step 3: Implement exact values**

~~~python
class NullPolicy(StrEnum):
    ALLOW = 'allow'
    REJECT = 'reject'
    DEFAULT = 'default'


@dataclass(frozen=True, slots=True)
class TransformSpec:
    name: str = 'identity'
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError('invalid transformation name')
        object.__setattr__(
            self,
            'parameters',
            MappingProxyType(dict(self.parameters)),
        )


@dataclass(frozen=True, slots=True)
class FieldMapping:
    source_field: str
    target_field: str
    target_type: FieldType
    required: bool = False
    null_policy: NullPolicy = NullPolicy.ALLOW
    default: object | None = None
    transform: TransformSpec = TransformSpec()


@dataclass(frozen=True, slots=True)
class DatasetMapping:
    source_dataset: DatasetId
    target_dataset: DatasetId
    fields: tuple[FieldMapping, ...]


@dataclass(frozen=True, slots=True)
class ReferenceTable:
    schema_version: Literal[1]
    datasets: tuple[DatasetMapping, ...]
~~~

Validate names with a shared field-name expression and reject duplicate
case-folded target fields and source dataset IDs.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/mapping/test_models.py -q
    .venv/bin/python -m mypy src/un_migration/mapping/models.py

- [ ] **Step 5: Commit**

    git add src/un_migration/mapping tests/unit/mapping/test_models.py
    git commit -m "feat: define source target mapping model"

---

### Task 2: Versioned Reference CSV Parser

**Files:**

- Create: src/un_migration/mapping/reference.py
- Create: tests/unit/mapping/test_reference.py
- Create: examples/mappings/water_reference.csv

**Interfaces:**

- Produces: load_reference(path: str | Path) -> ReferenceTable and
  normalize_reference(table: ReferenceTable) -> str.

- [ ] **Step 1: Write failing parser tests**

Use temporary CSV files to test multiple dataset groups, booleans, target types,
null policies, JSON transform parameters, deterministic normalization, missing
headers, unsupported schema version, invalid JSON, empty files, and duplicate
rows. Errors use MappingError codes reference.not-found, reference.header,
reference.version, reference.row, and reference.empty.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/mapping/test_reference.py -q

Expected: import fails for mapping.reference.

- [ ] **Step 3: Implement strict CSV parsing**

Required headers are schema_version, source_dataset, target_dataset,
source_field, target_field, target_type, required, null_policy, default,
transform, and transform_parameters. Parse rows through csv.DictReader with
utf-8-sig and strict mode. Convert target_type and null_policy through enums,
required through the exact values true or false, and parameters through
json.loads after requiring a JSON object.

Group rows by ordered source/target dataset pair. normalize_reference writes the
same required header and rows in dataset and field order with lowercase boolean
text, compact sorted JSON parameters, and a final newline.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/mapping/test_reference.py -q
    .venv/bin/python -m mypy src/un_migration/mapping/reference.py

- [ ] **Step 5: Commit**

    git add src/un_migration/mapping/reference.py tests/unit/mapping/test_reference.py examples/mappings/water_reference.csv
    git commit -m "feat: parse versioned mapping reference tables"

---

### Task 3: Schema-Aware Mapping Validation

**Files:**

- Create: src/un_migration/mapping/validation.py
- Create: tests/unit/mapping/test_validation.py

**Interfaces:**

- Produces: MappingValidationResult and
  validate_mapping(mapping, source, target=None) -> MappingValidationResult.

- [ ] **Step 1: Write failing validation tests**

Test missing source fields, missing target fields, incompatible types, string
length narrowing, numeric widening, nullable-to-required risks, exact valid
mapping, and deterministic finding order. Findings use rule IDs
mapping.source-field, mapping.target-field, mapping.type,
mapping.length, and mapping.nullability.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/mapping/test_validation.py -q

- [ ] **Step 3: Implement compatibility policy**

~~~python
_WIDENING = {
    FieldType.INTEGER: frozenset({FieldType.INTEGER, FieldType.FLOAT, FieldType.DECIMAL}),
    FieldType.FLOAT: frozenset({FieldType.FLOAT, FieldType.DECIMAL}),
}


@dataclass(frozen=True, slots=True)
class MappingValidationResult:
    findings: FindingCollection

    @property
    def valid(self) -> bool:
        return not self.findings.failed()
~~~

Iterate mapping fields in declared order, use inventory.field for
case-insensitive lookup, and construct deterministic Finding IDs from a
SequenceIdGenerator.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/mapping/test_validation.py -q

- [ ] **Step 5: Commit**

    git add src/un_migration/mapping/validation.py tests/unit/mapping/test_validation.py
    git commit -m "feat: validate mappings against inventories"

---

### Task 4: Typed Filter AST

**Files:**

- Create: src/un_migration/filters/__init__.py
- Create: src/un_migration/filters/ast.py
- Create: tests/unit/filters/test_ast.py

**Interfaces:**

- Produces: LiteralValue, Field, Parameter, CompareOperator, Compare, InList,
  IsNull, Not, And, Or, Expression, and normalize(expression) -> str.

- [ ] **Step 1: Write failing AST tests**

Test frozen nodes, nonempty IN lists, valid parameter names, normalized operator
spacing, required parentheses that preserve precedence, date/datetime literal
formatting, apostrophe escaping, and deterministic normalization.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_ast.py -q

- [ ] **Step 3: Implement immutable discriminated nodes**

~~~python
Scalar = None | bool | int | float | Decimal | str | date | datetime


@dataclass(frozen=True, slots=True)
class Field:
    name: str


@dataclass(frozen=True, slots=True)
class Compare:
    left: Field
    operator: CompareOperator
    right: LiteralValue | Parameter


Expression: TypeAlias = Compare | InList | IsNull | Not | And | Or
~~~

normalize recursively renders canonical uppercase operators and safely quoted
literal values without producing backend SQL.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_ast.py -q
    .venv/bin/python -m mypy src/un_migration/filters

- [ ] **Step 5: Commit**

    git add src/un_migration/filters tests/unit/filters/test_ast.py
    git commit -m "feat: model safe filter expression AST"

---

### Task 5: Filter Lexer and Parser

**Files:**

- Create: src/un_migration/filters/parser.py
- Create: tests/unit/filters/test_parser.py

**Interfaces:**

- Produces: parse_filter(text: str) -> Expression and
  validate_filter_fields(expression, inventory) -> None.

- [ ] **Step 1: Write failing grammar tests**

Cover comparison operators, AND/OR/NOT precedence, parentheses, IN/NOT IN,
IS NULL/IS NOT NULL, strings with doubled apostrophes, integers, floats,
booleans, nulls, DATE and TIMESTAMP literals, :named parameters, empty input,
unknown tokens, unterminated strings, invalid operators, unknown fields, and
type-incompatible literal comparisons.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_parser.py -q

- [ ] **Step 3: Implement recursive-descent parser**

Tokenize with one anchored regex and explicit TokenKind values. Parsing methods
follow parse_or -> parse_and -> parse_not -> parse_primary -> parse_predicate.
Every method advances or raises FilterSyntaxError with code filter.syntax and a
one-based character position. Field validation uses DatasetInventory and emits
filter.unknown-field or filter.type errors before compilation.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_parser.py -q

- [ ] **Step 5: Commit**

    git add src/un_migration/filters/parser.py tests/unit/filters/test_parser.py
    git commit -m "feat: parse safe filter expressions"

---

### Task 6: In-Memory Filter Evaluator

**Files:**

- Create: src/un_migration/filters/evaluate.py
- Create: tests/unit/filters/test_evaluate.py
- Modify: src/un_migration/adapters/memory/source.py

**Interfaces:**

- Produces: evaluate(expression, record, parameters=None) -> bool.

- [ ] **Step 1: Write failing evaluation tests**

Test every comparison, null semantics, IN/NOT IN, boolean precedence, missing
record fields, missing parameters, mixed incomparable types, and filtered
MemorySourceReader count/read_batches behavior.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_evaluate.py tests/contract/test_memory_source.py -q

- [ ] **Step 3: Implement visitor-style evaluation**

Resolve Field from a record with exact then case-insensitive lookup. Resolve
Parameter from a mapping or raise FilterSyntaxError with code
filter.parameter-missing. Equality with None is permitted; ordered comparisons
with None return false. TypeError from ordered comparisons becomes
filter.incomparable. Update MemorySourceReader so Expression values are
evaluated while other objects still raise adapter.filter-unsupported.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_evaluate.py tests/contract/test_memory_source.py -q
    .venv/bin/python -m mypy src/un_migration/filters src/un_migration/adapters/memory

- [ ] **Step 5: Commit**

    git add src/un_migration/filters/evaluate.py src/un_migration/adapters/memory/source.py tests
    git commit -m "feat: evaluate filters in memory sources"

---

### Task 7: Parameterized SQL Compiler

**Files:**

- Create: src/un_migration/filters/sql.py
- Create: tests/unit/filters/test_sql.py

**Interfaces:**

- Produces: SqlDialect, CompiledSql, and
  compile_sql(expression, dialect, parameters=None) -> CompiledSql.

- [ ] **Step 1: Write failing compiler tests**

Test quoted identifiers, qmark and named placeholder dialects, parameter order,
IN expansion, null predicates, apostrophes remaining in parameter values rather
than SQL text, date/datetime parameters, missing parameters, and nested
parentheses.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_sql.py -q

- [ ] **Step 3: Implement value-separating compiler**

~~~python
@dataclass(frozen=True, slots=True)
class SqlDialect:
    identifier_quote: str = '"'
    placeholder: Literal['qmark', 'named'] = 'qmark'


@dataclass(frozen=True, slots=True)
class CompiledSql:
    text: str
    parameters: tuple[object, ...] | Mapping[str, object]
~~~

The compiler never interpolates a literal into SQL. It appends literal values to
an ordered parameter list or stable p1, p2 named mapping.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_sql.py -q

- [ ] **Step 5: Commit**

    git add src/un_migration/filters/sql.py tests/unit/filters/test_sql.py
    git commit -m "feat: compile filters to parameterized SQL"

---

### Task 8: ArcPy Where-Clause Compiler

**Files:**

- Create: src/un_migration/filters/arcpy.py
- Create: tests/unit/filters/test_arcpy.py

**Interfaces:**

- Produces: compile_arcpy(expression, delimit_field, parameters=None) -> str.

- [ ] **Step 1: Write failing ArcPy compiler tests**

Use a fake delimiter that returns [field]. Test strings with apostrophes,
booleans as 1/0, DATE and TIMESTAMP syntax, IN, null predicates, nested
expressions, parameters, field delimiter calls, and rejection of unsafe or
unsupported literal values.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_arcpy.py -q

- [ ] **Step 3: Implement escaped backend text compiler**

Strings replace one apostrophe with two. Dates render DATE 'YYYY-MM-DD';
datetimes render TIMESTAMP followed by an ISO second-precision value; booleans
render 1 and 0; null is valid only through IsNull. Every Field is passed to the
provided delimiter callable. Parameter values use the same literal formatter.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/filters/test_arcpy.py -q

- [ ] **Step 5: Commit**

    git add src/un_migration/filters/arcpy.py tests/unit/filters/test_arcpy.py
    git commit -m "feat: compile filters to ArcPy where clauses"

---

### Task 9: Transformation Registry and Built-ins

**Files:**

- Create: src/un_migration/transformation/__init__.py
- Create: src/un_migration/transformation/registry.py
- Create: src/un_migration/transformation/builtins.py
- Create: tests/unit/transformation/test_registry.py
- Create: tests/unit/transformation/test_builtins.py

**Interfaces:**

- Produces: TransformContext, TransformResult, Transform, TransformRegistry,
  default_registry(), and transform_record(record, mapping, registry).

- [ ] **Step 1: Write failing transformation tests**

Cover duplicate registration, unknown transform, identity, cast to every
portable scalar type, trim, upper/lower, date parse, constant and conditional
default, lookup hit/miss, concatenate, coalesce, null policies, input
immutability, and structured TransformationError context.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/transformation -q

- [ ] **Step 3: Implement registry and deterministic built-ins**

~~~python
Transform: TypeAlias = Callable[[object, Mapping[str, object]], object]


class TransformRegistry:
    def register(self, name: str, transform: Transform) -> None:
        if name in self._transforms:
            raise ValueError(f'transformation already registered: {name}')
        self._transforms[name] = transform

    def apply(
        self,
        spec: TransformSpec,
        value: object,
    ) -> object:
        try:
            transform = self._transforms[spec.name]
        except KeyError as error:
            raise TransformationError(
                code='transform.unknown',
                message=f'Unknown transformation: {spec.name}',
                guidance='Register the transformation before running migration.',
            ) from error
        return transform(value, spec.parameters)
~~~

transform_record creates a new mapping, applies null policy before transform,
casts to target_type after transform, and returns the record plus findings for
rejected nullable/default conditions.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/transformation -q
    .venv/bin/python -m mypy src/un_migration/transformation

- [ ] **Step 5: Commit**

    git add src/un_migration/transformation tests/unit/transformation
    git commit -m "feat: add deterministic transformation registry"

---

### Task 10: Mapping and Filter CLI

**Files:**

- Modify: src/un_migration/cli.py
- Create: tests/cli/test_reference.py
- Create: tests/cli/test_filter.py
- Modify: examples/mappings/water_reference.csv

**Interfaces:**

- Produces: un-migrate reference validate|normalize and
  un-migrate filter validate|explain.

- [ ] **Step 1: Write failing CLI tests**

Reference validate reports dataset/field counts and valid=true; invalid rows
exit 2 with a safe MappingError. normalize writes deterministic CSV. Filter
validate parses and checks fields from a configured source inventory. explain
emits normalized expression, parameterized SQL text/parameters, and ArcPy text.
Invalid filter exits 2 with FilterSyntaxError.

- [ ] **Step 2: Run RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/cli/test_reference.py tests/cli/test_filter.py -q

- [ ] **Step 3: Implement Typer command groups**

Add reference_app and filter_app beside existing groups. Reuse _write and typed
error to exit-code translation. JSON output contains no backend objects and uses
sorted operations and parameters. Filter explain uses a deterministic fake
ArcPy delimiter in portable environments and labels the result as preview.

- [ ] **Step 4: Run complete quality gate**

    .venv/bin/python -m ruff format --check .
    .venv/bin/python -m ruff check .
    .venv/bin/python -m mypy src/un_migration
    PYTHONPATH=src .venv/bin/python -m pytest -q
    PYTHONPATH=src .venv/bin/un-migrate reference validate examples/mappings/water_reference.csv --json
    PYTHONPATH=src .venv/bin/un-migrate filter explain "active = true AND diameter >= 8" --json
    .venv/bin/python -m build
    .venv/bin/python -m twine check dist/*

- [ ] **Step 5: Commit**

    git add src/un_migration/cli.py tests/cli examples/mappings/water_reference.csv
    git commit -m "feat: expose mapping and filter CLI"

---

## Plan Completion Evidence

- Synthetic reference CSV loads, validates, and normalizes deterministically.
- Mapping validation produces ordered explainable findings.
- Filter grammar cannot execute Python and validates source field names.
- In-memory, SQL, and ArcPy backends consume the same AST.
- SQL values remain separate parameters.
- ArcPy literals are escaped and all fields use the delimiter callback.
- Built-in transformations are deterministic and do not mutate inputs.
- Reference and filter CLI commands support human and JSON output.
- Ruff, strict mypy, all tests, builds, and Twine checks pass.
- The branch contains one substantive commit for each task.

The next subplan covers workflow planning, staging, validation execution,
checkpoints, reports, manifests, notifications, ArcPy capability boundaries, CI,
documentation, and release readiness.
