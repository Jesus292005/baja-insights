"""Free matches must look like football: every metric inside its Premier League reference range."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.realism import format_report, measure, out_of_range
from helpers import roster


class RealismTest(unittest.TestCase):
    def test_free_matches_are_inside_the_reference_ranges(self):
        report = measure(roster(), range(1, 101))
        self.assertEqual(out_of_range(report), {}, "\n" + format_report(report))


if __name__ == "__main__":
    unittest.main()
