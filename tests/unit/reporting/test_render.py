import csv
import io
import json
from datetime import UTC, datetime

from un_migration.domain.artifacts import Artifact, ArtifactKind, Checksum
from un_migration.domain.findings import Evidence, Finding, FindingCollection
from un_migration.domain.identity import ArtifactId, DatasetId, FindingId, RunId
from un_migration.domain.runs import MigrationRun, RunMetrics, RunSummary
from un_migration.domain.status import (
    AcceptanceStatus,
    FindingStatus,
    RunState,
    Severity,
)
from un_migration.reporting.render import render_reports, summary_payload


def summary() -> RunSummary:
    artifact = Artifact(
        ArtifactId("artifact-1"),
        ArtifactKind.STAGING,
        "run-1/staging/lines.csv",
        "text/csv",
        4,
        Checksum.sha256(b"data"),
    )
    finding = Finding(
        FindingId("finding-1"),
        "record.required",
        FindingStatus.FAILED,
        Severity.ERROR,
        "Missing <asset>|identifier",
        "Populate the field.",
        Evidence(None, "non-empty", "row-1"),
        DatasetId("utility-lines"),
        "asset_id",
    )
    return RunSummary(
        MigrationRun(
            RunId("run-1"),
            RunState.VALIDATED,
            datetime(2026, 7, 16, 12, 30, tzinfo=UTC),
        ),
        AcceptanceStatus.REJECTED,
        FindingCollection((finding,)),
        (artifact,),
        RunMetrics(
            selected=2,
            transformed=1,
            staged=1,
            rejected=1,
            validated=1,
            duration_seconds=1.25,
        ),
    )


def test_summary_payload_contains_stable_evidence_sections() -> None:
    payload = summary_payload(summary())

    assert payload["run"] == {
        "id": "run-1",
        "state": "validated",
        "started_at": "2026-07-16T12:30:00Z",
    }
    assert payload["acceptance"] == "rejected"
    assert payload["severity_counts"] == {"error": 1}
    assert payload["metrics"]["duration_seconds"] == 1.25  # type: ignore[index]


def test_render_reports_returns_all_requested_formats_deterministically() -> None:
    first = render_reports(summary(), ("json", "csv", "markdown", "html"))
    second = render_reports(summary(), ("json", "csv", "markdown", "html"))

    assert first == second
    assert [report.filename for report in first] == [
        "summary.json",
        "findings.csv",
        "summary.md",
        "summary.html",
    ]


def test_json_report_is_machine_readable() -> None:
    report = render_reports(summary(), ("json",))[0]
    payload = json.loads(report.payload)

    assert payload["artifacts"][0]["checksum"]["algorithm"] == "sha256"
    assert payload["findings"][0]["severity"] == "error"


def test_csv_report_round_trips_finding_evidence() -> None:
    report = render_reports(summary(), ("csv",))[0]
    rows = list(csv.DictReader(io.StringIO(report.payload.decode())))

    assert rows[0]["rule_id"] == "record.required"
    assert rows[0]["record_id"] == "row-1"
    assert rows[0]["actual"] == "null"


def test_markdown_escapes_table_delimiters() -> None:
    report = render_reports(summary(), ("markdown",))[0]
    text = report.payload.decode()

    assert "Missing <asset>\\|identifier" in text
    assert "Acceptance | rejected" in text


def test_html_report_escapes_untrusted_finding_text() -> None:
    report = render_reports(summary(), ("html",))[0]
    text = report.payload.decode()

    assert "Missing &lt;asset&gt;|identifier" in text
    assert "Missing <asset>" not in text


def test_empty_findings_csv_still_has_header() -> None:
    value = summary()
    empty = RunSummary(
        value.run,
        AcceptanceStatus.ACCEPTED,
        FindingCollection(),
        value.artifacts,
        value.metrics,
    )

    text = render_reports(empty, ("csv",))[0].payload.decode()
    assert text.count("\n") == 1
    assert text.startswith("finding_id,rule_id,")
