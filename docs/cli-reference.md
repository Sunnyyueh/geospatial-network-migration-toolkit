# CLI Reference

All commands support `--help`. Machine-readable commands accept `--json`.

## Runtime and Configuration

```text
un-migrate version [--json]
un-migrate doctor [--json]
un-migrate config validate PATH [--json]
un-migrate config render PATH
un-migrate config schema [--json]
```

`doctor` reports Python, working-directory, and optional ArcPy availability.
Rendered config is canonical JSON with secret-like adapter options redacted.

## Inventory and Reference Tables

```text
un-migrate inventory source CONFIG [--json]
un-migrate reference validate REFERENCE [--json]
un-migrate reference normalize REFERENCE [--output PATH]
```

Inventory currently supports the portable CSV adapter. Normalize emits or
writes deterministic version 1 CSV.

## Filters

```text
un-migrate filter validate EXPRESSION --config CONFIG [--dataset ID] [--json]
un-migrate filter explain EXPRESSION [--parameters-json OBJECT] [--json]
```

`validate` checks field existence and literal types against source inventory.
`explain` returns normalized syntax, parameterized SQL, and an escaped ArcPy
preview. ArcPy preview is not a database execution.

## Portable Run

```text
un-migrate run portable CONFIG REFERENCE \
  [--run-id ID] [--filter EXPRESSION] [--json]
```

The command supports only `source.adapter.kind: csv` and
`target.adapter.kind: filesystem` in version 0.1.0. When `--run-id` is omitted,
the runner combines a UTC timestamp and configuration fingerprint.

The output reports run ID, validated state, acceptance, metrics, artifact
paths, and outbox receipt. A rejected or incomplete run still writes evidence
and exits with code 3.

## Typed Error Shape

JSON errors have stable code, safe message, remediation, retryability, and
optional run/step/dataset context:

```json
{
  "error": {
    "code": "filter.unknown-field",
    "message": "Filter field 'missing' does not exist in the source inventory.",
    "guidance": "Use a field name reported by the inventory command.",
    "retryable": false,
    "context": {"dataset_id": "water-mains"}
  },
  "valid": false
}
```
