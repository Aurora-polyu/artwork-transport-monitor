from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from artwork_monitor.adapters.persistence import SQLiteTransportSessionRepository
from artwork_monitor.adapters.simulated import (
    SequenceGPSFixSource,
    SequenceSensorSource,
)
from artwork_monitor.application import (
    MonitoringService,
    SessionReportGenerator,
    TransportSessionWorkflow,
)
from artwork_monitor.domain import (
    GPSFix,
    GPSFixStatus,
    HONG_KONG,
    SensorReading,
)
from artwork_monitor.web import WebDependencies, create_app
from artwork_monitor.web.services import create_demo_dependencies


class RealtimeWebTests(unittest.TestCase):
    def _app(self, directory: Path):
        app = create_app(
            dependencies=create_demo_dependencies(directory / "web.sqlite3")
        )
        app.config.update(TESTING=True)
        return app

    def test_factory_initializes_socketio_without_starting_work(self) -> None:
        with TemporaryDirectory() as temporary:
            before = threading.active_count()
            app = self._app(Path(temporary))

            self.assertIn("socketio", app.extensions)
            self.assertEqual(threading.active_count(), before)
            self.assertFalse(
                app.extensions["artwork_monitor_dependencies"].artwork_workflow.checking
            )

    def test_connect_receives_current_snapshot_and_disconnects(self) -> None:
        with TemporaryDirectory() as temporary:
            app = self._app(Path(temporary))
            socket = app.extensions["socketio"].test_client(app)

            received = socket.get_received()

            self.assertTrue(socket.is_connected())
            self.assertEqual(received[0]["name"], "state_snapshot")
            self.assertEqual(
                received[0]["args"][0]["transport"]["state"], "not_started"
            )
            self.assertEqual(
                received[0]["args"][0]["capabilities"]["components"]["sensors"][
                    "state"
                ],
                "simulated",
            )
            socket.disconnect()
            self.assertFalse(socket.is_connected())

    def test_explicit_transport_actions_emit_ordered_session_scoped_events(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary:
            app = self._app(Path(temporary))
            http = app.test_client()
            socket = app.extensions["socketio"].test_client(app)
            socket.get_received()
            started_at = datetime(2026, 8, 9, 12, 0, tzinfo=HONG_KONG).isoformat()

            self.assertEqual(
                http.post(
                    "/transport/start",
                    json={"session_id": "rt-1", "started_at": started_at},
                ).status_code,
                201,
            )
            self.assertEqual(
                http.post("/transport/step", json={"monotonic_seconds": 0}).status_code,
                200,
            )
            self.assertEqual(
                http.post("/transport/stop", json={"ended_at": started_at}).status_code,
                200,
            )
            events = socket.get_received()

            self.assertEqual(
                [event["name"] for event in events],
                [
                    "transport_started",
                    "transport_cycle",
                    "gps_update",
                    "transport_completed",
                    "report_ready",
                ],
            )
            self.assertTrue(
                all(event["args"][0]["session_id"] == "rt-1" for event in events)
            )

    def test_violation_event_contains_existing_condition_data(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = SQLiteTransportSessionRepository(root / "violation.sqlite3")
            reading = SensorReading(
                timestamp=datetime(2026, 8, 9, 12, 0, tzinfo=HONG_KONG),
                temperature_c=27.1,
            )
            monitoring = MonitoringService(
                SequenceSensorSource((reading,)),
                gps_source=SequenceGPSFixSource((GPSFix.no_fix(reading.timestamp),)),
                session_repository=repository,
            )
            dependencies = WebDependencies(
                session_repository=repository,
                report_generator=SessionReportGenerator(),
                artwork_workflow=create_demo_dependencies(
                    root / "art.sqlite3"
                ).artwork_workflow,
                transport_workflow=TransportSessionWorkflow(monitoring, repository),
                runtime_capabilities=create_demo_dependencies(
                    root / "capabilities.sqlite3"
                ).runtime_capabilities,
            )
            app = create_app(dependencies=dependencies)
            socket = app.extensions["socketio"].test_client(app)
            socket.get_received()
            http = app.test_client()
            started_at = reading.timestamp.isoformat()
            http.post(
                "/transport/start", json={"session_id": "hot", "started_at": started_at}
            )
            http.post("/transport/step", json={"monotonic_seconds": 0})

            events = socket.get_received()
            violation = next(
                event["args"][0] for event in events if event["name"] == "violation"
            )
            self.assertEqual(violation["session_id"], "hot")
            self.assertEqual(violation["kind"], "immediate")
            self.assertEqual(violation["condition"], "temperature_high")

    def test_realtime_wall_clock_timestamps_are_normalized_to_hong_kong(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = SQLiteTransportSessionRepository(root / "timestamps.sqlite3")
            observed_at = datetime(2026, 8, 9, 4, 0, tzinfo=timezone.utc)
            monitoring = MonitoringService(
                SequenceSensorSource(
                    (SensorReading(timestamp=observed_at, temperature_c=27.1),)
                ),
                gps_source=SequenceGPSFixSource(
                    (GPSFix(observed_at, GPSFixStatus.FIX, 22.30, 114.17),)
                ),
                session_repository=repository,
            )
            demo = create_demo_dependencies(root / "web.sqlite3")
            app = create_app(
                dependencies=WebDependencies(
                    session_repository=repository,
                    report_generator=SessionReportGenerator(),
                    artwork_workflow=demo.artwork_workflow,
                    transport_workflow=TransportSessionWorkflow(monitoring, repository),
                    runtime_capabilities=demo.runtime_capabilities,
                )
            )
            socket = app.extensions["socketio"].test_client(app)
            socket.get_received()
            http = app.test_client()
            http.post(
                "/transport/start",
                json={
                    "session_id": "timestamps",
                    "started_at": observed_at.isoformat(),
                },
            )
            http.post("/transport/step", json={"monotonic_seconds": 0})

            payloads = {
                event["name"]: event["args"][0] for event in socket.get_received()
            }
            self.assertEqual(
                payloads["transport_cycle"]["reading"]["timestamp"],
                "2026-08-09T12:00:00+08:00",
            )
            self.assertEqual(
                payloads["gps_update"]["timestamp"], "2026-08-09T12:00:00+08:00"
            )
            self.assertEqual(
                payloads["violation"]["occurred_at"], "2026-08-09T12:00:00+08:00"
            )

    def test_artwork_transition_emits_status_change_only_after_legacy_cadence(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary:
            app = self._app(Path(temporary))
            socket = app.extensions["socketio"].test_client(app)
            socket.get_received()
            http = app.test_client()

            http.post("/check/start")
            for _ in range(5):
                http.post("/check/step")
            events = socket.get_received()

            self.assertEqual(
                [event["name"] for event in events],
                ["artwork_check_started", "artwork_status_changed"],
            )
            status = events[-1]["args"][0]
            self.assertEqual(status["transition"]["label_index"], 0)
            self.assertEqual(status["artworks"][0]["status"], "in")

    def test_separate_apps_do_not_share_realtime_state(self) -> None:
        with TemporaryDirectory() as temporary:
            first = self._app(Path(temporary) / "first")
            second = self._app(Path(temporary) / "second")
            first_socket = first.extensions["socketio"].test_client(first)
            second_socket = second.extensions["socketio"].test_client(second)
            first_socket.get_received()
            second_socket.get_received()

            first.test_client().post("/check/start")

            self.assertEqual(
                [event["name"] for event in first_socket.get_received()],
                ["artwork_check_started"],
            )
            self.assertEqual(second_socket.get_received(), [])
