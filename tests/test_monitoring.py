from datetime import datetime, timezone
import unittest

from artwork_monitor.adapters.simulated import SequenceGPSFixSource, SequenceSensorSource, run_simulated_session
from artwork_monitor.adapters.simulated import scenarios
from artwork_monitor.application import MonitoringService
from artwork_monitor.domain import Condition, GPSFixStatus, SensorReading
from artwork_monitor.ports import AlarmSource


TIMESTAMP = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def reading(**values: float | None) -> SensorReading:
    return SensorReading(timestamp=TIMESTAMP, **values)


class RecordingAlarmOutput:
    def __init__(self) -> None:
        self.calls: list[tuple[AlarmSource, bool]] = []

    def set_active(self, source: AlarmSource, active: bool) -> None:
        self.calls.append((source, active))

    def reset(self) -> None:
        raise AssertionError("MonitoringService must not globally reset an alarm output")


class MonitoringServiceTests(unittest.TestCase):
    def test_normal_session_is_filtered_deterministic_and_violation_free(self) -> None:
        first = run_simulated_session(scenarios.normal_transport(), (0.0, 2.0, 4.0))
        second = run_simulated_session(scenarios.normal_transport(), (0.0, 2.0, 4.0))

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0].immediate_violations, ())
        self.assertEqual(first[1].immediate_violations, ())
        self.assertAlmostEqual(first[1].reading.temperature_c, 22.02)
        self.assertAlmostEqual(first[1].reading.light_lux, 506.0)

    def test_temperature_immediate_and_prolonged_conditions_remain_distinct(self) -> None:
        service = MonitoringService(SequenceSensorSource(tuple(reading(temperature_c=27.1) for _ in range(4))))
        service.start()
        results = [service.step(time) for time in (0.0, 2.0, 4.0, 6.0)]

        assert all(result is not None for result in results)
        self.assertTrue(all(Condition.TEMPERATURE_HIGH in self._conditions(result.immediate_violations) for result in results))
        self.assertEqual(tuple(results[0].prolonged_violations), ())
        self.assertEqual(tuple(results[1].prolonged_violations), ())
        self.assertEqual(self._conditions(results[2].prolonged_violations), (Condition.TEMPERATURE_HIGH,))
        self.assertEqual(tuple(results[3].prolonged_violations), ())

    def test_multiple_immediate_violations_are_preserved(self) -> None:
        result = run_simulated_session(scenarios.multiple_environmental_violations(), (0.0,))[0]
        self.assertEqual(
            self._conditions(result.immediate_violations),
            (Condition.TEMPERATURE_LOW, Condition.HUMIDITY_HIGH, Condition.LIGHT_HIGH),
        )
        self.assertEqual(result.prolonged_violations, ())

    def test_missing_measurement_resets_prolonged_continuity(self) -> None:
        service = MonitoringService(
            SequenceSensorSource(
                (
                    reading(temperature_c=27.1),
                    reading(temperature_c=None),
                    reading(temperature_c=27.1),
                    reading(temperature_c=27.1),
                )
            )
        )
        service.start()
        results = [service.step(time) for time in (0.0, 2.0, 4.0, 8.0)]

        assert all(result is not None for result in results)
        self.assertIsNone(results[1].reading.temperature_c)
        self.assertEqual(results[1].immediate_violations, ())
        self.assertEqual(results[2].prolonged_violations, ())
        self.assertEqual(self._conditions(results[3].prolonged_violations), (Condition.TEMPERATURE_HIGH,))

    def test_darkness_does_not_suppress_acceleration_or_gravity_deviation(self) -> None:
        result = run_simulated_session(scenarios.dark_environment_with_acceleration(), (0.0,))[0]
        self.assertEqual(result.reading.light_lux, 0.0)
        self.assertEqual(result.reading.acceleration_z_g, 1.2)
        self.assertEqual(result.reading.gravity_deviation_g, 0.2)

    def test_gps_fixes_no_fix_and_exhaustion_do_not_block_monitoring(self) -> None:
        sensor_source = SequenceSensorSource(tuple(reading(temperature_c=22.0) for _ in range(4)))
        service = MonitoringService(sensor_source, gps_source=SequenceGPSFixSource(scenarios.gps_dropout().fixes))
        service.start()
        results = [service.step(time) for time in (0.0, 1.0, 2.0, 3.0)]

        assert all(result is not None for result in results)
        self.assertTrue(results[0].gps_fix.is_available)
        self.assertEqual(results[1].gps_fix.status, GPSFixStatus.NO_FIX)
        self.assertTrue(results[2].gps_fix.is_available)
        self.assertIsNone(results[3].gps_fix)
        self.assertTrue(all(result.immediate_violations == () for result in results))

    def test_new_session_resets_sources_filters_and_prolonged_state(self) -> None:
        source = SequenceSensorSource((reading(temperature_c=27.1), reading(temperature_c=30.0)))
        service = MonitoringService(source)
        service.start()
        first = service.step(0.0)
        second = service.step(2.0)
        service.stop()
        service.start()
        restarted = service.step(4.0)

        assert first is not None and second is not None and restarted is not None
        self.assertAlmostEqual(second.reading.temperature_c, 27.39)
        self.assertEqual(restarted.reading.temperature_c, 27.1)
        self.assertEqual(restarted.prolonged_violations, ())

    def test_temperature_humidity_and_light_violations_activate_transport_alarm(self) -> None:
        for values in (
            {"temperature_c": 17.9},
            {"humidity_percent_rh": 75.1},
            {"light_lux": 6000.1},
        ):
            with self.subTest(values=values):
                alarm = RecordingAlarmOutput()
                service = MonitoringService(SequenceSensorSource((reading(**values),)), alarm_output=alarm)
                service.start()
                service.step(0.0)
                self.assertEqual(alarm.calls, [(AlarmSource.TRANSPORT_MONITORING, False), (AlarmSource.TRANSPORT_MONITORING, True)])

    def test_excessive_but_not_moderate_gravity_deviation_activates_transport_alarm(self) -> None:
        for value, expected in ((20.0, True), (15.0, False)):
            with self.subTest(value=value):
                alarm = RecordingAlarmOutput()
                service = MonitoringService(SequenceSensorSource((reading(gravity_deviation_g=value),)), alarm_output=alarm)
                service.start()
                service.step(0.0)
                self.assertEqual(alarm.calls[-1], (AlarmSource.TRANSPORT_MONITORING, expected))

    def test_normal_and_unavailable_cycles_clear_transport_alarm(self) -> None:
        alarm = RecordingAlarmOutput()
        service = MonitoringService(
            SequenceSensorSource((reading(temperature_c=27.1), reading(temperature_c=22.0), reading(temperature_c=None))),
            alarm_output=alarm,
        )
        service.start()
        service.step(0.0)
        service.step(1.0)
        service.step(2.0)

        self.assertEqual(alarm.calls[-3:], [(AlarmSource.TRANSPORT_MONITORING, True), (AlarmSource.TRANSPORT_MONITORING, False), (AlarmSource.TRANSPORT_MONITORING, False)])

    def test_start_and_stop_clear_only_transport_alarm_source(self) -> None:
        alarm = RecordingAlarmOutput()
        service = MonitoringService(SequenceSensorSource((reading(temperature_c=22.0),)), alarm_output=alarm)

        service.start()
        service.stop()

        self.assertEqual(alarm.calls, [(AlarmSource.TRANSPORT_MONITORING, False), (AlarmSource.TRANSPORT_MONITORING, False)])

    def _conditions(self, violations: tuple) -> tuple[Condition, ...]:
        return tuple(violation.condition for violation in violations)
