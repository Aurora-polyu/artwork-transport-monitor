from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest

from artwork_monitor.adapters.persistence import SQLiteTransportSessionRepository
from artwork_monitor.domain import GPSFix, GPSFixStatus, HONG_KONG, SensorReading, SessionMonitoringRecord, TransportSession
from artwork_monitor.web import WebDependencies, create_app
from artwork_monitor.web.services import create_demo_dependencies


class WebAppTests(unittest.TestCase):
    def _app(self, directory: Path):
        app = create_app(dependencies=create_demo_dependencies(directory / "web.sqlite3"))
        app.config.update(TESTING=True)
        return app

    def test_factory_creation_does_not_start_a_thread_or_workflow(self) -> None:
        with TemporaryDirectory() as temporary:
            before = threading.active_count()
            app = self._app(Path(temporary))

            self.assertEqual(threading.active_count(), before)
            self.assertEqual(app.extensions["artwork_monitor_dependencies"].artwork_workflow.checking, False)

    def test_main_and_legacy_equivalent_pages_render(self) -> None:
        with TemporaryDirectory() as temporary:
            client = self._app(Path(temporary)).test_client()

            for path, title in (
                ("/", b"Artwork Transportation Monitoring"),
                ("/transport", b"Transport Monitoring"),
                ("/check", b"Artwork Checking"),
                ("/report", b"Session Reports"),
                ("/gps", b"GPS Tracking"),
            ):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(title, response.data)

    def test_artwork_http_actions_delegate_to_injected_workflow(self) -> None:
        with TemporaryDirectory() as temporary:
            app = self._app(Path(temporary))
            client = app.test_client()

            self.assertEqual(client.post("/check/start").get_json()["checking"], True)
            for _ in range(5):
                client.post("/check/step")
            state = client.get("/check/status").get_json()

            self.assertEqual(state["artworks"][0]["status"], "in")
            self.assertEqual(client.post("/check/stop").get_json()["checking"], False)

    def test_report_and_gps_are_selected_by_one_session_only(self) -> None:
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "sessions.sqlite3"
            repository = SQLiteTransportSessionRepository(database)
            first = _stored_session(repository, "first", 21.0, 22.30)
            _stored_session(repository, "second", 29.0, 22.40)
            dependencies = create_demo_dependencies(database)
            dependencies = WebDependencies(
                session_repository=repository,
                report_generator=dependencies.report_generator,
                artwork_workflow=dependencies.artwork_workflow,
                transport_workflow=dependencies.transport_workflow,
            )
            client = create_app(dependencies=dependencies).test_client()

            report = client.get("/api/report/data?session_id=first")
            gps = client.get("/api/gps/history?session_id=first")

            self.assertEqual(report.status_code, 200)
            self.assertEqual(report.get_json()["session_id"], "first")
            self.assertEqual(report.get_json()["temperature"]["maximum"], 21.0)
            self.assertEqual(gps.get_json()["points"][0]["latitude"], 22.30)
            self.assertIn(first.session_id.encode(), client.get("/report").data)

    def test_unknown_sessions_and_invalid_transport_request_are_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            client = self._app(Path(temporary)).test_client()

            self.assertEqual(client.get("/api/report/data?session_id=missing").status_code, 404)
            self.assertEqual(client.get("/api/gps/history?session_id=missing").status_code, 404)
            self.assertEqual(client.post("/transport/start", json={}).status_code, 400)

    def test_separate_factories_have_no_artwork_state_leakage(self) -> None:
        with TemporaryDirectory() as temporary:
            first = self._app(Path(temporary) / "one")
            second = self._app(Path(temporary) / "two")
            first_client = first.test_client()

            first_client.post("/check/start")
            for _ in range(5):
                first_client.post("/check/step")

            self.assertEqual(first_client.get("/check/status").get_json()["artworks"][0]["status"], "in")
            self.assertEqual(second.test_client().get("/check/status").get_json()["artworks"][0]["status"], "out")

    def test_importing_and_creating_apps_loads_no_hardware_or_background_thread(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, threading; before = threading.active_count(); "
                "from artwork_monitor.web import create_app; first = create_app(); second = create_app(); "
                "assert threading.active_count() == before; "
                "assert not any(name.split('.')[0] in {'cv2', 'tflite_runtime', 'picamera', 'RPi', 'smbus2'} for name in sys.modules); "
                "print('safe')",
            ],
            cwd=project_root,
            env={**os.environ, "PYTHONPATH": os.pathsep.join([str(project_root / "src"), "/private/tmp/artwork-monitor-task10-flask"])},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "safe")


def _stored_session(
    repository: SQLiteTransportSessionRepository,
    session_id: str,
    temperature: float,
    latitude: float,
) -> TransportSession:
    started_at = datetime(2026, 8, 9, 12, 0, tzinfo=HONG_KONG)
    session = TransportSession(session_id, started_at)
    repository.create_session(session)
    repository.append_record(
        SessionMonitoringRecord(
            session_id=session_id,
            sequence=0,
            reading=SensorReading(timestamp=started_at, temperature_c=temperature),
            gps_fix=GPSFix(started_at, GPSFixStatus.FIX, latitude, 114.17),
            immediate_violations=(),
            prolonged_violations=(),
        )
    )
    repository.finish_session(session_id, started_at + timedelta(seconds=1))
    return session
