import sys
import subprocess
import unittest
from pathlib import Path

from artwork_monitor.adapters.simulated import SequenceGPSFixSource, SequenceSensorSource
from artwork_monitor.adapters.simulated import scenarios
from artwork_monitor.domain import GPSFixStatus
from artwork_monitor.ports import GPSFixSource, SensorSource


class SimulatedSensorSourceTests(unittest.TestCase):
    def test_sequence_order_exhaustion_and_reset_are_deterministic(self) -> None:
        scenario = scenarios.normal_transport()
        source: SensorSource = SequenceSensorSource(scenario.readings)

        self.assertEqual(source.next_reading(), scenario.readings[0])
        self.assertEqual(source.next_reading(), scenario.readings[1])
        self.assertIsNone(source.next_reading())
        self.assertIsNone(source.next_reading())
        source.reset()
        self.assertEqual(source.next_reading(), scenario.readings[0])

    def test_missing_measurements_are_preserved(self) -> None:
        source = SequenceSensorSource(scenarios.missing_sensor_reading().readings)
        reading = source.next_reading()

        assert reading is not None
        self.assertIsNone(reading.temperature_c)
        self.assertIsNone(reading.humidity_percent_rh)
        self.assertIsNone(reading.light_lux)

    def test_scenarios_contain_intended_normal_and_abnormal_values(self) -> None:
        self.assertEqual(scenarios.normal_transport().readings[0].temperature_c, 22.0)
        self.assertEqual(scenarios.excessive_temperature().readings[0].temperature_c, 27.1)
        self.assertEqual(scenarios.high_humidity().readings[0].humidity_percent_rh, 75.1)
        self.assertEqual(scenarios.excessive_light().readings[0].light_lux, 6000.1)
        self.assertEqual(scenarios.gravity_deviation_example().readings[0].gravity_deviation_g, 0.2)
        multiple = scenarios.multiple_environmental_violations().readings[0]
        self.assertEqual((multiple.temperature_c, multiple.humidity_percent_rh, multiple.light_lux), (17.9, 75.1, 6000.1))

    def test_dark_scenario_keeps_acceleration_and_gravity_deviation(self) -> None:
        reading = scenarios.dark_environment_with_acceleration().readings[0]
        self.assertEqual(reading.light_lux, 0.0)
        self.assertEqual(reading.acceleration_z_g, 1.2)
        self.assertEqual(reading.gravity_deviation_g, 0.2)


class SimulatedGPSFixSourceTests(unittest.TestCase):
    def test_route_sequence_exhaustion_and_reset_are_deterministic(self) -> None:
        scenario = scenarios.gps_route()
        source: GPSFixSource = SequenceGPSFixSource(scenario.fixes)

        self.assertEqual(source.next_fix(), scenario.fixes[0])
        self.assertEqual(source.next_fix(), scenario.fixes[1])
        self.assertEqual(source.next_fix(), scenario.fixes[2])
        self.assertIsNone(source.next_fix())
        source.reset()
        self.assertEqual(source.next_fix(), scenario.fixes[0])

    def test_no_fix_is_explicit_data_not_source_exhaustion(self) -> None:
        source = SequenceGPSFixSource(scenarios.gps_dropout().fixes)
        first = source.next_fix()
        unavailable = source.next_fix()
        final = source.next_fix()

        assert first is not None and unavailable is not None and final is not None
        self.assertTrue(first.is_available)
        self.assertEqual(unavailable.status, GPSFixStatus.NO_FIX)
        self.assertFalse(unavailable.is_available)
        self.assertIsNone(unavailable.latitude)
        self.assertIsNone(unavailable.longitude)
        self.assertTrue(final.is_available)
        self.assertIsNone(source.next_fix())

    def test_simulated_modules_have_no_runtime_side_effect_dependencies(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import artwork_monitor.adapters.simulated; "
                "forbidden = {'RPi', 'smbus2', 'serial', 'pynmea2', 'cv2', 'flask', 'socket', 'sqlite3'}; "
                "assert not forbidden.intersection(sys.modules)",
            ],
            cwd=project_root,
            env={"PYTHONPATH": str(project_root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
