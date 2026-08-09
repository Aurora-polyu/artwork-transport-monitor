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
from artwork_monitor.domain import Condition, GPSFix, GPSFixStatus, HONG_KONG, SensorReading, SessionMonitoringRecord, TransportSession, Violation
from artwork_monitor.web import CapabilityState, ComponentCapability, PhysicalValidation, RuntimeCapabilities, WebDependencies, create_app
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

    def test_dashboard_uses_local_assets_and_correct_domain_labels(self) -> None:
        with TemporaryDirectory() as temporary:
            client = self._app(Path(temporary)).test_client()
            page = client.get("/")

            self.assertIn(b"dashboard.js", page.data)
            self.assertIn(b"vendor/socket.io.js", page.data)
            self.assertIn(b"Gravity Deviation", page.data)
            self.assertIn(b"\xe2\x89\xa4 6000 lux", page.data)
            self.assertIn(b"SIMULATION MODE", page.data)
            self.assertNotIn(b"Vibration", page.data)
            self.assertNotIn(b"cdn", page.data.lower())
            script = client.get("/static/dashboard.js")
            self.assertEqual(script.status_code, 200)
            script.close()
            socket_client = client.get("/static/vendor/socket.io.js")
            self.assertEqual(socket_client.status_code, 200)
            socket_client.close()

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
                runtime_capabilities=dependencies.runtime_capabilities,
            )
            client = create_app(dependencies=dependencies).test_client()

            report = client.get("/api/report/data?session_id=first")
            gps = client.get("/api/gps/history?session_id=first")

            self.assertEqual(report.status_code, 200)
            self.assertEqual(report.get_json()["session_id"], "first")
            self.assertEqual(report.get_json()["temperature"]["maximum"], 21.0)
            self.assertEqual(gps.get_json()["points"][0]["latitude"], 22.30)
            self.assertIn(first.session_id.encode(), client.get("/report").data)

    def test_dashboard_data_loads_one_persisted_session_with_gps_dropout(self) -> None:
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "sessions.sqlite3"
            repository = SQLiteTransportSessionRepository(database)
            started_at = datetime(2026, 8, 9, 12, 0, tzinfo=HONG_KONG)
            first = TransportSession("first", started_at)
            repository.create_session(first)
            repository.append_record(
                SessionMonitoringRecord(
                    session_id="first",
                    sequence=0,
                    reading=SensorReading(timestamp=started_at, temperature_c=21.0, humidity_percent_rh=40.0, light_lux=500.0, gravity_deviation_g=0.2),
                    gps_fix=GPSFix(started_at, GPSFixStatus.FIX, 22.30, 114.17),
                    immediate_violations=(),
                    prolonged_violations=(),
                )
            )
            dropout_at = started_at + timedelta(seconds=1)
            repository.append_record(
                SessionMonitoringRecord(
                    session_id="first",
                    sequence=1,
                    reading=SensorReading(timestamp=dropout_at, temperature_c=22.0, humidity_percent_rh=41.0, light_lux=6000.1, gravity_deviation_g=None),
                    gps_fix=GPSFix.no_fix(dropout_at),
                    immediate_violations=(Violation(Condition.LIGHT_HIGH, 6000.1, 6000.0, "lux", dropout_at),),
                    prolonged_violations=(),
                )
            )
            repository.finish_session("first", dropout_at)
            _stored_session(repository, "second", 29.0, 22.40)
            demo = create_demo_dependencies(database)
            client = create_app(dependencies=WebDependencies(
                session_repository=repository,
                report_generator=demo.report_generator,
                artwork_workflow=demo.artwork_workflow,
                transport_workflow=demo.transport_workflow,
                runtime_capabilities=demo.runtime_capabilities,
            )).test_client()

            response = client.get("/api/sessions/first/dashboard-data")

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["session_id"], "first")
            self.assertEqual(len(data["records"]), 2)
            self.assertEqual(data["records"][0]["gps"]["status"], "fix")
            self.assertEqual(data["records"][1]["gps"]["status"], "no_fix")
            self.assertIsNone(data["records"][1]["gps"]["latitude"])
            self.assertEqual(data["records"][1]["immediate_violations"][0]["condition"], "light_high")
            other = client.get("/api/sessions/second/dashboard-data").get_json()
            self.assertEqual(other["session_id"], "second")
            self.assertEqual(len(other["records"]), 1)
            self.assertEqual(other["records"][0]["reading"]["temperature_c"], 29.0)

    def test_dashboard_capabilities_are_declared_by_dependencies(self) -> None:
        with TemporaryDirectory() as temporary:
            demo = create_demo_dependencies(Path(temporary) / "web.sqlite3")
            simulated = create_app(dependencies=demo).test_client().get("/api/dashboard/capabilities").get_json()
            self.assertEqual(simulated["components"]["sensors"], {"state": "simulated", "physical_validation": "not_validated"})
            self.assertEqual(simulated["components"]["gps"], {"state": "simulated", "physical_validation": "not_validated"})
            self.assertEqual(simulated["components"]["storage"], {"state": "available", "physical_validation": "not_applicable"})

            validated = RuntimeCapabilities(
                sensors=ComponentCapability(CapabilityState.AVAILABLE, PhysicalValidation.VALIDATED),
                gps=ComponentCapability(CapabilityState.UNAVAILABLE, PhysicalValidation.NOT_VALIDATED),
                artwork=ComponentCapability(CapabilityState.AVAILABLE, PhysicalValidation.VALIDATED),
                storage=ComponentCapability(CapabilityState.AVAILABLE, PhysicalValidation.NOT_APPLICABLE),
                realtime=ComponentCapability(CapabilityState.AVAILABLE, PhysicalValidation.NOT_APPLICABLE),
            )
            configured = WebDependencies(
                session_repository=demo.session_repository,
                report_generator=demo.report_generator,
                artwork_workflow=demo.artwork_workflow,
                transport_workflow=demo.transport_workflow,
                runtime_capabilities=validated,
            )
            payload = create_app(dependencies=configured).test_client().get("/api/dashboard/capabilities").get_json()
            self.assertEqual(payload["components"]["sensors"]["physical_validation"], "validated")
            self.assertEqual(payload["components"]["gps"]["state"], "unavailable")

    def test_unknown_sessions_and_invalid_transport_request_are_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            client = self._app(Path(temporary)).test_client()

            self.assertEqual(client.get("/api/report/data?session_id=missing").status_code, 404)
            self.assertEqual(client.get("/api/gps/history?session_id=missing").status_code, 404)
            self.assertEqual(client.get("/api/sessions/missing/dashboard-data").status_code, 404)
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
