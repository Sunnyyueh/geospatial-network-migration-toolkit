# Portable Migration Quickstart

This walkthrough uses only the repository's synthetic water-main CSV.

## 1. Verify Inputs

```bash
un-migrate config validate examples/configs/water.yml --json
un-migrate reference validate examples/mappings/water_reference.csv --json
un-migrate inventory source examples/configs/water.yml --json
```

The inventory should report five source records and typed `asset_id`,
`diameter`, `material`, `active`, and `installed_on` fields.

## 2. Inspect Selection Logic

```bash
un-migrate filter validate \
  "active = true AND diameter >= 8" \
  --config examples/configs/water.yml \
  --json

un-migrate filter explain \
  "active = true AND diameter >= 8" \
  --json
```

The SQL representation contains `?` placeholders and a separate parameter
array. The ArcPy representation is an escaped preview.

## 3. Execute the Staging Run

```bash
un-migrate run portable \
  examples/configs/water.yml \
  examples/mappings/water_reference.csv \
  --run-id water-quickstart-001 \
  --filter "active = true AND diameter >= 8" \
  --json
```

Four synthetic records are selected, transformed, staged, and validated. The
command exits 0 when the acceptance result is accepted or accepted with
warnings.

## 4. Verify Evidence

Review these files before any downstream action:

- `outputs/water-quickstart-001/staging/utility-lines.csv`
- `outputs/water-quickstart-001/reports/summary.json`
- `outputs/water-quickstart-001/reports/summary.md`
- `outputs/water-quickstart-001/logs/events.jsonl`
- `outputs/water-quickstart-001/manifests/run.json`
- `outputs/water-quickstart-001/review/index.json`

The manifest records SHA-256 checksums for staging, reports, and the event log.
The review index sets `deployment_authorized` to `false` regardless of the
acceptance result.

## 5. Rerun Safely

The same run ID is rejected because its directory already exists. Correct
inputs and choose a new run ID. Do not delete or overwrite prior evidence when
it belongs to an audit trail.
