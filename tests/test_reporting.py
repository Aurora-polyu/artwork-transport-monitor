import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from artwork_monitor.adapters.persistence import SQLiteTransportSessionRepository
from artwork_monitor.adapters.simulated import SequenceGPSFixSource, SequenceSensorSource
from artwork_monitor.adapters.simulated import scenarios
from artwork_monitor.application import MonitoringService, SessionReportGenerator, render_markdown
from artwork_monitor.domain import Condition, SensorReading, TransportSession


UTC_START = datetime(2026, 8, 8, 4, 0, tzinfo=timezone.utc)


def reading(offset_seconds: int, **values: float | None) -> SensorReading:
    return SensorReading(timestamp=UTC_START + timedelta(seconds=offset_seconds), **values)


class SessionReportTests(unittest.TestCase):
    def test_normal_report_is_generated_after_sqlite_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(Path(temporary_directory) / "monitoring.sqlite3")
            self._persist(
                repository,
                "normal",
                (
                    reading(0, temperature_c=22.0, humidity_percent_rh=50.0, light_lux=500.0, gravity_deviation_g=0.0),
                    reading(2, temperature_c=22.2, humidity_percent_rh=50.5, light_lux=520.0, gravity_deviation_g=0.1),
                ),
                (0.0, 2.0),
            )
            report = SessionReportGenerator().generate_from_repository(repository, "normal")

        self.assertEqual(report.session_id, "normal")
        self.assertEqual(report.started_at, "2026-08-08T12:00:00+08:00")
        self.assertEqual(report.ended_at, "2026-08-08T12:00:04+08:00")
        self.assertEqual(report.duration_seconds, 4.0)
        self.assertEqual(report.monitoring_cycle_count, 2)
        self.assertEqual((report.temperature.minimum, report.temperature.maximum), (22.0, 22.02))
        self.assertAlmostEqual(report.temperature.mean, 22.01)
        self.assertEqual(report.immediate_violations, ())
        self.assertEqual(report.prolonged_violations, ())

    def test_abnormal_report_keeps_immediate_and_prolonged_violations_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(Path(temporary_directory) / "monitoring.sqlite3")
            abnormal_readings = tuple(
                reading(offset, temperature_c=17.9, humidity_percent_rh=75.1, light_lux=6000.1)
                for offset in (0, 2, 4)
            )
            self._persist(repository, "abnormal", abnormal_readings, (0.0, 2.0, 4.0))
            report = SessionReportGenerator().generate_from_repository(repository, "abnormal")

        self.assertEqual(len(report.immediate_violations), 9)
        self.assertEqual(len(report.prolonged_violations), 3)
        self.assertEqual(
            {violation.condition for violation in report.immediate_violations},
            {"temperature_low", "humidity_high", "light_high"},
        )
        self.assertEqual(
            {violation.condition for violation in report.prolonged_violations},
            {"temperature_low", "humidity_high", "light_high"},
        )
        self.assertTrue(all(violation.occurred_at.endswith("+08:00") for violation in report.prolonged_violations))

    def test_missing_measurements_are_explicit_not_zero_filled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(Path(temporary_directory) / "monitoring.sqlite3")
            self._persist(
                repository,
                "missing",
                (reading(0, temperature_c=None, humidity_percent_rh=None, light_lux=None, gravity_deviation_g=None),),
                (0.0,),
            )
            report = SessionReportGenerator().generate_from_repository(repository, "missing")
            markdown = render_markdown(report)

        for summary in (report.temperature, report.humidity, report.light, report.gravity_deviation):
            self.assertEqual(summary.valid_count, 0)
            self.assertEqual(summary.missing_count, 1)
            self.assertIsNone(summary.minimum)
            self.assertIsNone(summary.mean)
        self.assertIn("| temperature (°C) | n/a | n/a | n/a | 0 | 1 |", markdown)

    def test_gps_summary_distinguishes_available_no_fix_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(Path(temporary_directory) / "monitoring.sqlite3")
            self._persist(
                repository,
                "dropout",
                tuple(reading(offset, temperature_c=22.0) for offset in (0, 1, 2)),
                (0.0, 1.0, 2.0),
                gps_source=SequenceGPSFixSource(scenarios.gps_dropout().fixes),
            )
            self._persist(repository, "no-gps", (reading(0, temperature_c=22.0),), (0.0,))
            generator = SessionReportGenerator()
            dropout = generator.generate_from_repository(repository, "dropout")
            no_gps = generator.generate_from_repository(repository, "no-gps")

        self.assertEqual((dropout.gps.available_fix_count, dropout.gps.no_fix_count, dropout.gps.missing_fix_count), (2, 1, 0))
        self.assertEqual(dropout.gps.first_available_fix.latitude, 22.302)
        self.assertEqual((no_gps.gps.available_fix_count, no_gps.gps.no_fix_count, no_gps.gps.missing_fix_count), (0, 0, 1))

    def test_repeated_generation_is_deterministic_and_session_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(Path(temporary_directory) / "monitoring.sqlite3")
            self._persist(repository, "first", (reading(0, temperature_c=27.1),), (0.0,))
            self._persist(repository, "second", (reading(0, temperature_c=22.0), reading(2, temperature_c=22.2)), (0.0, 2.0))
            generator = SessionReportGenerator()
            first_once = generator.generate_from_repository(repository, "first")
            first_twice = generator.generate_from_repository(repository, "first")
            second = generator.generate_from_repository(repository, "second")

        self.assertEqual(first_once, first_twice)
        self.assertEqual(render_markdown(first_once), render_markdown(first_twice))
        self.assertEqual(first_once.monitoring_cycle_count, 1)
        self.assertEqual(second.monitoring_cycle_count, 2)
        self.assertEqual(first_once.session_id, "first")
        self.assertEqual(second.session_id, "second")
        self.assertEqual(first_once.immediate_violations[0].condition, Condition.TEMPERATURE_HIGH.value)
        self.assertEqual(second.immediate_violations, ())

    def _persist(
        self,
        repository: SQLiteTransportSessionRepository,
        session_id: str,
        readings: tuple[SensorReading, ...],
        monotonic_times: tuple[float, ...],
        *,
        gps_source: SequenceGPSFixSource | None = None,
    ) -> None:
        service = MonitoringService(SequenceSensorSource(readings), gps_source=gps_source, session_repository=repository)
        started_at = UTC_START
        service.start(TransportSession(session_id, started_at))
        for monotonic_time in monotonic_times:
            service.step(monotonic_time)
        service.stop(started_at + timedelta(seconds=4))
