# QA/QC Checklist

Use this checklist after loading records into a staging workspace or optional versioned review environment.

## Completeness

- [ ] Source record count is documented.
- [ ] Target/staging record count is documented.
- [ ] Filter expression is documented.
- [ ] Excluded records are documented.
- [ ] Unexpected missing records are reviewed.

## Mapping

- [ ] Source-to-target layer mapping is complete.
- [ ] Source-to-target field mapping is complete.
- [ ] Required target fields are mapped.
- [ ] Unmapped target fields are reviewed.
- [ ] Duplicate mappings are reviewed.
- [ ] Data type mismatches are reviewed.

## Domains and Asset Types

- [ ] Domain values are mapped.
- [ ] Invalid target domain values are flagged.
- [ ] Unknown asset groups/types are flagged.
- [ ] Subtypes or asset classifications are reviewed.

## Geometry and Network Quality

- [ ] Null geometries are flagged.
- [ ] Invalid geometries are flagged.
- [ ] Duplicate features are flagged.
- [ ] Overlapping features are reviewed.
- [ ] Connectivity issues are reviewed.
- [ ] Terminal assignments are reviewed, if applicable.
- [ ] Subnetwork controller readiness is reviewed, if applicable.

## Review Outcome

- [ ] Pass.
- [ ] Pass with warnings.
- [ ] Requires cleanup.
- [ ] Requires stakeholder decision.
- [ ] Re-run migration after correction.
