import csv
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from artwork_monitor.adapters.persistence import (
    CsvTransportSessionExporter,
    SQLiteTransportSessionRepository,
)
from artwork_monitor.adapters.simulated import SequenceSensorSource
from artwork_monitor.application import MonitoringService
from artwork_monitor.domain import Condition, SensorReading, TransportSession


UTC_START = datetime(2026, 8, 8, 4, 0, tzinfo=timezone.utc)


def reading(*, timestamp: datetime, **values: float | None) -> SensorReading:
    return SensorReading(timestamp=timestamp, **values)


class TransportSessionPersistenceTests(unittest.TestCase):
    def test_sqlite_readback_retains_normal_and_violation_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(
                Path(temporary_directory) / "monitoring.sqlite3"
            )
            source = SequenceSensorSource(
                (
                    reading(
                        timestamp=UTC_START,
                        temperature_c=27.1,
                        humidity_percent_rh=50.0,
                        light_lux=500.0,
                    ),
                    reading(
                        timestamp=UTC_START + timedelta(seconds=2),
                        temperature_c=27.1,
                        humidity_percent_rh=50.0,
                        light_lux=500.0,
                    ),
                    reading(
                        timestamp=UTC_START + timedelta(seconds=4),
                        temperature_c=27.1,
                        humidity_percent_rh=50.0,
                        light_lux=500.0,
                    ),
                    reading(
                        timestamp=UTC_START + timedelta(seconds=6),
                        temperature_c=27.1,
                        humidity_percent_rh=50.0,
                        light_lux=500.0,
                    ),
                )
            )
            service = MonitoringService(source, session_repository=repository)
            service.start(TransportSession("session-normal-and-violation", UTC_START))
            for monotonic_seconds in (0.0, 2.0, 4.0, 6.0):
                service.step(monotonic_seconds)
            service.stop(UTC_START + timedelta(seconds=8))

            stored = repository.load_session("session-normal-and-violation")

        self.assertEqual(len(stored.records), 4)
        self.assertEqual(stored.records[0].sequence, 0)
        self.assertEqual(
            stored.records[0].immediate_violations[0].condition,
            Condition.TEMPERATURE_HIGH,
        )
        self.assertEqual(
            stored.records[1].immediate_violations[0].condition,
            Condition.TEMPERATURE_HIGH,
        )
        self.assertEqual(
            stored.records[2].prolonged_violations[0].condition,
            Condition.TEMPERATURE_HIGH,
        )
        self.assertEqual(stored.session.ended_at, UTC_START + timedelta(seconds=8))

    def test_normal_reading_persists_without_a_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(
                Path(temporary_directory) / "monitoring.sqlite3"
            )
            service = MonitoringService(
                SequenceSensorSource(
                    (
                        reading(
                            timestamp=UTC_START,
                            temperature_c=22.0,
                            humidity_percent_rh=50.0,
                            light_lux=500.0,
                        ),
                    )
                ),
                session_repository=repository,
            )
            service.start(TransportSession("normal", UTC_START))
            service.step(0.0)
            service.stop(UTC_START + timedelta(seconds=1))
            stored = repository.load_session("normal")

        self.assertEqual(stored.records[0].reading.temperature_c, 22.0)
        self.assertEqual(stored.records[0].immediate_violations, ())

    def test_persisted_timestamps_are_hong_kong_iso_strings_and_not_monotonic_values(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "monitoring.sqlite3"
            repository = SQLiteTransportSessionRepository(database_path)
            service = MonitoringService(
                SequenceSensorSource(
                    (reading(timestamp=UTC_START, temperature_c=22.0),)
                ),
                session_repository=repository,
            )
            service.start(TransportSession("timezone", UTC_START))
            service.step(123.456)
            service.stop(UTC_START + timedelta(seconds=2))

            connection = sqlite3.connect(database_path)
            try:
                session_row = connection.execute(
                    "SELECT started_at, ended_at FROM transport_sessions"
                ).fetchone()
                cycle_row = connection.execute(
                    "SELECT reading_timestamp FROM monitoring_cycles"
                ).fetchone()
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(monitoring_cycles)"
                    )
                }
            finally:
                connection.close()

        self.assertEqual(
            session_row, ("2026-08-08T12:00:00+08:00", "2026-08-08T12:00:02+08:00")
        )
        self.assertEqual(cycle_row, ("2026-08-08T12:00:00+08:00",))
        self.assertNotIn("monotonic_seconds", columns)

    def test_missing_values_round_trip_as_null_and_export_as_blank_csv_cells(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = SQLiteTransportSessionRepository(root / "monitoring.sqlite3")
            service = MonitoringService(
                SequenceSensorSource(
                    (
                        reading(
                            timestamp=UTC_START,
                            temperature_c=None,
                            humidity_percent_rh=None,
                            light_lux=None,
                        ),
                    )
                ),
                session_repository=repository,
            )
            service.start(TransportSession("missing-values", UTC_START))
            service.step(0.0)
            service.stop(UTC_START + timedelta(seconds=1))
            stored = repository.load_session("missing-values")
            csv_path = CsvTransportSessionExporter(root / "csv").export(stored)
            with csv_path.open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))

        record = stored.records[0]
        self.assertIsNone(record.reading.temperature_c)
        self.assertIsNone(record.reading.humidity_percent_rh)
        self.assertIsNone(record.reading.light_lux)
        self.assertEqual(rows[0]["temperature_c"], "")
        self.assertEqual(rows[0]["humidity_percent_rh"], "")
        self.assertEqual(rows[0]["light_lux"], "")

    def test_sessions_are_isolated_and_new_session_state_does_not_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteTransportSessionRepository(
                Path(temporary_directory) / "monitoring.sqlite3"
            )
            service = MonitoringService(
                SequenceSensorSource(
                    (
                        reading(timestamp=UTC_START, temperature_c=27.1),
                        reading(
                            timestamp=UTC_START + timedelta(seconds=2),
                            temperature_c=30.0,
                        ),
                    )
                ),
                session_repository=repository,
            )
            service.start(TransportSession("first", UTC_START))
            service.step(0.0)
            service.step(2.0)
            service.stop(UTC_START + timedelta(seconds=3))
            service.start(TransportSession("second", UTC_START + timedelta(minutes=1)))
            service.step(0.0)
            service.stop(UTC_START + timedelta(minutes=1, seconds=1))

            first = repository.load_session("first")
            second = repository.load_session("second")

        self.assertEqual(len(first.records), 2)
        self.assertEqual(len(second.records), 1)
        self.assertEqual(first.records[0].sequence, 0)
        self.assertEqual(second.records[0].sequence, 0)
        self.assertAlmostEqual(first.records[1].reading.temperature_c, 27.39)
        self.assertEqual(second.records[0].reading.temperature_c, 27.1)
        self.assertEqual(second.records[0].prolonged_violations, ())

    def test_csv_is_session_specific_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = SQLiteTransportSessionRepository(root / "monitoring.sqlite3")
            service = MonitoringService(
                SequenceSensorSource(
                    (reading(timestamp=UTC_START, temperature_c=27.1),)
                ),
                session_repository=repository,
            )
            service.start(TransportSession("csv-session", UTC_START))
            service.step(0.0)
            service.stop(UTC_START + timedelta(seconds=1))
            stored = repository.load_session("csv-session")
            exporter = CsvTransportSessionExporter(root / "csv")
            first_path = exporter.export(stored)
            first_contents = first_path.read_text(encoding="utf-8")
            second_path = exporter.export(stored)
            second_contents = second_path.read_text(encoding="utf-8")
            with second_path.open(newline="", encoding="utf-8") as source:
                row = next(csv.DictReader(source))

        self.assertEqual(first_path, second_path)
        self.assertEqual(first_contents, second_contents)
        self.assertEqual(row["session_id"], "csv-session")
        self.assertEqual(row["reading_timestamp"], "2026-08-08T12:00:00+08:00")
        self.assertEqual(row["immediate_violations"].count("temperature_high"), 1)
