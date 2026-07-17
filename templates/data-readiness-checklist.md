# Data Readiness Checklist

Use this checklist before running a geospatial network migration.

## Source Inventory

- [ ] Source feature classes and tables are listed.
- [ ] Record counts are documented.
- [ ] Geometry types are documented.
- [ ] Required attributes are identified.
- [ ] Domains/subtypes/code lists are exported or summarized.
- [ ] Known source filters are documented.

## Attribute Readiness

- [ ] Required fields are populated.
- [ ] Null values are reviewed.
- [ ] Material values are standardized or mapped.
- [ ] Life cycle/status values are standardized or mapped.
- [ ] Asset group/type values are standardized or mapped.
- [ ] Created/edited user fields are understood, if used for filtering.
- [ ] Added/edited date fields are understood, if used for filtering.

## Geometry Readiness

- [ ] Empty geometries are identified.
- [ ] Invalid geometries are identified.
- [ ] Duplicate features are identified.
- [ ] Overlapping features are reviewed.
- [ ] Multipart features are reviewed.
- [ ] Simple vertices/connectivity issues are reviewed where applicable.

## Network Readiness

- [ ] Connectivity assumptions are documented.
- [ ] Directionality assumptions are documented.
- [ ] Terminal assignment requirements are documented, if applicable.
- [ ] Subnetwork controller requirements are documented, if applicable.
- [ ] External system dependencies are documented.

## Review Decision

- [ ] Ready for proof-of-concept migration.
- [ ] Ready for full migration.
- [ ] Needs data cleanup before migration.
- [ ] Needs stakeholder decision before migration.
