import unittest

from artwork_monitor.application import EnvironmentalFilters, EwmaFilter, clean_gravity_deviation


class EwmaFilterTests(unittest.TestCase):
    def test_first_value_and_alpha_point_one_updates(self) -> None:
        filter_ = EwmaFilter(alpha=0.1)
        self.assertEqual(filter_.update(10.0), 10.0)
        self.assertAlmostEqual(filter_.update(20.0), 11.0)
        self.assertAlmostEqual(filter_.update(20.0), 11.9)

    def test_alpha_point_three_updates(self) -> None:
        filter_ = EwmaFilter(alpha=0.3)
        self.assertEqual(filter_.update(10.0), 10.0)
        self.assertAlmostEqual(filter_.update(20.0), 13.0)

    def test_none_preserves_state_and_later_valid_value_recovers(self) -> None:
        filter_ = EwmaFilter(alpha=0.1)
        filter_.update(10.0)
        self.assertIsNone(filter_.update(None))
        self.assertAlmostEqual(filter_.update(20.0), 11.0)

    def test_reset_forgets_previous_value(self) -> None:
        filter_ = EwmaFilter(alpha=0.1)
        filter_.update(10.0)
        filter_.reset()
        self.assertEqual(filter_.update(20.0), 20.0)

    def test_environmental_filters_use_legacy_alphas(self) -> None:
        filters = EnvironmentalFilters()
        self.assertEqual(filters.temperature.update(10.0), 10.0)
        self.assertAlmostEqual(filters.temperature.update(20.0), 11.0)
        self.assertEqual(filters.humidity.update(10.0), 10.0)
        self.assertAlmostEqual(filters.humidity.update(20.0), 11.0)
        self.assertEqual(filters.light.update(10.0), 10.0)
        self.assertAlmostEqual(filters.light.update(20.0), 13.0)


class GravityDeviationCleanupTests(unittest.TestCase):
    def test_legacy_cutoff(self) -> None:
        self.assertEqual(clean_gravity_deviation(0.019), 0.0)
        self.assertEqual(clean_gravity_deviation(0.02), 0.02)
        self.assertEqual(clean_gravity_deviation(0.5), 0.5)
        self.assertIsNone(clean_gravity_deviation(None))

    def test_cleanup_has_no_light_input_or_dependency(self) -> None:
        self.assertEqual(clean_gravity_deviation(0.019), 0.0)
        self.assertEqual(clean_gravity_deviation(0.02), 0.02)
