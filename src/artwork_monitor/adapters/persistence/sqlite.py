"""SQLite repository for deterministic, session-scoped monitoring history."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from artwork_monitor.domain import (
    GPSFix,
    GPSFixStatus,
    SensorReading,
    SessionMonitoringRecord,
    StoredTransportSession,
    TransportSession,
)

from ._serialization import timestamp_to_hong_kong_iso, violations_from_json, violations_to_json


class SQLiteTransportSessionRepository:
    """Store each transport session and its ordered cycles in one SQLite file."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def create_session(self, session: TransportSession) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO transport_sessions (session_id, started_at, ended_at) VALUES (?, ?, ?)",
                (
                    session.session_id,
                    timestamp_to_hong_kong_iso(session.started_at),
                    timestamp_to_hong_kong_iso(session.ended_at) if session.ended_at else None,
                ),
            )

    def append_record(self, record: SessionMonitoringRecord) -> None:
        reading = record.reading
        gps_fix = record.gps_fix
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO monitoring_cycles (
                    session_id, sequence, reading_timestamp,
                    temperature_c, humidity_percent_rh, light_lux,
                    acceleration_x_g, acceleration_y_g, acceleration_z_g,
                    gravity_deviation_g, inclination_degrees,
                    gps_timestamp, gps_status, gps_latitude, gps_longitude,
                    immediate_violations, prolonged_violations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.sequence,
                    timestamp_to_hong_kong_iso(reading.timestamp),
                    reading.temperature_c,
                    reading.humidity_percent_rh,
                    reading.light_lux,
                    reading.acceleration_x_g,
                    reading.acceleration_y_g,
                    reading.acceleration_z_g,
                    reading.gravity_deviation_g,
                    reading.inclination_degrees,
                    timestamp_to_hong_kong_iso(gps_fix.timestamp) if gps_fix else None,
                    gps_fix.status.value if gps_fix else None,
                    gps_fix.latitude if gps_fix else None,
                    gps_fix.longitude if gps_fix else None,
                    violations_to_json(record.immediate_violations),
                    violations_to_json(record.prolonged_violations),
                ),
            )

    def finish_session(self, session_id: str, ended_at: datetime) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE transport_sessions SET ended_at = ? WHERE session_id = ?",
                (timestamp_to_hong_kong_iso(ended_at), session_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown transport session: {session_id}")

    def load_session(self, session_id: str) -> StoredTransportSession:
        with self._connect() as connection:
            session_row = connection.execute(
                "SELECT session_id, started_at, ended_at FROM transport_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session_row is None:
                raise KeyError(f"unknown transport session: {session_id}")
            record_rows = connection.execute(
                "SELECT * FROM monitoring_cycles WHERE session_id = ? ORDER BY sequence",
                (session_id,),
            ).fetchall()

        session = TransportSession(
            session_id=session_row["session_id"],
            started_at=datetime.fromisoformat(session_row["started_at"]),
            ended_at=datetime.fromisoformat(session_row["ended_at"]) if session_row["ended_at"] else None,
        )
        return StoredTransportSession(session=session, records=tuple(self._record_from_row(row) for row in record_rows))

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS transport_sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS monitoring_cycles (
                    session_id TEXT NOT NULL REFERENCES transport_sessions(session_id),
                    sequence INTEGER NOT NULL,
                    reading_timestamp TEXT NOT NULL,
                    temperature_c REAL,
                    humidity_percent_rh REAL,
                    light_lux REAL,
                    acceleration_x_g REAL,
                    acceleration_y_g REAL,
                    acceleration_z_g REAL,
                    gravity_deviation_g REAL,
                    inclination_degrees REAL,
                    gps_timestamp TEXT,
                    gps_status TEXT,
                    gps_latitude REAL,
                    gps_longitude REAL,
                    immediate_violations TEXT NOT NULL,
                    prolonged_violations TEXT NOT NULL,
                    PRIMARY KEY (session_id, sequence)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> SessionMonitoringRecord:
        gps_fix = None
        if row["gps_status"] is not None:
            gps_fix = GPSFix(
                timestamp=datetime.fromisoformat(row["gps_timestamp"]),
                status=GPSFixStatus(row["gps_status"]),
                latitude=row["gps_latitude"],
                longitude=row["gps_longitude"],
            )
        return SessionMonitoringRecord(
            session_id=row["session_id"],
            sequence=row["sequence"],
            reading=SensorReading(
                timestamp=datetime.fromisoformat(row["reading_timestamp"]),
                temperature_c=row["temperature_c"],
                humidity_percent_rh=row["humidity_percent_rh"],
                light_lux=row["light_lux"],
                acceleration_x_g=row["acceleration_x_g"],
                acceleration_y_g=row["acceleration_y_g"],
                acceleration_z_g=row["acceleration_z_g"],
                gravity_deviation_g=row["gravity_deviation_g"],
                inclination_degrees=row["inclination_degrees"],
            ),
            gps_fix=gps_fix,
            immediate_violations=violations_from_json(row["immediate_violations"]),
            prolonged_violations=violations_from_json(row["prolonged_violations"]),
        )
