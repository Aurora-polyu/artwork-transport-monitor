from datetime import datetime, timezone
import unittest

from artwork_monitor.domain import (
    Condition,
    SensorReading,
    calculate_gravity_deviation,
    evaluate_reading,
)


TIMESTAMP = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def reading(**values: float | None) -> SensorReading:
    return SensorReading(timestamp=TIMESTAMP, **values)


class EnvironmentalThresholdTests(unittest.TestCase):
    def test_temperature_boundaries_are_normal_and_outside_values_violate(self) -> None:
        self.assertEqual(
            self._conditions(temperature_c=17.9), (Condition.TEMPERATURE_LOW,)
        )
        self.assertEqual(self._conditions(temperature_c=18.0), ())
        self.assertEqual(self._conditions(temperature_c=27.0), ())
        self.assertEqual(
            self._conditions(temperature_c=27.1), (Condition.TEMPERATURE_HIGH,)
        )

    def test_humidity_boundaries_are_normal_and_outside_values_violate(self) -> None:
        self.assertEqual(
            self._conditions(humidity_percent_rh=24.9), (Condition.HUMIDITY_LOW,)
        )
        self.assertEqual(self._conditions(humidity_percent_rh=25.0), ())
        self.assertEqual(self._conditions(humidity_percent_rh=75.0), ())
        self.assertEqual(
            self._conditions(humidity_percent_rh=75.1), (Condition.HUMIDITY_HIGH,)
        )

    def test_light_maximum_is_strict(self) -> None:
        self.assertEqual(self._conditions(light_lux=6000.0), ())
        self.assertEqual(self._conditions(light_lux=6000.1), (Condition.LIGHT_HIGH,))

    def test_missing_values_are_not_environmental_violations(self) -> None:
        self.assertEqual(evaluate_reading(reading()), ())
        self.assertEqual(
            evaluate_reading(
                reading(temperature_c=None, humidity_percent_rh=None, light_lux=None)
            ),
            (),
        )

    def test_multiple_conditions_are_retained(self) -> None:
        violations = evaluate_reading(
            reading(temperature_c=17.9, humidity_percent_rh=75.1, light_lux=6000.1)
        )
        self.assertEqual(
            tuple(violation.condition for violation in violations),
            (Condition.TEMPERATURE_LOW, Condition.HUMIDITY_HIGH, Condition.LIGHT_HIGH),
        )
        self.assertTrue(
            all(violation.occurred_at == TIMESTAMP for violation in violations)
        )

    def _conditions(self, **values: float) -> tuple[Condition, ...]:
        return tuple(
            violation.condition for violation in evaluate_reading(reading(**values))
        )


class MotionTests(unittest.TestCase):
    def test_gravity_deviation_is_magnitude_deviation_from_one_g(self) -> None:
        self.assertEqual(calculate_gravity_deviation(0.0, 0.0, 1.0), 0.0)
        self.assertAlmostEqual(calculate_gravity_deviation(0.0, 0.0, 1.2), 0.2)
        self.assertAlmostEqual(calculate_gravity_deviation(1.0, 1.0, 1.0), 3**0.5 - 1.0)
        self.assertIsNone(calculate_gravity_deviation(None, 0.0, 1.0))

    def test_light_does_not_change_acceleration_derived_motion(self) -> None:
        dark = SensorReading.with_calculated_gravity_deviation(
            timestamp=TIMESTAMP,
            acceleration_x_g=0.0,
            acceleration_y_g=0.0,
            acceleration_z_g=1.2,
            light_lux=0.0,
        )
        bright = SensorReading.with_calculated_gravity_deviation(
            timestamp=TIMESTAMP,
            acceleration_x_g=0.0,
            acceleration_y_g=0.0,
            acceleration_z_g=1.2,
            light_lux=6001.0,
        )

        self.assertAlmostEqual(dark.gravity_deviation_g, 0.2)
        self.assertEqual(dark.gravity_deviation_g, bright.gravity_deviation_g)
        self.assertEqual(dark.acceleration_z_g, bright.acceleration_z_g)

    def test_provisional_motion_thresholds_are_structured(self) -> None:
        moderate = evaluate_reading(reading(gravity_deviation_g=15.0))
        excessive = evaluate_reading(reading(gravity_deviation_g=20.0))

        self.assertEqual(moderate[0].condition, Condition.GRAVITY_DEVIATION_MODERATE)
        self.assertEqual(excessive[0].condition, Condition.GRAVITY_DEVIATION_EXCESSIVE)
