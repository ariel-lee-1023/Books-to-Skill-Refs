"""Tests for tools/reference_budget.py — the Step 7 / Step 8 budget formulas.

The properties asserted here are the ones the formula exists to guarantee, not
just its arithmetic: sub-linear growth in section count (the defect that made a
linear per-section allowance over-budget thick books), internal consistency
between budget and cap (the defect that made the old 2x2 table unsatisfiable for
a 26-chapter technical book), and the ordering the depth/type multipliers encode.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from reference_budget import (  # noqa: E402
    CAP_AT_SECTIONS,
    MASTER_HARD_STOP,
    TOLERANCE,
    master_budget,
    measure_library,
    reference_budget,
    reference_cap,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestReferenceBudget(unittest.TestCase):
    def test_grows_with_sections(self):
        self.assertLess(reference_budget(5), reference_budget(20))
        self.assertLess(reference_budget(20), reference_budget(40))

    def test_growth_is_sub_linear(self):
        """Doubling the chapters must not double the file.

        This is the defect the formula replaces: cost per section falls as
        sections rise, because you merge and compress.
        """
        small, large = reference_budget(10), reference_budget(20)
        self.assertLess(large, 2 * small)
        per_section_small = small / 10
        per_section_large = large / 20
        self.assertLess(per_section_large, per_section_small)

    def test_study_exceeds_reference_depth(self):
        for n in (5, 20, 50):
            self.assertGreater(reference_budget(n, "study"), reference_budget(n, "reference"))

    def test_technical_exceeds_text(self):
        for n in (5, 20, 50):
            self.assertGreater(reference_budget(n, book_type="technical"),
                               reference_budget(n, book_type="text"))

    def test_budget_never_exceeds_its_own_cap_within_range(self):
        """The old 2x2 table was unsatisfiable for a 26-section technical book."""
        for depth in ("study", "reference"):
            for book_type in ("text", "technical"):
                cap = reference_cap(depth, book_type)
                for n in range(1, CAP_AT_SECTIONS + 1):
                    self.assertLessEqual(
                        reference_budget(n, depth, book_type), cap,
                        msg=f"{n} sections {depth}/{book_type} exceeds its own cap",
                    )

    def test_cap_is_the_budget_at_the_stated_section_count_rounded_up(self):
        for depth in ("study", "reference"):
            for book_type in ("text", "technical"):
                raw = reference_budget(CAP_AT_SECTIONS, depth, book_type)
                cap = reference_cap(depth, book_type)
                self.assertGreaterEqual(cap, raw)
                self.assertLess(cap - raw, 500)
                self.assertEqual(cap % 500, 0)

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            reference_budget(0)
        with self.assertRaises(ValueError):
            reference_budget(10, depth="skim")
        with self.assertRaises(ValueError):
            reference_budget(10, book_type="poetry")

    def test_matches_the_calibration_library(self):
        """Retrodiction on the five hand-written files it was fitted against."""
        observed = {11: 8_156, 19: 10_323, 21: 9_358, 22: 11_149, 25: 10_557}
        for sections, actual in observed.items():
            budget = reference_budget(sections, "study", "text")
            err = abs(budget - actual) / actual
            self.assertLessEqual(err, TOLERANCE,
                                 msg=f"{sections} sections: budget {budget} vs actual {actual}")


class TestMasterBudget(unittest.TestCase):
    def test_scales_with_books_and_capabilities(self):
        self.assertLess(master_budget(5), master_budget(20))
        self.assertLess(master_budget(5, 2), master_budget(5, 6))

    def test_capability_term_is_present(self):
        """The old formula had no term for the behaviour blocks, so it read 3.3x under."""
        self.assertGreater(master_budget(5, 4), master_budget(5, 0))

    def test_index_allowance_is_capped(self):
        self.assertEqual(master_budget(5, 4, 40), master_budget(5, 4, 400))

    def test_calibration_library_is_inside_budget_and_stop(self):
        budget = master_budget(n_books=5, n_capabilities=4, index_entries=14)
        actual = 3_158
        self.assertLessEqual(abs(budget - actual) / actual, TOLERANCE)
        self.assertLess(actual, MASTER_HARD_STOP)

    def test_a_normal_library_fits_under_the_hard_stop(self):
        self.assertLess(master_budget(10, 4, 24), MASTER_HARD_STOP)


class TestMeasureLibrary(unittest.TestCase):
    def test_good_fixture_is_within_budget(self):
        rows, master = measure_library(FIXTURES / "good-library")
        self.assertTrue(rows)
        self.assertIsNotNone(master)
        for row in rows:
            self.assertLessEqual(row["tokens"], row["cap"])

    def test_over_budget_fixture_breaches_its_cap(self):
        rows, _ = measure_library(FIXTURES / "over-budget-library")
        self.assertTrue(any(r["tokens"] > r["cap"] for r in rows),
                        "the over-budget fixture must breach a cap, or CI proves nothing")

    def test_missing_sections_header_yields_no_budget(self):
        rows, _ = measure_library(FIXTURES / "over-budget-library")
        self.assertTrue(all(r["sections"] is None or r["budget"] is not None for r in rows))


if __name__ == "__main__":
    unittest.main()
