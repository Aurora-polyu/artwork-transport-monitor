from datetime import datetime, timezone
import unittest

from artwork_monitor.application import ProlongedConditionTracker
from artwork_monitor.domain import Condition, SensorReading, evaluate_reading


TIMESTAMP = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def reading(**values: float | None) -> SensorReading:
    return SensorReading(timestamp=TIMESTAMP, **values)


def observe(
    tracker: ProlongedConditionTracker,
    elapsed: float,
    **values: float | None,
) -> tuple[Condition, ...]:
    observation = reading(**values)
    return tuple(
        violation.condition
        for violation in tracker.observe(
            observation, evaluate_reading(observation), elapsed
        )
    )


class ProlongedConditionTrackerTests(unittest.TestCase):
    def test_alert_transitions_once_at_four_continuous_seconds(self) -> None:
        tracker = ProlongedConditionTracker()
        self.assertEqual(observe(tracker, 0.0, temperature_c=17.9), ())
        self.assertEqual(observe(tracker, 2.0, temperature_c=17.9), ())
        self.assertEqual(observe(tracker, 3.9, temperature_c=17.9), ())
        self.assertEqual(
            observe(tracker, 4.0, temperature_c=17.9), (Condition.TEMPERATURE_LOW,)
        )
        self.assertEqual(observe(tracker, 6.0, temperature_c=17.9), ())

    def test_recovery_allows_a_later_episode_to_alert(self) -> None:
        tracker = ProlongedConditionTracker()
        observe(tracker, 0.0, humidity_percent_rh=75.1)
        self.assertEqual(
            observe(tracker, 4.0, humidity_percent_rh=75.1), (Condition.HUMIDITY_HIGH,)
        )
        self.assertEqual(observe(tracker, 5.0, humidity_percent_rh=75.0), ())
        self.assertEqual(observe(tracker, 6.0, humidity_percent_rh=75.1), ())
        self.assertEqual(
            observe(tracker, 10.0, humidity_percent_rh=75.1), (Condition.HUMIDITY_HIGH,)
        )

    def test_missing_measurement_breaks_continuity(self) -> None:
        tracker = ProlongedConditionTracker()
        observe(tracker, 0.0, light_lux=6000.1)
        self.assertEqual(observe(tracker, 3.0, light_lux=None), ())
        self.assertEqual(observe(tracker, 4.0, light_lux=6000.1), ())
        self.assertEqual(
            observe(tracker, 8.0, light_lux=6000.1), (Condition.LIGHT_HIGH,)
        )

    def test_conditions_progress_independently(self) -> None:
        tracker = ProlongedConditionTracker()
        observe(tracker, 0.0, temperature_c=17.9, humidity_percent_rh=75.1)
        self.assertEqual(
            observe(tracker, 4.0, temperature_c=17.9, humidity_percent_rh=75.1),
            (Condition.TEMPERATURE_LOW, Condition.HUMIDITY_HIGH),
        )
        self.assertEqual(
            observe(tracker, 5.0, temperature_c=18.0, humidity_percent_rh=75.1), ()
        )
        self.assertEqual(
            observe(tracker, 6.0, temperature_c=17.9, humidity_percent_rh=75.1), ()
        )
        self.assertEqual(
            observe(tracker, 10.0, temperature_c=17.9, humidity_percent_rh=75.1),
            (Condition.TEMPERATURE_LOW,),
        )

    def test_session_reset_clears_all_active_episodes(self) -> None:
        tracker = ProlongedConditionTracker()
        observe(tracker, 0.0, temperature_c=17.9, light_lux=6000.1)
        tracker.reset()
        self.assertEqual(
            observe(tracker, 4.0, temperature_c=17.9, light_lux=6000.1), ()
        )
        self.assertEqual(
            observe(tracker, 8.0, temperature_c=17.9, light_lux=6000.1),
            (Condition.TEMPERATURE_LOW, Condition.LIGHT_HIGH),
        )

    def test_motion_violation_is_not_part_of_prolonged_environmental_tracking(
        self,
    ) -> None:
        tracker = ProlongedConditionTracker()
        self.assertEqual(observe(tracker, 0.0, gravity_deviation_g=20.0), ())
        self.assertEqual(observe(tracker, 4.0, gravity_deviation_g=20.0), ())
