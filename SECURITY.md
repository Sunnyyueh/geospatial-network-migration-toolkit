# Security Policy

## Supported Version

Security fixes are applied to the latest release and the `main` branch.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private
security advisory reporting for this repository and include:

- affected version or commit;
- a minimal reproduction using synthetic data;
- security impact;
- whether credentials or sensitive data were exposed; and
- a suggested mitigation, if known.

Maintainers should acknowledge a complete report within seven days. Disclosure
timing is coordinated after a fix is available.

## Operational Boundaries

- The toolkit does not store credentials and does not authorize production
  deployment.
- Supply secrets through environment variables or an external secret manager.
- Treat source inventories, staged data, reports, manifests, and logs as
  potentially sensitive operational data.
- Keep `.sde` files, geodatabases, secured URLs, and runtime outputs out of Git.
- Review redacted evidence before sharing it; redaction is defense in depth.
