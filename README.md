# Geospatial Network Migration Toolkit

`geospatial-network-migration-toolkit` is a Python 3.11+ toolkit for planning,
filtering, transforming, staging, validating, and documenting repeatable
geospatial network migrations.

Version 0.1.0 includes a real portable CSV workflow and import-safe extension
boundaries for ArcPy. The portable workflow never deploys to production: it
creates an isolated staging run, validation evidence, reports, a manifest, and
a reviewer notification bundle.

## Implemented Capabilities

- Strict YAML/JSON project configuration with environment interpolation,
  profiles, overrides, secret redaction, and generated JSON Schema.
- CSV source inventory with deterministic schema fingerprints and typed values.
- Versioned source-to-target CSV reference tables with canonical normalization.
- Schema-aware mapping validation for fields, types, lengths, and nullability.
- Safe filter parser with a typed AST; no `eval`, `exec`, or raw Python input.
- In-memory evaluation, parameterized SQL compilation, and escaped ArcPy preview.
- Deterministic transformation registry with casts, trim, case, date, default,
  lookup, concatenate, and coalesce operations.
- Managed CSV staging with run overwrite protection, schema drift checks, abort
  markers, SHA-256 artifacts, and path traversal protection.
- Completeness, required-field, duplicate-key, and allowed-value validation.
- Explicit accepted, accepted-with-warnings, rejected, and incomplete decisions.
- JSON, CSV, Markdown, and escaped HTML reports.
- Canonical manifests, redacted JSONL events, review bundles, and local outbox.
- Durable JSON checkpoints and checksum-aware resume decisions.
- Lazy ArcPy capability probing that does not import ArcPy on package import.
- Typer CLI, strict mypy, Ruff, pytest, build verification, and CI workflows.

## Safety Model

The toolkit is staging-first. A portable run:

1. validates configuration and mappings;
2. inventories the source;
3. parses and validates an optional filter;
4. transforms bounded record batches;
5. writes a new managed staging directory;
6. validates staged records;
7. renders evidence and a reviewer handoff; and
8. explicitly states that deployment is not authorized.

It never reconciles, posts, or overwrites an enterprise Utility Network. Any
future deployment adapter remains a separately authorized operation behind the
`DeploymentTarget` port.

## Quickstart

Create a virtual environment and install the development dependencies:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Inspect the included synthetic project:

```bash
un-migrate config validate examples/configs/water.yml --json
un-migrate inventory source examples/configs/water.yml --json
un-migrate reference validate examples/mappings/water_reference.csv --json
```

Validate and explain a safe filter:

```bash
un-migrate filter validate \
  "active = true AND diameter >= 8" \
  --config examples/configs/water.yml \
  --json

un-migrate filter explain \
  "active = true AND diameter >= 8" \
  --json
```

Run the portable migration:

```bash
un-migrate run portable \
  examples/configs/water.yml \
  examples/mappings/water_reference.csv \
  --run-id water-demo-001 \
  --filter "active = true AND diameter >= 8" \
  --json
```

The example writes under `outputs/water-demo-001/`:

```text
staging/utility-lines.csv
reports/summary.json
reports/summary.md
logs/events.jsonl
manifests/run.json
review/index.json
```

The local reviewer message is content-addressed under `outputs/outbox/`.

## Configuration

The included project configuration is intentionally synthetic:

```yaml
config_version: 1
project_name: Synthetic water network migration
source:
  adapter:
    kind: csv
    options: {}
  workspace: examples/data
  datasets:
    - id: water-mains
      path: water_mains.csv
target:
  adapter:
    kind: filesystem
    options: {}
  workspace: outputs/staging
reporting:
  output_directory: outputs
  formats: [json, markdown]
runtime:
  batch_size: 2
```

Environment placeholders use `${NAME}` or `${NAME:-default}`. Missing required
variables are errors. Rendered configuration replaces secret-like adapter
options with `***REDACTED***`.

Generate or inspect the exact schema with:

```bash
un-migrate config schema --json
```

## Reference Table

Version 1 reference CSV requires these columns:

```text
schema_version,source_dataset,target_dataset,source_field,target_field,
target_type,required,null_policy,default,transform,transform_parameters
```

`transform_parameters` is a JSON object. `required` is `true` or `false`, and
`null_policy` is `allow`, `reject`, or `default`.

Normalize a table deterministically:

```bash
un-migrate reference normalize mappings.csv --output normalized.csv
```

## Filter Language

The parser supports:

- `=`, `!=`, `<>`, `<`, `<=`, `>`, and `>=`;
- `AND`, `OR`, `NOT`, and parentheses;
- `IN`, `NOT IN`, `IS NULL`, and `IS NOT NULL`;
- strings with doubled apostrophes;
- integer, Decimal, Boolean, null, `DATE`, and `TIMESTAMP` literals; and
- separately supplied `:named_parameters`.

Example:

```text
active = true AND (
  material IN ('PVC', 'Ductile Iron')
  OR installed_on >= DATE '2020-01-01'
)
```

SQL compilation uses placeholders and a separate parameter container. The
ArcPy representation is an escaped preview and passes every field through an
injected backend delimiter.

## Exit Codes

| Code | Meaning |
| ---: | --- |
| 0 | Command succeeded; portable run accepted or accepted with warnings. |
| 1 | Runtime health or unexpected process failure. |
| 2 | Configuration, mapping, filter, staging, or other typed input error. |
| 3 | Portable run completed but acceptance is rejected or incomplete. |
| 4 | Requested adapter capability is unavailable. |

## Python Packages

The implementation is organized by responsibility:

```text
un_migration/
  adapters/        # CSV, memory, filesystem, and lazy ArcPy boundaries
  config/          # strict project configuration
  domain/          # immutable IDs, schemas, findings, runs, artifacts
  evidence/        # manifests and redacted structured events
  filters/         # AST, parser, evaluator, SQL, and ArcPy compiler
  inventory/       # deterministic inventory application service
  mapping/         # reference parser and schema compatibility
  ports/           # source, staging, artifact, checkpoint, deployment, notifier
  reporting/       # JSON, CSV, Markdown, and HTML renderers
  review/          # reviewer handoff bundle
  transformation/ # explicit registry and portable built-ins
  validation/      # record rules and acceptance policy
  workflow/        # DAG, checkpoints, batch and portable orchestration
```

See [Architecture](docs/architecture.md),
[CLI reference](docs/cli-reference.md), and
[Portable quickstart](docs/portable-quickstart.md).

## ArcPy Boundary

ArcPy is optional. `import un_migration` and portable commands do not import it.
`probe_arcpy()` checks module availability and a minimum ArcGIS Pro/ArcPy
version only when explicitly called. `LazyArcPyFacade` imports the proprietary
module on the first verified backend operation.

Version 0.1.0 does not implement enterprise Utility Network append,
reconcile/post, topology enablement, or production deployment. The ArcPy
boundary currently provides capability metadata and field delimiting used by
safe where-clause compilation.

## Development

Run the same local quality gate as CI:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy src/un_migration
PYTHONPATH=src python -m pytest --cov=un_migration --cov-report=term-missing
python -m build
python -m twine check dist/*
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the test-first contribution flow and
[SECURITY.md](SECURITY.md) for private vulnerability reporting.

## Data and Confidentiality

Only synthetic, public, or explicitly approved data belongs in examples and
issues. Do not commit credentials, tokens, secured URLs, `.sde` files,
geodatabases, production logs, or sensitive infrastructure identifiers.

Runtime outputs, virtual environments, environment files, connection files,
and geodatabases are ignored by Git. Event logs and outbox messages redact
known secrets, but operators must still review evidence before sharing it.

## License

Licensed under the [Apache License 2.0](LICENSE).
