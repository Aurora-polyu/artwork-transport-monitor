import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from artwork_monitor.adapters.notifications import InMemoryNotificationDispatcher
from artwork_monitor.adapters.persistence import CsvTransportSessionExporter, SQLiteTransportSessionRepository
from artwork_monitor.adapters.simulated import SequenceGPSFixSource, SequenceSensorSource
from artwork_monitor.adapters.simulated import scenarios
from artwork_monitor.application import (
    MonitoringService,
    SessionReportGenerator,
    TransportSessionState,
    TransportSessionWorkflow,
    render_markdown,
)
from artwork_monitor.domain import NotificationKind, SensorReading, TransportSession


START = datetime(2026, 8, 8, 4, 0, tzinfo=timezone.utc)


def reading(offset: int, **values: float | None) -> SensorReading:
    return SensorReading(timestamp=START + timedelta(seconds=offset), **values)


class TransportSessionWorkflowTests(unittest.TestCase):
    def test_complete_normal_session_persists_exports_and_reports(self) -> None:
        with self._workflow((reading(0, temperature_c=22.0, humidity_percent_rh=50.0, light_lux=500.0), reading(2, temperature_c=22.2, humidity_percent_rh=50.5, light_lux=520.0))) as context:
            workflow, dispatcher, _repository = context
            workflow.start(TransportSession("normal", START))
            cycles = workflow.run((0.0, 2.0))
            outcome = workflow.complete(START + timedelta(seconds=4))

            self.assertEqual(workflow.state, TransportSessionState.COMPLETED)
            self.assertEqual(len(cycles), 2)
            self.assertTrue(outcome.csv_path.is_file())
            self.assertEqual(outcome.stored_session.session.session_id, "normal")
            self.assertEqual(outcome.report.monitoring_cycle_count, 2)
            self.assertEqual(dispatcher.messages, [])
            self.assertEqual(outcome.report, SessionReportGenerator().generate(outcome.stored_session))
            self.assertEqual(render_markdown(outcome.report), render_markdown(outcome.report))

    def test_abnormal_session_preserves_immediate_and_one_shot_prolonged_notifications(self) -> None:
        readings = tuple(reading(offset, temperature_c=27.1) for offset in (0, 2, 4, 6))
        with self._workflow(readings) as context:
            workflow, dispatcher, _repository = context
            workflow.start(TransportSession("abnormal", START))
            outcome = self._run_and_complete(workflow, (0.0, 2.0, 4.0, 6.0))

            immediate = [message for message in dispatcher.messages if message.kind is NotificationKind.IMMEDIATE]
            prolonged = [message for message in dispatcher.messages if message.kind is NotificationKind.PROLONGED]
            self.assertEqual(len(immediate), 4)
            self.assertEqual(len(prolonged), 1)
            self.assertEqual(len(outcome.report.immediate_violations), 4)
            self.assertEqual(len(outcome.report.prolonged_violations), 1)
            self.assertEqual(prolonged[0].session_id, "abnormal")

    def test_simultaneous_conditions_and_missing_data_flow_end_to_end(self) -> None:
        readings = (
            reading(0, temperature_c=17.9, humidity_percent_rh=75.1, light_lux=6000.1),
            reading(2, temperature_c=None, humidity_percent_rh=None, light_lux=None),
        )
        with self._workflow(readings) as context:
            workflow, dispatcher, _repository = context
            workflow.start(TransportSession("mixed", START))
            outcome = self._run_and_complete(workflow, (0.0, 2.0))

            self.assertEqual([message.condition for message in dispatcher.messages], ["temperature_low", "humidity_high", "light_high"])
            self.assertEqual(outcome.report.temperature.valid_count, 1)
            self.assertEqual(outcome.report.temperature.missing_count, 1)
            self.assertEqual(outcome.report.prolonged_violations, ())

    def test_gps_dropout_is_preserved_through_persistence_and_report_reload(self) -> None:
        readings = tuple(reading(offset, temperature_c=22.0) for offset in (0, 1, 2))
        with self._workflow(readings, gps_source=SequenceGPSFixSource(scenarios.gps_dropout().fixes)) as context:
            workflow, _dispatcher, repository = context
            workflow.start(TransportSession("gps", START))
            outcome = self._run_and_complete(workflow, (0.0, 1.0, 2.0))
            reloaded = repository.load_session("gps")

            self.assertEqual(outcome.stored_session, reloaded)
            self.assertEqual((outcome.report.gps.available_fix_count, outcome.report.gps.no_fix_count, outcome.report.gps.missing_fix_count), (2, 1, 0))

    def test_two_consecutive_sessions_do_not_leak_state(self) -> None:
        readings = (reading(0, temperature_c=27.1), reading(4, temperature_c=27.1))
        with self._workflow(readings) as context:
            workflow, dispatcher, _repository = context
            workflow.start(TransportSession("first", START))
            first = self._run_and_complete(workflow, (0.0, 4.0))
            workflow.start(TransportSession("second", START + timedelta(minutes=1)))
            second = self._run_and_complete(workflow, (0.0,), ended_at=START + timedelta(minutes=1, seconds=8))

            prolonged = [message for message in dispatcher.messages if message.kind is NotificationKind.PROLONGED]
            self.assertEqual(len(first.report.prolonged_violations), 1)
            self.assertEqual(second.report.prolonged_violations, ())
            self.assertEqual([message.session_id for message in prolonged], ["first"])
            self.assertEqual(second.stored_session.records[0].sequence, 0)

    def test_invalid_lifecycle_operations_are_explicit(self) -> None:
        with self._workflow((reading(0, temperature_c=22.0),)) as context:
            workflow, _dispatcher, _repository = context
            with self.assertRaises(RuntimeError):
                workflow.step(0.0)
            with self.assertRaises(RuntimeError):
                workflow.complete(START)
            workflow.start(TransportSession("running", START))
            self.assertEqual(workflow.state, TransportSessionState.RUNNING)
            with self.assertRaises(RuntimeError):
                workflow.start(TransportSession("other", START))
            self._run_and_complete(workflow, (0.0,))
            with self.assertRaises(RuntimeError):
                workflow.step(1.0)

    def _workflow(
        self,
        readings: tuple[SensorReading, ...],
        *,
        gps_source: SequenceGPSFixSource | None = None,
    ):
        temporary_directory = tempfile.TemporaryDirectory()
        root = Path(temporary_directory.name)
        repository = SQLiteTransportSessionRepository(root / "transport.sqlite3")
        dispatcher = InMemoryNotificationDispatcher()
        service = MonitoringService(
            SequenceSensorSource(readings),
            gps_source=gps_source,
            session_repository=repository,
            notification_dispatcher=dispatcher,
        )
        workflow = TransportSessionWorkflow(
            service,
            repository,
            csv_exporter=CsvTransportSessionExporter(root / "csv"),
        )
        return _WorkflowContext(temporary_directory, workflow, dispatcher, repository)

    @staticmethod
    def _run_and_complete(
        workflow: TransportSessionWorkflow,
        times: tuple[float, ...],
        *,
        ended_at: datetime = START + timedelta(seconds=8),
    ):
        workflow.run(times)
        return workflow.complete(ended_at)


class _WorkflowContext:
    def __init__(self, temporary_directory, workflow, dispatcher, repository) -> None:
        self._temporary_directory = temporary_directory
        self.workflow = workflow
        self.dispatcher = dispatcher
        self.repository = repository

    def __enter__(self):
        return self.workflow, self.dispatcher, self.repository

    def __exit__(self, exception_type, exception, traceback) -> None:
        self._temporary_directory.cleanup()
