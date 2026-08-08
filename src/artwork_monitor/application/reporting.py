"""Deterministic, session-specific transport report generation."""

from __future__ import annotations

from dataclasses import dataclass

from artwork_monitor.domain import GPSFix, StoredTransportSession, Violation, format_hong_kong_timestamp
from artwork_monitor.ports import TransportSessionRepository


@dataclass(frozen=True, slots=True)
class NumericSummary:
    """Deterministic statistics for one measurement without imputing missing values."""

    metric: str
    unit: str
    minimum: float | None
    maximum: float | None
    mean: float | None
    valid_count: int
    missing_count: int


@dataclass(frozen=True, slots=True)
class ReportViolation:
    """A report-ready rendering-neutral copy of one condition violation."""

    condition: str
    observed_value: float
    threshold_value: float
    unit: str
    occurred_at: str


@dataclass(frozen=True, slots=True)
class GPSReportSummary:
    """GPS availability counts and the available route endpoints, if any."""

    available_fix_count: int
    no_fix_count: int
    missing_fix_count: int
    first_available_fix: GPSFix | None
    last_available_fix: GPSFix | None


@dataclass(frozen=True, slots=True)
class SessionReport:
    """One report model generated from exactly one persisted transport session."""

    session_id: str
    started_at: str
    ended_at: str | None
    duration_seconds: float | None
    monitoring_cycle_count: int
    temperature: NumericSummary
    humidity: NumericSummary
    light: NumericSummary
    gravity_deviation: NumericSummary
    immediate_violations: tuple[ReportViolation, ...]
    prolonged_violations: tuple[ReportViolation, ...]
    gps: GPSReportSummary


class SessionReportGenerator:
    """Generate report models solely from one stored, reloadable session."""

    def generate_from_repository(
        self,
        repository: TransportSessionRepository,
        session_id: str,
    ) -> SessionReport:
        return self.generate(repository.load_session(session_id))

    def generate(self, stored_session: StoredTransportSession) -> SessionReport:
        session = stored_session.session
        records = stored_session.records
        duration_seconds = None
        if session.ended_at is not None:
            duration_seconds = (session.ended_at - session.started_at).total_seconds()

        immediate = tuple(
            _report_violation(violation)
            for record in records
            for violation in record.immediate_violations
        )
        prolonged = tuple(
            _report_violation(violation)
            for record in records
            for violation in record.prolonged_violations
        )
        return SessionReport(
            session_id=session.session_id,
            started_at=format_hong_kong_timestamp(session.started_at),
            ended_at=format_hong_kong_timestamp(session.ended_at) if session.ended_at else None,
            duration_seconds=duration_seconds,
            monitoring_cycle_count=len(records),
            temperature=_numeric_summary("temperature", "°C", [record.reading.temperature_c for record in records]),
            humidity=_numeric_summary("humidity", "%RH", [record.reading.humidity_percent_rh for record in records]),
            light=_numeric_summary("light", "lux", [record.reading.light_lux for record in records]),
            gravity_deviation=_numeric_summary(
                "gravity deviation", "g", [record.reading.gravity_deviation_g for record in records]
            ),
            immediate_violations=immediate,
            prolonged_violations=prolonged,
            gps=_gps_summary(records),
        )


def render_markdown(report: SessionReport) -> str:
    """Render a stable, human-readable Markdown report for the software demo."""

    lines = [
        "# Transport Session Report",
        "",
        f"- Session ID: {report.session_id}",
        f"- Started: {report.started_at}",
        f"- Ended: {report.ended_at or 'not recorded'}",
        f"- Duration: {_duration_text(report.duration_seconds)}",
        f"- Monitoring cycles: {report.monitoring_cycle_count}",
        "",
        "## Sensor summaries",
        "",
        "| Measurement | Min | Max | Mean | Valid | Missing |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for summary in (report.temperature, report.humidity, report.light, report.gravity_deviation):
        lines.append(
            f"| {summary.metric} ({summary.unit}) | {_number(summary.minimum)} | {_number(summary.maximum)} | "
            f"{_number(summary.mean)} | {summary.valid_count} | {summary.missing_count} |"
        )

    lines.extend(["", "## Immediate violations", ""])
    lines.extend(_violation_lines(report.immediate_violations))
    lines.extend(["", "## Prolonged violations", ""])
    lines.extend(_violation_lines(report.prolonged_violations))
    lines.extend(
        [
            "",
            "## GPS",
            "",
            f"- Available fixes: {report.gps.available_fix_count}",
            f"- Explicit no-fix states: {report.gps.no_fix_count}",
            f"- Missing GPS records: {report.gps.missing_fix_count}",
        ]
    )
    if report.gps.first_available_fix is not None:
        lines.append(f"- First available fix: {_gps_text(report.gps.first_available_fix)}")
        lines.append(f"- Last available fix: {_gps_text(report.gps.last_available_fix)}")
    return "\n".join(lines) + "\n"


def _numeric_summary(metric: str, unit: str, values: list[float | None]) -> NumericSummary:
    valid_values = [value for value in values if value is not None]
    return NumericSummary(
        metric=metric,
        unit=unit,
        minimum=min(valid_values) if valid_values else None,
        maximum=max(valid_values) if valid_values else None,
        mean=sum(valid_values) / len(valid_values) if valid_values else None,
        valid_count=len(valid_values),
        missing_count=len(values) - len(valid_values),
    )


def _report_violation(violation: Violation) -> ReportViolation:
    return ReportViolation(
        condition=violation.condition.value,
        observed_value=violation.observed_value,
        threshold_value=violation.threshold_value,
        unit=violation.unit,
        occurred_at=format_hong_kong_timestamp(violation.occurred_at),
    )


def _gps_summary(records: tuple) -> GPSReportSummary:
    available_fixes = [record.gps_fix for record in records if record.gps_fix is not None and record.gps_fix.is_available]
    no_fix_count = sum(1 for record in records if record.gps_fix is not None and not record.gps_fix.is_available)
    missing_fix_count = sum(1 for record in records if record.gps_fix is None)
    return GPSReportSummary(
        available_fix_count=len(available_fixes),
        no_fix_count=no_fix_count,
        missing_fix_count=missing_fix_count,
        first_available_fix=available_fixes[0] if available_fixes else None,
        last_available_fix=available_fixes[-1] if available_fixes else None,
    )


def _duration_text(duration_seconds: float | None) -> str:
    return f"{duration_seconds:.3f} seconds" if duration_seconds is not None else "not recorded"


def _number(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "n/a"


def _violation_lines(violations: tuple[ReportViolation, ...]) -> list[str]:
    if not violations:
        return ["- None"]
    return [
        f"- {violation.occurred_at}: {violation.condition} "
        f"({violation.observed_value:.3f} {violation.unit}; threshold {violation.threshold_value:.3f} {violation.unit})"
        for violation in violations
    ]


def _gps_text(fix: GPSFix | None) -> str:
    assert fix is not None
    return f"{format_hong_kong_timestamp(fix.timestamp)} at {fix.latitude:.6f}, {fix.longitude:.6f}"
