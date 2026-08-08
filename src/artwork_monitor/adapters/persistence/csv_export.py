"""One-file CSV export for a single already-stored transport session."""

from __future__ import annotations

import csv
from pathlib import Path

from artwork_monitor.domain import StoredTransportSession

from ._serialization import timestamp_to_hong_kong_iso, violations_to_json


CSV_COLUMNS = (
    "session_id", "session_started_at", "session_ended_at", "sequence", "reading_timestamp",
    "temperature_c", "humidity_percent_rh", "light_lux", "acceleration_x_g", "acceleration_y_g",
    "acceleration_z_g", "gravity_deviation_g", "inclination_degrees", "gps_timestamp", "gps_status",
    "gps_latitude", "gps_longitude", "immediate_violations", "prolonged_violations",
)


class CsvTransportSessionExporter:
    """Write a deterministic CSV containing records from exactly one session."""

    def __init__(self, output_directory: Path) -> None:
        self._output_directory = Path(output_directory)

    def export(self, stored_session: StoredTransportSession) -> Path:
        self._output_directory.mkdir(parents=True, exist_ok=True)
        path = self._output_directory / f"transport-session-{stored_session.session.session_id}.csv"
        session = stored_session.session
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for record in stored_session.records:
                reading, gps_fix = record.reading, record.gps_fix
                writer.writerow(
                    {
                        "session_id": session.session_id,
                        "session_started_at": timestamp_to_hong_kong_iso(session.started_at),
                        "session_ended_at": timestamp_to_hong_kong_iso(session.ended_at) if session.ended_at else "",
                        "sequence": record.sequence,
                        "reading_timestamp": timestamp_to_hong_kong_iso(reading.timestamp),
                        "temperature_c": reading.temperature_c if reading.temperature_c is not None else "",
                        "humidity_percent_rh": reading.humidity_percent_rh if reading.humidity_percent_rh is not None else "",
                        "light_lux": reading.light_lux if reading.light_lux is not None else "",
                        "acceleration_x_g": reading.acceleration_x_g if reading.acceleration_x_g is not None else "",
                        "acceleration_y_g": reading.acceleration_y_g if reading.acceleration_y_g is not None else "",
                        "acceleration_z_g": reading.acceleration_z_g if reading.acceleration_z_g is not None else "",
                        "gravity_deviation_g": reading.gravity_deviation_g if reading.gravity_deviation_g is not None else "",
                        "inclination_degrees": reading.inclination_degrees if reading.inclination_degrees is not None else "",
                        "gps_timestamp": timestamp_to_hong_kong_iso(gps_fix.timestamp) if gps_fix else "",
                        "gps_status": gps_fix.status.value if gps_fix else "",
                        "gps_latitude": gps_fix.latitude if gps_fix and gps_fix.latitude is not None else "",
                        "gps_longitude": gps_fix.longitude if gps_fix and gps_fix.longitude is not None else "",
                        "immediate_violations": violations_to_json(record.immediate_violations),
                        "prolonged_violations": violations_to_json(record.prolonged_violations),
                    }
                )
        return path
