import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from artwork_monitor.adapters.notifications import InMemoryNotificationDispatcher
from artwork_monitor.adapters.simulated import SequenceSensorSource
from artwork_monitor.application import MonitoringService
from artwork_monitor.domain import NotificationKind, SensorReading, TransportSession


TIMESTAMP = datetime(2026, 8, 8, 4, 0, tzinfo=timezone.utc)


def reading(**values: float | None) -> SensorReading:
    return SensorReading(timestamp=TIMESTAMP, **values)


class NotificationWorkflowTests(unittest.TestCase):
    def test_normal_session_produces_no_notification(self) -> None:
        dispatcher = InMemoryNotificationDispatcher()
        service = self._service(
            dispatcher,
            (reading(temperature_c=22.0, humidity_percent_rh=50.0, light_lux=500.0),),
        )

        service.start(TransportSession("normal", TIMESTAMP))
        service.step(0.0)

        self.assertEqual(dispatcher.messages, [])

    def test_immediate_violation_dispatches_a_canonical_message(self) -> None:
        dispatcher = InMemoryNotificationDispatcher()
        service = self._service(dispatcher, (reading(temperature_c=27.1),))

        service.start(TransportSession("immediate", TIMESTAMP))
        service.step(0.0)

        self.assertEqual(len(dispatcher.messages), 1)
        message = dispatcher.messages[0]
        self.assertEqual(message.session_id, "immediate")
        self.assertEqual(message.kind, NotificationKind.IMMEDIATE)
        self.assertEqual(message.condition, "temperature_high")
        self.assertIn("observed 27.1", message.summary)
        self.assertEqual(message.occurred_at, "2026-08-08T12:00:00+08:00")

    def test_prolonged_violation_dispatches_once_after_four_seconds(self) -> None:
        dispatcher = InMemoryNotificationDispatcher()
        service = self._service(
            dispatcher, tuple(reading(temperature_c=27.1) for _ in range(4))
        )

        service.start(TransportSession("prolonged", TIMESTAMP))
        for monotonic_seconds in (0.0, 2.0, 4.0, 6.0):
            service.step(monotonic_seconds)

        immediate = [
            message
            for message in dispatcher.messages
            if message.kind is NotificationKind.IMMEDIATE
        ]
        prolonged = [
            message
            for message in dispatcher.messages
            if message.kind is NotificationKind.PROLONGED
        ]
        self.assertEqual(len(immediate), 4)
        self.assertEqual(len(prolonged), 1)
        self.assertEqual(prolonged[0].condition, "temperature_high")
        self.assertEqual(dispatcher.messages[2].kind, NotificationKind.IMMEDIATE)
        self.assertEqual(dispatcher.messages[3].kind, NotificationKind.PROLONGED)

    def test_simultaneous_conditions_keep_deterministic_order(self) -> None:
        dispatcher = InMemoryNotificationDispatcher()
        service = self._service(
            dispatcher,
            (reading(temperature_c=17.9, humidity_percent_rh=75.1, light_lux=6000.1),),
        )

        service.start(TransportSession("multiple", TIMESTAMP))
        service.step(0.0)

        self.assertEqual(
            [(message.kind, message.condition) for message in dispatcher.messages],
            [
                (NotificationKind.IMMEDIATE, "temperature_low"),
                (NotificationKind.IMMEDIATE, "humidity_high"),
                (NotificationKind.IMMEDIATE, "light_high"),
            ],
        )

    def test_missing_reading_creates_no_invented_notification(self) -> None:
        dispatcher = InMemoryNotificationDispatcher()
        service = self._service(
            dispatcher,
            (reading(temperature_c=None, humidity_percent_rh=None, light_lux=None),),
        )

        service.start(TransportSession("missing", TIMESTAMP))
        service.step(0.0)

        self.assertEqual(dispatcher.messages, [])

    def test_session_reset_prevents_prolonged_notification_state_leakage(self) -> None:
        dispatcher = InMemoryNotificationDispatcher()
        service = self._service(
            dispatcher, (reading(temperature_c=27.1), reading(temperature_c=27.1))
        )

        service.start(TransportSession("first", TIMESTAMP))
        service.step(0.0)
        service.step(4.0)
        service.stop()
        service.start(TransportSession("second", TIMESTAMP))
        service.step(0.0)

        prolonged = [
            message
            for message in dispatcher.messages
            if message.kind is NotificationKind.PROLONGED
        ]
        self.assertEqual([message.session_id for message in prolonged], ["first"])
        self.assertEqual(dispatcher.messages[-1].session_id, "second")
        self.assertEqual(dispatcher.messages[-1].kind, NotificationKind.IMMEDIATE)

    def test_notification_modules_do_not_import_smtp_or_network_clients(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import builtins, threading\n"
                "attempted = []\n"
                "forbidden = ('smtplib', 'socket', 'requests', 'urllib.request')\n"
                "original_import = builtins.__import__\n"
                "def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):\n"
                "    imported_names = (name, *(f'{name}.{item}' for item in (fromlist or ())))\n"
                "    if any(candidate in forbidden or candidate.startswith(('requests.', 'urllib.request.')) for candidate in imported_names):\n"
                "        attempted.append(name)\n"
                "    return original_import(name, globals, locals, fromlist, level)\n"
                "before_threads = set(threading.enumerate())\n"
                "builtins.__import__ = guarded_import\n"
                "try:\n"
                "    import artwork_monitor.adapters.notifications\n"
                "    import artwork_monitor.application.notifications\n"
                "finally:\n"
                "    builtins.__import__ = original_import\n"
                "assert not attempted, attempted\n"
                "assert set(threading.enumerate()) == before_threads\n",
            ],
            cwd=project_root,
            env={"PYTHONPATH": str(project_root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @staticmethod
    def _service(
        dispatcher: InMemoryNotificationDispatcher,
        readings: tuple[SensorReading, ...],
    ) -> MonitoringService:
        return MonitoringService(
            SequenceSensorSource(readings), notification_dispatcher=dispatcher
        )
