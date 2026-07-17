# Geospatial Network Migration Toolkit v1.0 Design

Status: Approved

Date: 2026-07-16

Target release: 1.0.0

## 1. Purpose

Geospatial Network Migration Toolkit is a production-style Python toolkit for
planning, executing, validating, and documenting repeatable migrations between
legacy utility datasets and modern geospatial network models.

The public project must be genuinely usable without proprietary software. Its
portable Python core will run complete migrations against synthetic tabular and
GeoJSON datasets. ArcGIS Pro and Utility Network support will be provided through
an optional ArcPy adapter with an explicit capability matrix and import guards.

The project is intended for water, wastewater, stormwater, drainage, and similar
infrastructure networks. It prioritizes auditability, deterministic results,
safe staging, explainable validation, and an honest separation between portable
logic and vendor-specific deployment operations.

## 2. Success Criteria

Version 1.0 is complete when all of the following are true:

1. The package installs on supported CPython versions and exposes the
   un-migrate command.
2. A synthetic migration runs end to end using only standard Python adapters.
3. Configuration, inventory, mapping, filtering, transformation, staging,
   validation, reporting, and run manifests are integrated through one workflow.
4. Every public command supports actionable help and consistent exit codes.
5. JSON, CSV, Markdown, and HTML artifacts can be generated deterministically.
6. The ArcPy adapter remains import-safe outside ArcGIS Pro and publishes a clear
   capability matrix for operations that require ArcGIS.
7. Unit, component, contract, integration, CLI, and documentation checks cover
   the portable core.
8. CI verifies supported Python versions, formatting, linting, typing, tests,
   package builds, documentation links, and example execution.
9. Public examples contain only synthetic data and contain no credentials,
   internal URLs, private paths, or client-specific schemas.
10. The repository contains at least 50 substantive commits in total. Each new
    commit must represent a coherent implementation, test, documentation, or
    release-engineering milestone; empty commits and artificial history padding
    are prohibited.

## 3. Scope

### 3.1 Included in v1.0

- Typed YAML and JSON project configuration with environment interpolation.
- Dataset inventory and schema fingerprinting.
- CSV-based source-to-target reference tables.
- Safe filter expression parsing and backend-specific compilation.
- Field rename, cast, default, lookup, and derived-value transformations.
- In-memory, CSV, JSON, GeoJSON, and filesystem artifact adapters.
- Configurable validation rules and acceptance thresholds.
- Readiness, completeness, mapping, field, domain, geometry, rule-gap,
  terminal, and subnetwork-oriented checks.
- Deterministic migration plans, dry runs, resumable checkpoints, and manifests.
- Staging writes with atomic replacement for portable filesystem targets.
- JSON, CSV, Markdown, and HTML reports.
- Structured logging, audit events, checksums, timing, and redaction.
- Optional webhook notification with retry and secret redaction.
- Optional ArcPy adapter interfaces for geodatabase inventory, filtered reads,
  staging writes, append, and version-oriented deployment.
- CLI, Python API, sample profiles, synthetic data, tutorials, architecture
  records, contribution guidance, and release automation.

### 3.2 Explicit limits

- The portable core will not emulate Utility Network topology or pretend to
  reconcile and post an enterprise geodatabase.
- ArcPy integration tests require a separately provisioned licensed ArcGIS Pro
  environment and are not represented as passing in ordinary CI.
- The toolkit will not store credentials or connection files in its project
  configuration.
- Production deployment remains an explicit opt-in phase with operator
  confirmation and adapter capability checks.
- The toolkit validates and orchestrates migration work; it does not replace
  engineering judgment, topology review, or organizational change control.

## 4. Chosen Delivery Approach

The implementation will use vertical slices with a portable core first.
Each slice will introduce a small public behavior, its domain model, adapter
contract, tests, documentation, and example where applicable. This produces
reviewable progress and keeps the package runnable throughout development.

Alternative approaches were rejected:

- A breadth-first skeleton would create many modules before proving integration.
- An ArcGIS-first implementation would prevent reliable development and
  verification outside a licensed Windows environment.

## 5. Architectural Style

The package will use a ports-and-adapters architecture with a src layout.
Domain and application modules may depend only on the Python standard library
and explicitly approved portable dependencies. Vendor-specific adapters depend
inward on protocols; core modules never import ArcPy.

Dependency direction:

    CLI and Python API
            |
            v
    Application services and workflow engine
            |
            v
    Domain models, policies, and ports
            ^
            |
    Portable and ArcPy adapters

The main package is un_migration. Public imports are intentionally small and
versioned. Internal modules can evolve without forcing consumers to depend on
implementation details.

## 6. Proposed Repository Structure

    .
    ├── .github/
    │   ├── ISSUE_TEMPLATE/
    │   ├── pull_request_template.md
    │   └── workflows/
    ├── docs/
    │   ├── adr/
    │   ├── architecture/
    │   ├── concepts/
    │   ├── guides/
    │   ├── reference/
    │   └── tutorials/
    ├── examples/
    │   ├── configs/
    │   ├── data/
    │   ├── mappings/
    │   ├── outputs/
    │   └── rules/
    ├── schemas/
    ├── src/un_migration/
    │   ├── adapters/
    │   │   ├── arcpy/
    │   │   ├── filesystem/
    │   │   ├── memory/
    │   │   └── notifications/
    │   ├── application/
    │   ├── config/
    │   ├── domain/
    │   ├── filters/
    │   ├── inventory/
    │   ├── mapping/
    │   ├── observability/
    │   ├── ports/
    │   ├── reporting/
    │   ├── transformation/
    │   ├── validation/
    │   ├── workflow/
    │   ├── api.py
    │   └── cli.py
    ├── tests/
    │   ├── contract/
    │   ├── integration/
    │   ├── unit/
    │   └── fixtures/
    ├── CHANGELOG.md
    ├── CONTRIBUTING.md
    ├── SECURITY.md
    ├── pyproject.toml
    └── README.md

## 7. Core Domain Model

The domain model will use frozen dataclasses or immutable Pydantic models where
validation at system boundaries is required.

Primary concepts:

| Concept | Responsibility |
| --- | --- |
| ProjectConfig | Fully resolved and validated configuration for one project. |
| MigrationRun | Identity, timestamps, state, configuration hash, and outcome. |
| DatasetRef | Stable logical identifier independent of physical workspace paths. |
| FieldSchema | Name, type, nullability, length, precision, scale, and domain. |
| DatasetInventory | Schema, geometry metadata, feature count, and fingerprint. |
| MappingSpec | Source/target datasets, field mappings, filters, and policies. |
| Transformation | Typed rename, cast, default, lookup, or derived-value operation. |
| ValidationRule | Rule identity, scope, severity, parameters, and remediation text. |
| Finding | Evidence for one pass, warning, error, or skipped validation outcome. |
| Artifact | Typed output with media type, checksum, size, and provenance. |
| MigrationPlan | Ordered immutable steps with prerequisites and expected outputs. |
| Checkpoint | Durable record of a completed idempotent workflow step. |
| RunSummary | Counts, timings, status, findings, artifacts, and next actions. |

Stable identifiers will be generated for runs, plans, steps, findings, and
artifacts. Canonical serialization will sort keys and normalize timestamps so
checksums and snapshot tests are deterministic.

## 8. Ports and Adapter Contracts

The domain layer defines protocols for:

- SourceReader: inventory, schema reads, filtered record streaming, and counts.
- StagingWriter: initialize, write batches, finalize, abort, and report counts.
- DeploymentTarget: capability discovery, preflight, deploy, and rollback advice.
- ArtifactStore: atomic writes, reads, listing, and checksum verification.
- CheckpointStore: save and load workflow state keyed by run and step.
- Notifier: deliver a redacted run notification and return delivery evidence.
- Clock: provide timezone-aware timestamps for deterministic tests.
- IdGenerator: provide stable identifiers for deterministic tests.

All adapters must pass reusable contract tests. Capabilities are discovered at
runtime rather than inferred from adapter names. Unsupported operations return a
typed capability error before any mutation begins.

Portable adapters:

- In-memory source and staging adapters for tests and embedded usage.
- CSV and JSON record readers and writers.
- GeoJSON feature reader and writer for public geospatial examples.
- Filesystem artifact and checkpoint stores using atomic temporary-file rename.
- HTTP webhook notifier with bounded retry and redacted diagnostics.

ArcPy adapter:

- Delayed ArcPy import with a diagnostic explaining how to use the correct
  ArcGIS Pro environment.
- Workspace and feature-class inventory.
- Search-cursor based filtered streaming.
- Staging feature-class writes and append operations when supported.
- Optional enterprise version operations behind explicit capability checks.
- No false fallback that reports a deployment as successful.

## 9. Configuration Design

Configuration resolution order, from lowest to highest precedence:

1. Package defaults.
2. Project YAML or JSON file.
3. Named profile file.
4. Environment-variable substitutions.
5. Explicit CLI overrides.

Configuration sections:

- project and run naming
- source adapter and workspace
- target staging adapter and workspace
- dataset mappings and reference table
- filters and parameters
- transformation policies
- validation rules and acceptance thresholds
- reporting formats and artifact directory
- checkpoint and resume policy
- optional deployment policy
- optional notification policy
- logging and redaction policy

The config command will support validate, render, schema, and explain operations.
Rendered configuration redacts secret values and records the source of each
effective setting. A JSON Schema will be generated and versioned with the
package.

## 10. Filter Language

Filters will be parsed into a small typed abstract syntax tree instead of being
evaluated with Python eval.

Supported expressions:

- equality and ordered comparisons
- AND, OR, and NOT
- IN and NOT IN
- IS NULL and IS NOT NULL
- parentheses
- strings, numbers, booleans, nulls, dates, and datetimes
- named parameters

Compiler targets:

- in-memory Python predicate
- portable SQL with bound parameters
- ArcPy where clause using field delimiters and escaped literals
- canonical normalized expression for manifests

Identifiers are validated against the source inventory. Unsafe tokens,
unsupported functions, unknown fields, and invalid type comparisons fail during
planning before any source records are read.

## 11. Mapping and Transformation

The reference table uses a documented CSV schema with version metadata.
Rows identify source and target datasets, source and target fields, target
types, transformation names, required status, default policies, lookup tables,
and notes.

Validation detects:

- missing datasets or fields
- duplicate target assignments
- incompatible types
- missing required targets
- unknown transformations
- lookup collisions
- unmapped domain values
- invalid geometry mappings
- conflicting defaults and null policies

Transformations operate on record mappings and return a transformed record plus
structured findings. Built-in transforms include identity, rename, cast,
constant default, conditional default, trim, case normalization, date parsing,
lookup, concatenate, and coalesce. A registry supports custom transforms through
Python entry points without allowing arbitrary code in configuration.

## 12. Workflow and Data Flow

The workflow is an explicit state machine:

    CREATED
      -> CONFIGURED
      -> PLANNED
      -> INVENTORIED
      -> EXTRACTED
      -> TRANSFORMED
      -> STAGED
      -> VALIDATED
      -> ACCEPTED
      -> DEPLOYED

Terminal non-success states are CANCELLED and FAILED. A run may stop at
VALIDATED or ACCEPTED when deployment is disabled.

End-to-end flow:

1. Resolve and validate configuration.
2. Discover adapter capabilities.
3. Inventory source and target schemas.
4. Parse and validate reference mappings, filters, and rules.
5. Build an immutable plan and write its configuration fingerprint.
6. Stream selected source records in bounded batches.
7. Apply transformations and collect record-level findings.
8. Write to an isolated staging location.
9. Finalize staging atomically.
10. Run validations and calculate acceptance status.
11. Generate reports, inventories, findings, logs, and the final manifest.
12. Optionally deploy after capability checks and explicit approval policy.
13. Optionally notify reviewers with redacted artifact links.

Each step declares inputs, outputs, prerequisites, idempotency, and retry policy.
Resume verifies checksums before reusing a checkpoint. Changed configuration,
mapping, rules, or source fingerprints invalidates affected downstream steps.

Dry run performs steps 1 through 5 and reports intended mutations without
creating staging or deployment outputs.

## 13. Validation Engine

Validators implement a common protocol and return findings rather than raising
for ordinary data-quality failures.

Validator families:

- inventory and schema compatibility
- source/target count completeness
- required fields and null thresholds
- type, length, precision, and scale compatibility
- coded-value domain and subtype compatibility
- duplicate identifiers and duplicate geometries
- null, empty, malformed, and geometry-type checks
- Foundation-style asset group and asset type crosswalk readiness
- connectivity and containment rule-gap indicators
- terminal assignment readiness
- subnetwork controller and tier readiness
- version compatibility metadata

Severity levels are info, warning, error, and critical. Acceptance is computed
from configurable thresholds but critical findings always fail the run.
Skipped validators must include a machine-readable reason such as missing
capability, missing optional metadata, or explicit project policy.

## 14. Reporting and Artifacts

All output formats consume the same RunSummary and Finding models.

Run directory:

    outputs/<run-id>/
      config.resolved.json
      plan.json
      source-inventory.json
      target-inventory.json
      findings.json
      findings.csv
      report.md
      report.html
      run.log.jsonl
      manifest.json

The manifest records package version, configuration hash, input and output
checksums, adapter capabilities, plan steps, counts, timestamps, findings
summary, artifact metadata, and final state. Reports link findings to their
dataset, field, record identifier when safe, rule, evidence, and recommended
action.

HTML output is a self-contained accessible document generated from versioned
templates. Dynamic execution and external tracking assets are prohibited.

## 15. Error Handling

Exceptions are reserved for operational failures and programmer errors.
Data-quality problems are findings.

Typed error hierarchy:

- ConfigurationError
- CapabilityError
- InventoryError
- MappingError
- FilterSyntaxError
- TransformationError
- StagingError
- ValidationExecutionError
- DeploymentError
- NotificationError
- IntegrityError

Errors carry a stable code, safe message, run and step context, retryability,
operator guidance, and an optional redacted cause. Batch processing can apply
fail-fast, quarantine-record, or collect-and-continue policy. Critical integrity
errors always stop the run.

CLI exit codes:

- 0: success or accepted result
- 1: unexpected operational failure
- 2: invalid command or configuration
- 3: validation failed acceptance criteria
- 4: requested capability unavailable
- 5: partial completion requiring operator review

## 16. Safety, Security, and Privacy

- Secrets are referenced by environment variable name and never serialized.
- Logs and reports use centralized redaction for tokens, URLs, credentials, and
  configured sensitive fields.
- Path traversal is rejected for managed output directories.
- Existing targets are not overwritten unless an explicit replace policy is
  configured.
- Staging writes use isolated directories and atomic finalization.
- Deployment defaults to disabled and requires preflight validation.
- Webhook destinations must use HTTPS unless explicitly allowed for local tests.
- Public fixtures use synthetic names, geometries, and identifiers.
- Dependency review, secret scanning, and artifact inspection run in CI.

## 17. CLI and Python API

Command groups:

    un-migrate version
    un-migrate doctor
    un-migrate config validate|render|schema|explain
    un-migrate inventory source|target|compare
    un-migrate reference validate|normalize
    un-migrate filter validate|explain
    un-migrate plan
    un-migrate run
    un-migrate resume
    un-migrate validate
    un-migrate report
    un-migrate artifacts verify

Every command supports human-readable output and a machine-readable JSON mode.
Commands that mutate state support dry-run where meaningful.

The Python API exposes a small facade:

    from un_migration import MigrationToolkit, load_config

    config = load_config('examples/configs/water.yml')
    result = MigrationToolkit(config).run()

Advanced consumers may construct application services with custom adapters
through documented dependency injection.

## 18. Observability

Structured JSON Lines logs include timestamp, level, event name, run ID, step ID,
dataset ID, batch number, duration, and redacted context. Console logs remain
concise and readable.

Metrics in the summary include selected, transformed, staged, rejected, and
validated record counts; bytes read and written; step durations; finding counts;
retry counts; and adapter operations. The project will not require an external
telemetry service.

## 19. Testing Strategy

Testing is mandatory for the real implementation.

| Layer | Coverage |
| --- | --- |
| Unit | Models, parsers, compilers, transforms, policies, and serializers. |
| Property | Filter normalization, serialization round trips, and invariants. |
| Component | Mapping, inventory, validation, reporting, and workflow services. |
| Contract | Every source, staging, artifact, checkpoint, and notifier adapter. |
| Integration | Portable filesystem migration and resume behavior. |
| CLI | Help, JSON output, exit codes, errors, and end-to-end commands. |
| Golden file | Stable Markdown, HTML, JSON, CSV, and manifest artifacts. |
| Documentation | Command examples, links, configuration snippets, and tutorial run. |
| ArcPy | Import guards and mocked boundaries in portable CI; licensed tests separately. |

Tests use temporary directories, deterministic clocks and identifiers, and
synthetic fixtures. Network calls are disabled unless a test explicitly installs
a local fake server. Coverage thresholds apply to the portable core and exclude
environment-only ArcPy branches with documented reasons.

## 20. Packaging and Automation

- pyproject.toml is the single package and tool configuration source.
- The base install contains portable dependencies.
- Optional extras cover portable geospatial libraries, notifications,
  documentation, and development tooling where appropriate.
- The ArcPy adapter ships with the package but treats ArcPy as an externally
  provided ArcGIS Pro runtime dependency rather than a pip-installable extra.
- Ruff provides formatting and linting.
- mypy provides strict type checks for the portable core.
- pytest provides tests and coverage.
- Build produces wheel and source distribution.
- GitHub Actions runs checks on supported Python versions and operating systems.
- Release automation builds, verifies, generates provenance, and publishes only
  from an approved version tag.
- Dependabot or an equivalent configuration tracks workflow and Python updates.

## 21. Documentation Set

The completed documentation includes:

- concise README with a verified quick start
- installation and ArcGIS environment guidance
- configuration, mapping, filter, validation, and report references
- end-to-end water migration tutorial using synthetic data
- wastewater terminal-readiness example
- stormwater incremental-migration example
- adapter authoring guide
- architecture overview and decision records
- security and confidentiality guidance
- troubleshooting and exit-code reference
- contribution, code of conduct, changelog, and release process

Generated command and configuration references must match runtime behavior.

## 22. Delivery Decomposition and Commit Integrity

Work will be decomposed into reviewable milestones across:

1. repository and packaging foundation
2. domain models and serialization
3. configuration system and JSON Schema
4. adapter protocols and in-memory contracts
5. inventory and schema fingerprinting
6. reference-table mapping
7. filter parser and compilers
8. transformation registry
9. validation engine and validator families
10. artifact, checkpoint, and manifest infrastructure
11. workflow planning, execution, resume, and dry run
12. report renderers
13. CLI and public Python facade
14. portable filesystem and GeoJSON adapters
15. optional notifications and ArcPy adapter
16. examples, tutorials, security, CI, packaging, and release readiness

The repository baseline contains 7 commits, and the commit containing this
design will become the eighth. The implementation plan will therefore include
at least 42 additional coherent milestones so the completed repository contains
50 or more substantive commits. Commit boundaries will follow dependency order;
tests and documentation may be committed with the behavior they verify or as
separate coherent improvements. Commit messages describe actual changes.

No empty commit, timestamp rewriting, duplicate-file padding, or nonfunctional
scaffold will count toward this requirement.

## 23. Acceptance Audit

Before release, completion will be proven with:

- clean installation in a new environment
- successful package build and metadata inspection
- full portable test suite and coverage report
- lint, format, and strict type-check results
- execution of all documented portable examples
- end-to-end synthetic migration with verified artifact checksums
- failure-path runs proving exit codes and redaction
- resume run proving checkpoint invalidation rules
- documentation link and snippet verification
- ArcPy capability documentation matched against implemented adapter methods
- secret and generated-artifact scans
- git history review proving at least 50 substantive commits
- clean worktree and release tag readiness

The release will not claim licensed ArcGIS integration results that were not run.
Unavailable environment-specific checks will be reported separately from the
portable release evidence.
