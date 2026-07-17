# Workflow, Reporting, and Release Readiness Implementation Plan

**Goal:** Complete a real portable CSV-to-staging migration path with durable
evidence, validation, reports, review handoff, optional ArcPy capability
detection, automation, and operator documentation.

**Architecture:** The application layer coordinates existing ports and pure
domain services. Filesystem adapters write only managed run directories and
use atomic replacement. Proprietary ArcPy integration remains delayed and
capability-based. Every run produces independently verifiable artifacts before
any optional deployment boundary.

**Tech Stack:** Python 3.11+, standard library, Pydantic, Typer, Jinja2,
pytest, Ruff, strict mypy, GitHub Actions, and synthetic CSV fixtures.

## Global Constraints

- Use failing tests before implementation for every code task.
- Never overwrite a completed run directory or escape a configured workspace.
- Stage records before acceptance; no production deployment is automatic.
- Checkpoints and manifests carry SHA-256 checksums and UTC timestamps.
- Logs and notifications redact configured secret-like values.
- ArcPy is imported only after an explicit capability check.
- Reports use escaped content and deterministic ordering.
- Each task ends in one coherent, substantive commit.

### Task 1: Workflow Planning and Batch Transformation

Create `un_migration.workflow.planning` and `un_migration.workflow.execution`.
Build the canonical dependency graph, select one reference-table mapping per
configured source dataset, transform bounded batches, aggregate selected,
transformed, and rejected counts, and preserve record-level findings. Test
deterministic step ordering, missing mappings, partial rejection, batching, and
source immutability.

Commit: `feat: orchestrate portable batch transformations`

### Task 2: Filesystem Staging and Artifact Store

Create filesystem `ArtifactStore` and CSV `StagingWriter` implementations.
Constrain all paths below a managed root, initialize an isolated run directory,
write headers once, reject schema drift, finalize immutable artifact metadata,
verify checksums, and abort into an explicit marker. Test traversal rejection,
duplicate initialization, multi-batch output, checksum verification, and abort.

Commit: `feat: persist managed staging artifacts`

### Task 3: Durable Checkpoint Store

Create a JSON filesystem `CheckpointStore` using canonical serialization and
atomic temporary-file replacement. Validate run/step identity, timestamp, and
checksums while loading; reject corrupt or conflicting checkpoints. Add a
resume decision service that skips only idempotent steps with matching input
checksums. Test save/load, corruption, conflicts, path safety, and resume rules.

Commit: `feat: add durable workflow checkpoints`

### Task 4: Validation Execution and Acceptance Policy

Create portable completeness, required-field, duplicate-key, and allowed-value
validators plus an acceptance policy. Generate deterministic findings with
record evidence, support configurable warning/error thresholds, and derive
accepted, accepted-with-warnings, rejected, or incomplete outcomes. Test every
rule, aggregation, stable IDs, and decision boundary.

Commit: `feat: execute validation and acceptance policy`

### Task 5: Multi-Format Reporting

Create report view models and deterministic JSON, CSV, Markdown, and escaped
HTML renderers for `RunSummary`. Include run state, acceptance, metrics,
artifact checksums, severity counts, and finding details. Test snapshots of
stable sections, CSV round-trip, HTML escaping, empty findings, and timezone
formatting.

Commit: `feat: render migration evidence reports`

### Task 6: Manifests and Redacted Structured Logs

Create a manifest builder with package/config/reference fingerprints, adapter
capabilities, run plan, artifact inventory, and timestamps. Add JSON-lines
structured events with recursive key/value redaction and no traceback leakage.
Test deterministic manifests, secret redaction, event ordering, and checksum
verification through the artifact store.

Commit: `feat: record manifests and redacted run events`

### Task 7: Notification Outbox and Review Bundle

Create a filesystem notifier implementing the existing port and a review-bundle
service that writes a reviewer-safe notification, report index, artifact list,
acceptance decision, and deployment disclaimer. Test delivery receipts,
managed paths, redaction, rejected-run wording, and immutable outbox messages.

Commit: `feat: prepare reviewer notification bundles`

### Task 8: Import-Safe ArcPy Capability Boundary

Create an ArcPy capability probe and lazy facade. Report unavailable,
available, and incompatible versions without importing ArcPy during package
import. Expose field delimiting and source capability metadata only after a
successful probe. Use injected import/spec/version functions in tests.

Commit: `feat: add lazy ArcPy capability boundary`

### Task 9: End-to-End Portable Run Command

Add `un-migrate run portable CONFIG REFERENCE` with optional filter and run ID.
Wire config loading, CSV inventory/read, mapping validation, filter validation,
batch transformation, managed CSV staging, validation, reports, manifest, and
review notification. Default to a deterministic generated run ID, reject
existing output, emit JSON summary, and return nonzero for rejected acceptance.
Test a synthetic successful run, rejected null, filter selection, rerun safety,
and complete artifact layout.

Commit: `feat: run portable migrations end to end`

### Task 10: CI, Security, Documentation, and Release Audit

Add GitHub Actions for supported Python versions, Ruff, strict mypy, tests with
coverage, build/Twine, dependency review, and CodeQL. Add security and
contribution guidance, architecture and CLI references, correct the README from
planned to implemented capabilities, document ArcPy limitations, provide a
synthetic quickstart, and audit license/package metadata. Run the complete
quality gate and require at least 50 meaningful commits in branch history.

Commit: `docs: complete release and operator readiness`

## Completion Evidence

- Portable example performs a real CSV-to-CSV staging migration.
- A run cannot escape or silently overwrite its managed directory.
- Findings drive an explicit acceptance result before review handoff.
- JSON, CSV, Markdown, and HTML evidence share the same run summary.
- Manifest/checkpoint/artifact checksums are independently verifiable.
- Notifications and structured events redact secrets.
- ArcPy remains optional and import-safe.
- CI, security, contribution, architecture, and operator docs match behavior.
- Ruff, strict mypy, all tests, coverage, build, and Twine checks pass.
- Branch history contains at least 50 substantive commits.
