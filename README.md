# Geospatial Network Migration Toolkit

`geospatial-network-migration-toolkit` is an open-source Python toolkit for planning, configuring, running, and validating repeatable migrations between geospatial network models.

The toolkit is designed for infrastructure networks such as water, wastewater, stormwater, drainage, and other utility-style GIS networks. It can support transitions from legacy GIS network models, Geometric Networks, Trace Networks, custom enterprise geodatabase network models, or other structured source networks into modern target network models such as ArcGIS Utility Network.

For Utility Network projects, the toolkit supports a safer and more repeatable way to migrate selected records from a legacy source system into a staging or quality-control environment. For organizations that use enterprise deployment workflows, the same process can be extended into a recommended versioned review path before production reconciliation.

For schema mapping, Data Reference workbook validation, asset group/type checks, attribute-rule readiness, and dirty-area classification, see the companion foundational QA project:

`utility-network-schema-qa-toolkit`

This repository is based on generalized migration patterns and public-safe examples only. It does not include client data, company infrastructure details, server URLs, credentials, internal scripts, proprietary schemas, or confidential deliverables.

## Why This Toolkit Matters

Many utilities still maintain authoritative assets in legacy GIS network structures while transitioning to modern Utility Network platforms. That transition is often slow because migration work requires repeated manual steps:

- Reviewing source and target schemas.
- Updating data loading spreadsheets.
- Mapping legacy fields to Utility Network fields.
- Applying configurable attribute filters to isolate the records that should be migrated or reviewed.
- Loading records into an intermediate target workspace.
- Optionally appending results into a versioned Utility Network environment for enterprise review workflows.
- Reviewing errors before changes are reconciled into production.

When these steps are performed manually, teams face higher risk of missed records, inconsistent field mappings, accidental overwrites, incomplete logs, and unclear QA/QC accountability. This toolkit aims to make the workflow more repeatable, auditable, and easier to adapt across utility domains.

## Use Cases

This toolkit can support:

- Legacy geospatial network to modern target network migration.
- Geometric Network to Utility Network migration.
- Trace Network to Utility Network migration.
- Custom water, wastewater, or stormwater network model migration.
- Incremental migration of newly created or recently modified utility records.
- Water, wastewater, and stormwater Utility Network implementation support.
- Data loading worksheet preparation.
- Migration workflow orchestration based on validated source-to-target mappings.
- Attribute-filtered data extraction.
- Intermediate asset package or staging workspace loading.
- Recommended versioned Utility Network append workflows for teams that use enterprise production deployment.
- QA/QC review before reconcile/post.
- Migration logging, error reporting, and operational handoff.

## What the Toolkit Can Do

The planned toolkit provides a repeatable migration workflow:

1. Read a migration configuration file.
2. Read validated source-to-target mapping and Data Reference configuration.
3. Apply a configurable source filter to identify the records that should be migrated or reviewed.
4. Update data loading references for the current run.
5. Load source records into a target staging workspace or empty asset package.
6. Optionally append staged records to a versioned Utility Network target when the organization uses versioned enterprise review.
7. Generate logs and structured run summaries.
8. Validate loaded records before acceptance, handoff, or production reconciliation.
9. Produce QA/QC reports for analysts and project leads.
10. Optionally notify designated reviewers when errors occur.

The toolkit is intended to support a controlled migration pattern: validate schema and QA assumptions first, load into a staging workspace, review the result, then optionally use a named version or branch version when production deployment, multi-user editing, or formal reconcile/post workflows are required.

## Companion Foundation QA Layer

This migration toolkit is designed to work downstream of a schema QA layer. The recommended separation is:

```text
utility-network-schema-qa-toolkit
  -> validates schema mapping, domains, asset groups/types, Data Reference configuration,
     attribute-rule readiness, network rules, dirty areas, and QA reports

geospatial-network-migration-toolkit
  -> uses validated mappings and configuration to support migration planning,
     filtering, staging, loading, review, and optional deployment workflows
```

This separation keeps the migration workflow generic while allowing Utility Network-specific schema QA to remain focused and reusable.

## Technical Capabilities Reflected in Public Conference Workflows

The toolkit roadmap is informed by public Utility Network conference workflows covering water, wastewater, and stormwater implementation patterns. These workflows highlight that successful migration is not only a loading task; it also requires readiness assessment, Foundation alignment, dirty-area review, rules management, subnetwork configuration, and tracing validation.

Planned public-safe capabilities include:

- Migration readiness assessment for connectivity, simple vertices, unknown asset types, overlapping features, and domain coverage.
- Foundation crosswalk validation for local asset groups, asset types, subtypes, and domains.
- Data loading spreadsheet validation and update support.
- Dirty-area classification and recommended remediation categories.
- Subnetwork controller and subnetwork definition readiness checks.
- Connectivity, containment, association, and rule-gap review.
- Terminal-assignment support for directionally modeled sewer networks.
- Proof-of-concept subset workflow before scaling to a full network migration.
- Version compatibility checks for ArcGIS Pro, Enterprise, Utility Network, database, and Python environment dependencies.
- External system integration notes for asset management, modeling, inspection, and dashboard workflows.

## Documentation and Templates

This repository also includes open-source documentation templates so the toolkit can support both technical automation and human review workflows in one project.

Included documentation assets:

- [Documentation framework](docs/documentation-framework.md)
- [Migration plan template](templates/migration-plan-template.md)
- [Data readiness checklist](templates/data-readiness-checklist.md)
- [Filter configuration template](templates/filter-configuration-template.yml)
- [QA/QC checklist](templates/qa-qc-checklist.md)
- [Validation report template](templates/validation-report-template.md)

These templates are intentionally generic. They are designed for public, reusable migration planning and QA/QC workflows and should be populated only with synthetic data, public data, or organization-approved non-confidential information.

## Main Toolkit Input and Output

### Input

The toolkit is designed to accept the following generalized inputs:

| Input | Required | Description |
| --- | --- | --- |
| Source legacy GIS workspace | Yes | Authoritative legacy utility dataset, such as an enterprise geodatabase connection or exported file geodatabase. |
| Target Utility Network schema | Yes | Empty target schema, staging geodatabase, asset package, or Utility Network-compatible target workspace. |
| Data reference table | Yes | CSV, Excel, or structured table describing source datasets, target datasets, field mappings, domains, and loading rules. |
| Migration profile | Yes | Configuration identifying the utility domain, such as water, wastewater, or stormwater. |
| Source filter | Recommended | Configurable attribute or SQL-style expression used to select records for migration or QA/QC. Examples include life cycle status, material, added date, last added date, created date, last edited date, created user, last edited user, asset group, asset type, project area, or any other available source attribute. |
| Staging environment | Recommended | File geodatabase, asset package, QA/QC workspace, or other staging target where migrated records can be reviewed before acceptance. |
| Utility Network version | Recommended for enterprise deployments | Named version or branch version used when the organization needs multi-user editing, controlled review, or production reconcile/post workflows. Smaller teams may not need this configuration. |
| Authentication configuration | Required for secured systems | Credentials or tokens supplied through environment variables, local secret files, or an external secret manager. Hardcoded credentials should not be used. |
| Notification configuration | Optional | Email or webhook settings for reporting run failures or validation warnings. |
| Validation rules | Optional | YAML or JSON file defining required fields, domain checks, geometry checks, topology checks, and reporting thresholds. |
| Version/environment profile | Optional | Software and database version metadata used to check compatibility across development, staging, and production environments. |
| Subnetwork configuration metadata | Optional | Subnetwork controller, tier, asset group/type, and terminal assignment information used for readiness checks. |
| External system requirements | Optional | Notes or structured metadata for asset management, modeling, inspection, or dashboard systems that must remain compatible with migrated data. |

### Output

The toolkit can produce:

| Output | Description |
| --- | --- |
| Updated data reference table | A run-specific data loading table with refreshed paths, target references, and configurable source filters. |
| Staging workspace | Intermediate geodatabase or asset package containing transformed records before append. |
| Staging or append result | Records loaded into a staging workspace, QA/QC target, or optional Utility Network version. |
| Migration run log | Detailed log of parameters, datasets processed, feature counts, warnings, errors, and runtime status. |
| Error report | Structured CSV/JSON report of failed datasets, failed records, field-mapping issues, domain conflicts, and append errors. |
| QA/QC validation report | Human-readable Markdown/HTML report summarizing migration completeness and validation results. |
| Readiness assessment report | Summary of data health, Foundation alignment, version compatibility, and migration blockers before loading. |
| Rule-gap report | Summary of missing or inconsistent connectivity, containment, association, terminal, or subnetwork rules. |
| Notification message | Optional email or webhook alert when critical errors occur. |
| Reconciliation handoff package | Optional summary information that helps reviewers decide whether a versioned deployment is ready for reconcile/post. |

## Validator Input and Output

The validator is a core part of the toolkit. It is intended to verify that a migration run produced a reviewable, traceable result before data is accepted into the main Utility Network environment.

### Validator Input

| Validator Input | Required | Description |
| --- | --- | --- |
| Source dataset inventory | Yes | List of source feature classes, tables, feature counts, applied filters, and object identifiers included in the run. |
| Target loaded dataset inventory | Yes | List of staged or appended target datasets and resulting feature counts. |
| Data reference table | Yes | Source-to-target mapping table used during the migration run. |
| Target Utility Network schema metadata | Recommended | Target fields, required fields, asset groups, asset types, domains, subtypes, and relationship expectations. |
| Foundation crosswalk | Recommended | Mapping between local schema concepts and target Foundation asset groups, asset types, domains, tiers, and subnetworks. |
| Subnetwork and terminal metadata | Optional | Tables or exports describing controllers, tiers, terminal assignments, and directional network assumptions. |
| Migration log | Recommended | Run log generated during extraction, loading, and append steps. |
| Validation rules | Optional | Project-specific QA/QC thresholds and required checks. |

### Validator Output

| Validator Output | Description |
| --- | --- |
| Completeness summary | Compares source records selected by the configured filter against records loaded into the staging or target environment. |
| Mapping validation report | Flags missing mappings, duplicated mappings, incompatible field types, missing required fields, and unmapped target fields. |
| Domain validation report | Identifies values that do not match target coded value domains, subtypes, asset groups, or asset types. |
| Geometry validation report | Flags null geometry, invalid geometry, duplicate features, or geometry type mismatches. |
| Utility Network readiness report | Identifies records that may require additional connectivity, containment, association, or topology review. |
| Subnetwork readiness report | Flags asset types, controllers, or terminal assignments that may prevent clean subnetwork creation or tracing. |
| Rule-gap report | Identifies missing or inconsistent connectivity, containment, association, and terminal rules. |
| Error classification table | Groups errors by severity, dataset, field, rule, and recommended review action. |
| Pass/warning/fail summary | High-level decision support for whether the run is ready for analyst review or reconciliation. |
| Machine-readable report | JSON or CSV output for dashboards, audit trails, or CI-style validation. |
| Human-readable report | Markdown or HTML report suitable for migration documentation and stakeholder review. |

## Example Workflow

The public toolkit workflow is intentionally generic:

```text
Legacy Utility Dataset
        |
        v
Data Reference Table + Migration Config
        |
        v
Configurable Filtered Extraction
        |
        v
Staging Workspace / Empty Target Schema
        |
        v
Optional Versioned Utility Network Append
        |
        v
QA/QC Validation Report
        |
        v
Reviewer Decision: Fix, Re-run, Accept, or Reconcile
```

## Example CLI Design

The final command names may change, but the toolkit is intended to work like this:

```bash
un-migrate prepare-reference \
  --reference data/data_reference.csv \
  --source-workspace connections/source_legacy.sde \
  --target-workspace staging/empty_asset_package.gdb \
  --where "life_cycle_status = 'Active' AND material IN ('PVC', 'Ductile Iron')" \
  --output outputs/data_reference_updated.csv
```

Other valid filter examples may include:

```bash
--where "added_date >= DATE '2026-01-01'"
--where "last_added_date >= DATE '2026-01-01'"
--where "created_user = 'field_editor'"
--where "last_added_user = 'field_editor'"
--where "last_edited_user IN ('editor_a', 'editor_b')"
--where "material = 'Vitrified Clay'"
--where "life_cycle_status IN ('Active', 'Proposed')"
```

```bash
un-migrate load-staging \
  --reference outputs/data_reference_updated.csv \
  --config examples/water_profile.yml \
  --output-workspace outputs/staging_asset_package.gdb
```

```bash
un-migrate append-version \
  --staging-workspace outputs/staging_asset_package.gdb \
  --target-service-env UTILITY_NETWORK_TARGET_URL \
  --version-name migration_qc_2026_01 \
  --secrets-env UTILITY_NETWORK_AUTH_PROFILE \
  --log outputs/migration_run.log
```

The versioned append step is recommended for organizations that use enterprise Utility Network versioning, multi-user editing, production deployment gates, or formal reconcile/post workflows. Smaller organizations can use the staging and validation workflow without adopting versioned deployment.

```bash
un-migrate validate \
  --source-inventory outputs/source_inventory.csv \
  --target-inventory outputs/target_inventory.csv \
  --reference outputs/data_reference_updated.csv \
  --rules examples/validation_rules.yml \
  --report outputs/migration_qaqc_report.html
```

## Example Python API Design

```python
from un_migration import (
    prepare_reference_table,
    load_staging_workspace,
    append_to_utility_network_version,
    validate_migration_run,
)

reference = prepare_reference_table(
    reference_path="data/data_reference.csv",
    source_workspace="connections/source_legacy.sde",
    target_workspace="staging/empty_asset_package.gdb",
    where="life_cycle_status = 'Active' AND material IN ('PVC', 'Ductile Iron')",
)

staging = load_staging_workspace(
    reference=reference,
    profile="examples/water_profile.yml",
)

append_result = append_to_utility_network_version(
    staging_workspace=staging,
    target_service_url_env="UTILITY_NETWORK_TARGET_URL",
    version_name="migration_qc_2026_01",
)

report = validate_migration_run(
    source_inventory=append_result.source_inventory,
    target_inventory=append_result.target_inventory,
    reference=reference,
    rules="examples/validation_rules.yml",
)

report.to_html("outputs/migration_qaqc_report.html")
```

## Example Configuration

```yaml
profile_name: water
source:
  workspace_env: SOURCE_LEGACY_WORKSPACE
  filter_expression: "life_cycle_status = 'Active'"
target:
  staging_workspace: outputs/staging_asset_package.gdb
versioned_deployment:
  enabled: false
  utility_network_service_env: UTILITY_NETWORK_TARGET_URL
  version_name_template: migration_qc_{date}
security:
  auth_profile_env: UTILITY_NETWORK_AUTH_PROFILE
notifications:
  enabled: true
  on_error_only: true
validation:
  check_version_compatibility: true
  require_feature_count_match: true
  check_required_fields: true
  check_domains: true
  check_geometry: true
  check_foundation_crosswalk: true
  check_subnetwork_definitions: true
  check_terminal_assignments: true
  check_rule_gaps: true
  classify_errors: true
```

## Expected Results

A successful migration run should produce:

- A refreshed data reference table for the selected source records.
- A staging workspace containing only the records selected for migration.
- An optional versioned Utility Network append result for organizations using enterprise production reconciliation.
- A detailed log showing which datasets were processed, how many records were loaded, and whether errors occurred.
- A validation report identifying pass/warning/fail status by dataset and rule.
- A readiness report identifying migration blockers before data is loaded.
- A rule-gap report identifying missing or inconsistent Utility Network rules.
- A subnetwork readiness report identifying controller, asset type, or terminal-assignment issues.
- A structured error table that supports targeted correction rather than broad manual investigation.
- Optional notifications to reviewers if critical errors occur.

Expected practical benefits include:

- Less repetitive manual configuration.
- More consistent source-to-target mapping.
- More transparent migration QA/QC.
- Earlier detection of dirty-area causes and subnetwork readiness issues.
- Better alignment between local utility data and Foundation-style schema design.
- Reduced risk of loading incomplete or incorrect records.
- Faster identification of field, domain, geometry, and append issues.
- A repeatable methodology that can be adapted across water, wastewater, and stormwater utility networks.

## Planned Python Package

The project is intended to be installable as a Python package:

```bash
pip install geospatial-network-migration-toolkit
```

Because Utility Network data loading often depends on ArcGIS Pro and ArcPy, some features may require running inside an ArcGIS Pro Python environment. The public package can still provide configuration, validation, reporting, and workflow orchestration components through standard Python where possible.

Planned package components:

```text
un_migration/
  io.py
  readiness.py
  reference.py
  schema.py
  mapping.py
  filters.py
  foundation.py
  staging.py
  append.py
  rules.py
  subnetwork.py
  terminals.py
  validate.py
  report.py
  notify.py
  cli.py
```

Planned repository structure:

```text
geospatial-network-migration-toolkit/
  README.md
  docs/
    documentation-framework.md
  templates/
    migration-plan-template.md
    data-readiness-checklist.md
    filter-configuration-template.yml
    qa-qc-checklist.md
    validation-report-template.md
  un_migration/
    ...
```

## Roadmap

### Version 0.1.0

- Public README.
- Documentation framework.
- Migration plan template.
- Data readiness checklist.
- QA/QC checklist.
- Project structure.
- CLI skeleton.
- Data reference table parser.
- Configurable source filter generator.
- Readiness assessment checklist.
- Basic run logging.
- Basic validation report.
- Synthetic example dataset and configuration files.

### Version 0.2.0

- Source-to-target mapping validator.
- Foundation crosswalk validator.
- Source-to-target mapping template.
- Filter configuration template.
- Required field and domain validation.
- Feature count comparison.
- Version compatibility check.
- JSON, CSV, Markdown, and HTML report outputs.

### Version 0.3.0

- Staging workspace workflow.
- ArcGIS Pro/ArcPy integration notes.
- Utility-domain profiles for water, wastewater, and stormwater.
- Dirty-area classification report.
- Rule-gap report.
- Subnetwork readiness report.
- Error notification hooks.

### Version 1.0.0

- Stable CLI and Python API.
- Documented end-to-end migration workflow.
- Documented proof-of-concept subset workflow.
- Documented terminal-assignment support for directional sewer networks.
- Stable public documentation and template set.
- Public examples and tutorials.
- PyPI release suitable for external evaluation.

## Security and Confidentiality

This toolkit should never store production credentials, server URLs, or confidential database paths in source code.

Recommended practices:

- Use environment variables for secured URLs and authentication profiles.
- Keep local connection files out of Git.
- Use synthetic or public sample data.
- Redact client, employer, and infrastructure identifiers from examples.
- Do not commit logs that contain credentials, tokens, internal URLs, or protected asset information.
- Review sample outputs before publication.

## Important Limitations

This toolkit is intended to support migration preparation, automation, and QA/QC. It does not eliminate the need for experienced GIS analyst review, Utility Network design review, topology validation, or organizational change control.

Production reconcile/post decisions should remain under the control of authorized utility GIS administrators and project reviewers.

## License

This project is planned for release under the MIT License.

## Intended Audience

- Municipal utility GIS teams.
- Water, wastewater, and stormwater utility network analysts.
- GIS developers working with migration automation.
- Civil infrastructure and environmental engineering teams.
- Students and researchers studying geospatial infrastructure modernization.

## Project Status

Planning and initial documentation stage. The first implementation milestone is a Python package skeleton with a data reference parser, configurable source filter generator, validator, and sample QA/QC report.
