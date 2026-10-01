from __future__ import annotations

import unittest

from research.wrong_direction.wd2_anatomy import probability_b_greater_than_a


class WD2AnatomyTests(unittest.TestCase):
    def test_probability_perfect_separation(self):
        self.assertEqual(
            probability_b_greater_than_a([1.0, 2.0], [3.0, 4.0]),
            1.0,
        )

    def test_probability_reverse_separation(self):
        self.assertEqual(
            probability_b_greater_than_a([3.0, 4.0], [1.0, 2.0]),
            0.0,
        )

    def test_probability_ties_are_half_credit(self):
        self.assertAlmostEqual(
            probability_b_greater_than_a([1.0, 2.0], [2.0, 2.0]),
            0.75,
        )


if __name__ == "__main__":
    unittest.main()
