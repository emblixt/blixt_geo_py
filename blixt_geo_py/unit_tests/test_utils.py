"""
Tests of the functions in utils/utils.py
"""
import unittest

import numpy as np

from blixt_geo_py.utils.utils import find_value


class FindValueTests(unittest.TestCase):
    x = np.array([0, 1, 3, 1, -1, -2, -1, 0, 2, 5, 2, -3, 0], dtype=float)
    # Local maxima at index 2 (value 3) and 9 (value 5)
    # Local minima at index 5 (value -2) and 11 (value -3)

    def assert_finds(self, x_index, snap_to, expected_index):
        value, index = find_value(self.x, x_index, snap_to=snap_to)
        self.assertEqual(index, expected_index)
        self.assertEqual(value, self.x[expected_index])

    def test_exact(self):
        # Returns the given position, whether or not it is a local extreme
        for x_index in [0, 3, 5, 9, 12]:
            self.assert_finds(x_index, 'exact', x_index)

    def test_exact_is_the_default(self):
        self.assertEqual(find_value(self.x, 3), (self.x[3], 3))

    def test_nearest_min(self):
        self.assert_finds(0, 'nearest_min', 5)
        self.assert_finds(7, 'nearest_min', 5)  # 2 samples from index 5, 4 from index 11
        self.assert_finds(9, 'nearest_min', 11)  # 4 samples from index 5, 2 from index 11
        self.assert_finds(12, 'nearest_min', 11)

    def test_nearest_min_on_a_minimum(self):
        self.assert_finds(5, 'nearest_min', 5)
        self.assert_finds(11, 'nearest_min', 11)

    def test_nearest_max(self):
        self.assert_finds(0, 'nearest_max', 2)
        self.assert_finds(5, 'nearest_max', 2)  # 3 samples from index 2, 4 from index 9
        self.assert_finds(6, 'nearest_max', 9)  # 4 samples from index 2, 3 from index 9
        self.assert_finds(12, 'nearest_max', 9)

    def test_nearest_max_on_a_maximum(self):
        self.assert_finds(2, 'nearest_max', 2)
        self.assert_finds(9, 'nearest_max', 9)

    def test_nearest_extreme(self):
        self.assert_finds(3, 'nearest_extreme', 2)  # 1 sample from the maximum, 2 from the minimum
        self.assert_finds(4, 'nearest_extreme', 5)  # 2 samples from the maximum, 1 from the minimum
        self.assert_finds(8, 'nearest_extreme', 9)  # 1 sample from the maximum, 3 from the minimum
        self.assert_finds(10, 'nearest_extreme', 9)  # Equally far, see the test below
        self.assert_finds(12, 'nearest_extreme', 11)  # 3 samples from the maximum, 1 from the minimum

    def test_nearest_extreme_on_an_extreme(self):
        for x_index in [2, 5, 9, 11]:
            self.assert_finds(x_index, 'nearest_extreme', x_index)

    def test_nearest_extreme_prefers_the_maximum_when_equally_far(self):
        # Index 7 is 2 samples from the minimum at index 5 and 2 samples from the maximum at index 9
        self.assert_finds(7, 'nearest_extreme', 9)

    def test_unknown_snap_to(self):
        with self.assertRaises(IOError):
            find_value(self.x, 3, snap_to='nearest_something')

    def test_no_extreme_of_the_requested_type(self):
        monotonic = np.arange(5.)
        for snap_to in ['nearest_min', 'nearest_max', 'nearest_extreme']:
            with self.assertRaisesRegex(ValueError, snap_to):
                find_value(monotonic, 1, snap_to=snap_to)

        only_a_minimum = np.array([2., 1., 0., 1., 2.])
        with self.assertRaisesRegex(ValueError, 'nearest_max'):
            find_value(only_a_minimum, 1, snap_to='nearest_max')

        only_a_maximum = np.array([0., 1., 2., 1., 0.])
        with self.assertRaisesRegex(ValueError, 'nearest_min'):
            find_value(only_a_maximum, 1, snap_to='nearest_min')

    def test_nearest_extreme_with_only_one_type_of_extreme(self):
        only_a_minimum = np.array([2., 1., 0., 1., 2.])
        self.assertEqual(find_value(only_a_minimum, 0, snap_to='nearest_extreme'), (0., 2))

        only_a_maximum = np.array([0., 1., 2., 1., 0.])
        self.assertEqual(find_value(only_a_maximum, 4, snap_to='nearest_extreme'), (2., 2))

    def test_flat_top_with_odd_number_of_samples_returns_the_middle_index(self):
        x = np.array([0., 1., 2., 2., 2., 1., 0.])  # Flat top at index 2, 3 and 4
        for x_index in range(len(x)):
            self.assertEqual(find_value(x, x_index, snap_to='nearest_max'), (2., 3))
            self.assertEqual(find_value(x, x_index, snap_to='nearest_extreme'), (2., 3))

    def test_flat_top_with_even_number_of_samples_returns_the_lower_middle_index(self):
        x = np.array([0., 1., 2., 2., 2., 2., 1., 0.])  # Flat top at index 2, 3, 4 and 5
        for x_index in range(len(x)):
            self.assertEqual(find_value(x, x_index, snap_to='nearest_max'), (2., 3))
            self.assertEqual(find_value(x, x_index, snap_to='nearest_extreme'), (2., 3))

    def test_flat_bottom_with_odd_number_of_samples_returns_the_middle_index(self):
        x = -np.array([0., 1., 2., 2., 2., 1., 0.])
        for x_index in range(len(x)):
            self.assertEqual(find_value(x, x_index, snap_to='nearest_min'), (-2., 3))
            self.assertEqual(find_value(x, x_index, snap_to='nearest_extreme'), (-2., 3))

    def test_flat_bottom_with_even_number_of_samples_returns_the_lower_middle_index(self):
        x = -np.array([0., 1., 2., 2., 2., 2., 1., 0.])
        for x_index in range(len(x)):
            self.assertEqual(find_value(x, x_index, snap_to='nearest_min'), (-2., 3))
            self.assertEqual(find_value(x, x_index, snap_to='nearest_extreme'), (-2., 3))

    def test_flat_section_on_a_slope_is_not_an_extreme(self):
        x = np.array([0., 1., 1., 2., 3.])
        with self.assertRaises(ValueError):
            find_value(x, 1, snap_to='nearest_extreme')

    def test_flat_section_at_the_end_of_the_data_is_not_an_extreme(self):
        x = np.array([0., 1., 2., 2.])
        with self.assertRaises(ValueError):
            find_value(x, 1, snap_to='nearest_max')


if __name__ == '__main__':
    unittest.main()
