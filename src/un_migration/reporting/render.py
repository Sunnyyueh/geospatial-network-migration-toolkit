import csv
import html
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from un_migration.domain.findings import Finding
from un_migration.domain.runs import RunSummary
from un_migration.domain.serialization import canonical_json

ReportFormat = Literal["json", "csv", "markdown", "html"]


@dataclass(frozen=True, slots=True)
class RenderedReport:
    format: ReportFormat
    filename: str
    media_type: str
    payload: bytes


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _finding_payload(finding: Finding) -> dict[str, object]:
    evidence: dict[str, object] | None = None
    if finding.evidence is not None:
        evidence = {
            "actual": finding.evidence.actual,
            "expected": finding.evidence.expected,
            "record_id": finding.evidence.record_id,
        }
    return {
        "id": str(finding.id),
        "rule_id": finding.rule_id,
        "status": finding.status.value,
        "severity": finding.severity.name.casefold(),
        "message": finding.message,
        "remediation": finding.remediation,
        "dataset_id": str(finding.dataset_id) if finding.dataset_id else None,
        "field_name": finding.field_name,
        "evidence": evidence,
    }


def summary_payload(summary: RunSummary) -> dict[str, object]:
    """Create the shared deterministic report view model."""

    return {
        "run": {
            "id": str(summary.run.id),
            "state": summary.run.state.value,
            "started_at": _timestamp(summary.run.started_at),
        },
        "acceptance": summary.acceptance.value,
        "metrics": {
            "selected": summary.metrics.selected,
            "transformed": summary.metrics.transformed,
            "staged": summary.metrics.staged,
            "rejected": summary.metrics.rejected,
            "validated": summary.metrics.validated,
            "duration_seconds": summary.metrics.duration_seconds,
        },
        "severity_counts": summary.findings.count_by_severity(),
        "artifacts": [
            {
                "id": str(artifact.id),
                "kind": artifact.kind.value,
                "path": artifact.path,
                "media_type": artifact.media_type,
                "size": artifact.size,
                "checksum": {
                    "algorithm": artifact.checksum.algorithm,
                    "digest": artifact.checksum.digest,
                },
            }
            for artifact in summary.artifacts
        ],
        "findings": [_finding_payload(finding) for finding in summary.findings],
    }


_CSV_FIELDS = (
    "finding_id",
    "rule_id",
    "status",
    "severity",
    "dataset_id",
    "field_name",
    "message",
    "remediation",
    "record_id",
    "actual",
    "expected",
)


def _csv(summary: RunSummary) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for finding in summary.findings:
        evidence = finding.evidence
        writer.writerow(
            {
                "finding_id": finding.id,
                "rule_id": finding.rule_id,
                "status": finding.status.value,
                "severity": finding.severity.name.casefold(),
                "dataset_id": finding.dataset_id or "",
                "field_name": finding.field_name or "",
                "message": finding.message,
                "remediation": finding.remediation or "",
                "record_id": evidence.record_id if evidence else "",
                "actual": canonical_json(evidence.actual) if evidence else "",
                "expected": canonical_json(evidence.expected) if evidence else "",
            }
        )
    return stream.getvalue().encode("utf-8")


def _markdown(summary: RunSummary) -> bytes:
    def escape(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        f"# Migration Run {summary.run.id}",
        "",
        "| Attribute | Value |",
        "| --- | --- |",
        f"| State | {summary.run.state.value} |",
        f"| Acceptance | {summary.acceptance.value} |",
        f"| Selected | {summary.metrics.selected} |",
        f"| Staged | {summary.metrics.staged} |",
        f"| Rejected | {summary.metrics.rejected} |",
        "",
        "## Findings",
        "",
        "| Severity | Rule | Dataset | Field | Message | Remediation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not summary.findings.items:
        lines.append("| - | - | - | - | No findings | - |")
    for finding in summary.findings:
        lines.append(
            "| "
            + " | ".join(
                escape(value)
                for value in (
                    finding.severity.name.casefold(),
                    finding.rule_id,
                    finding.dataset_id or "",
                    finding.field_name or "",
                    finding.message,
                    finding.remediation or "",
                )
            )
            + " |"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _html(summary: RunSummary) -> bytes:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(finding.severity.name.casefold())}</td>"
        f"<td>{html.escape(finding.rule_id)}</td>"
        f"<td>{html.escape(str(finding.dataset_id or ''))}</td>"
        f"<td>{html.escape(finding.field_name or '')}</td>"
        f"<td>{html.escape(finding.message)}</td>"
        f"<td>{html.escape(finding.remediation or '')}</td>"
        "</tr>"
        for finding in summary.findings
    )
    if not rows:
        rows = '<tr><td colspan="6">No findings</td></tr>'
    document = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>Migration Run {html.escape(str(summary.run.id))}</title></head><body>"
        f"<h1>Migration Run {html.escape(str(summary.run.id))}</h1>"
        f"<p>Acceptance: <strong>{html.escape(summary.acceptance.value)}</strong></p>"
        "<table><thead><tr><th>Severity</th><th>Rule</th><th>Dataset</th>"
        "<th>Field</th><th>Message</th><th>Remediation</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>\n"
    )
    return document.encode("utf-8")


def render_reports(
    summary: RunSummary,
    formats: tuple[ReportFormat, ...],
) -> tuple[RenderedReport, ...]:
    """Render requested formats from one shared summary view."""

    reports: list[RenderedReport] = []
    for format_name in formats:
        if format_name == "json":
            reports.append(
                RenderedReport(
                    format_name,
                    "summary.json",
                    "application/json",
                    (canonical_json(summary_payload(summary)) + "\n").encode("utf-8"),
                )
            )
        elif format_name == "csv":
            reports.append(
                RenderedReport(format_name, "findings.csv", "text/csv", _csv(summary))
            )
        elif format_name == "markdown":
            reports.append(
                RenderedReport(
                    format_name,
                    "summary.md",
                    "text/markdown",
                    _markdown(summary),
                )
            )
        elif format_name == "html":
            reports.append(
                RenderedReport(format_name, "summary.html", "text/html", _html(summary))
            )
    return tuple(reports)
