# Migration Plan Template

## Project Summary

- Project name:
- Network domain: water / wastewater / stormwater / drainage / transportation / other
- Source network model:
- Target network model:
- Primary migration goal:
- Planned review environment:
- Planned acceptance process:

## Scope

### In Scope

- Source datasets:
- Target datasets:
- Asset groups/types:
- Geography or service area:
- Records selected for migration:

### Out of Scope

- Excluded datasets:
- Excluded attributes:
- Excluded geographies:
- Known future phases:

## Source Filters

Document all filters used to select migration or QA/QC records.

| Filter name | Expression | Purpose | Notes |
| --- | --- | --- | --- |
| Active assets | `life_cycle_status = 'Active'` | Limit migration to active assets. | Example only. |
| Material review | `material IN ('PVC', 'Ductile Iron')` | Review selected material values before domain mapping. | Example only. |

## Source and Target Systems

| Item | Description |
| --- | --- |
| Source workspace | Generic source workspace reference. Do not include private paths or credentials. |
| Target workspace | Generic target workspace reference. Do not include secured service URLs. |
| Staging workspace | Generic staging workspace reference. |
| Optional versioned deployment | Yes / No / Not applicable. |

## Migration Steps

1. Prepare source inventory.
2. Review data readiness.
3. Confirm source filters.
4. Complete source-to-target mapping.
5. Load selected records into staging.
6. Validate staging output.
7. Resolve QA/QC issues.
8. Optionally deploy through versioned review.
9. Record stakeholder acceptance.

## Acceptance Criteria

- Required fields populated:
- Domains validated:
- Geometry checks complete:
- Feature counts reconciled:
- Connectivity/topology review complete:
- Stakeholder review complete:

## Risks and Mitigations

| Risk | Impact | Mitigation | Owner |
| --- | --- | --- | --- |
| Unknown asset types | Mapping uncertainty | Add review category before migration. | TBD |

## Stakeholder Review

| Reviewer | Role | Review area | Status | Notes |
| --- | --- | --- | --- | --- |
| TBD | GIS lead | QA/QC review | Pending |  |
