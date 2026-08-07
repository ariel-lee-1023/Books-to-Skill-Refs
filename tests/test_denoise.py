"""Tests for bookrefs/denoise.py — boilerplate removal on a reading slice."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.denoise import (  # noqa: E402
    DEFAULT_ORDER,
    FILTERS,
    _is_mangled_table_row,
    clean,
    detect_filters,
    filter_blanks,
    filter_nav,
    filter_pdf,
    filter_quiz,
    filter_repeats,
    filter_rst,
)


class TestTableConservatism(unittest.TestCase):
    """The promise: drop extraction scaffolding, keep real tables."""

    def test_real_rows_are_kept(self):
        for row in ("| Area | Reward | Error |",
                    "| Basal Ganglia | +++ | --- |",
                    "| a | b |"):
            self.assertFalse(_is_mangled_table_row(row), row)

    def test_scaffolding_is_dropped(self):
        for row in ("| --- | --- | --- |",
                    "|  |  |  |",
                    "| x |  |  |  |  |",
                    "| --- | --- |"):
            self.assertTrue(_is_mangled_table_row(row), row)

    def test_non_table_lines_are_not_table_rows(self):
        self.assertFalse(_is_mangled_table_row("ordinary prose | with a pipe"))

    def test_filter_pdf_keeps_real_tables(self):
        lines = ["| Area | Reward |", "| --- | --- |", "| BG | +++ |"]
        self.assertEqual(filter_pdf(lines), ["| Area | Reward |", "| BG | +++ |"])


class TestPdfFilter(unittest.TestCase):
    def test_removes_page_markers_links_and_images(self):
        lines = [
            "Real prose.",
            "<!-- page 41 -->",
            "Link: [https://doi.org/10.1](https://doi.org/10.1)",
            "![PDF image 1 on page 8](asset:sha256:abc)",
            "More prose.",
        ]
        self.assertEqual(filter_pdf(lines), ["Real prose.", "More prose."])

    def test_case_insensitive_page_marker(self):
        self.assertEqual(filter_pdf(["<!-- Page 7 -->"]), [])


class TestRstFilter(unittest.TestCase):
    def test_removes_directives_options_and_underlines(self):
        lines = [
            "Chapter Title",
            "=============",
            ".. figure:: image.png",
            "   :align: center",
            "Real prose survives.",
        ]
        self.assertEqual(filter_rst(lines), ["Chapter Title", "Real prose survives."])

    def test_keeps_prose_containing_two_colons(self):
        self.assertEqual(filter_rst(["The ratio is 2::1 in this case."]),
                         ["The ratio is 2::1 in this case."])


class TestNavFilter(unittest.TestCase):
    def test_removes_navigation_chrome(self):
        lines = ["Skip to Main Content", "- Home", "Table of Contents",
                 "Actual chapter prose."]
        self.assertEqual(filter_nav(lines), ["Actual chapter prose."])

    def test_keeps_a_sentence_containing_a_nav_word(self):
        self.assertEqual(filter_nav(["Home is where the hippocampus is."]),
                         ["Home is where the hippocampus is."])


class TestQuizFilter(unittest.TestCase):
    def test_truncates_at_the_marker(self):
        lines = ["Body.", "More body.", "Test Your Knowledge", "- Question 1", "- A", "- B"]
        self.assertEqual(filter_quiz(lines), ["Body.", "More body."])

    def test_marker_with_heading_markup(self):
        self.assertEqual(filter_quiz(["Body.", "## Review Questions", "q"]), ["Body."])

    def test_no_marker_leaves_text_untouched(self):
        lines = ["Body.", "More body."]
        self.assertEqual(filter_quiz(lines), lines)


class TestRepeatsFilter(unittest.TestCase):
    def test_running_header_removed(self):
        lines = ["Chapter Seven: Memory Systems"] * 5 + ["Unique prose line here."]
        self.assertEqual(filter_repeats(lines), ["Unique prose line here."])

    def test_below_threshold_survives(self):
        lines = ["A repeated but not boilerplate line."] * 3
        self.assertEqual(filter_repeats(lines), lines)

    def test_short_lines_are_exempt(self):
        lines = ["ok"] * 10
        self.assertEqual(filter_repeats(lines), lines)

    def test_table_rows_are_exempt(self):
        """Composed with filter_pdf this is what keeps real tables alive."""
        lines = ["| Area | Reward | Error |"] * 8
        self.assertEqual(filter_repeats(lines), lines)


class TestBlanksFilter(unittest.TestCase):
    def test_runs_collapse_to_one(self):
        self.assertEqual(filter_blanks(["a", "", "", "", "b"]), ["a", "", "b"])


class TestAutoDetection(unittest.TestCase):
    def test_pdf_markers_select_the_pdf_filter(self):
        self.assertIn("pdf", detect_filters("body\n<!-- page 3 -->\nbody\n"))

    def test_rst_directives_select_the_rst_filter(self):
        self.assertIn("rst", detect_filters("text\n.. figure:: x.png\n"))

    def test_quiz_marker_selects_the_quiz_filter(self):
        self.assertIn("quiz", detect_filters("body\nTest Your Knowledge\nq\n"))

    def test_plain_prose_selects_only_the_safe_filters(self):
        chosen = detect_filters("Just ordinary prose about the hippocampus.\n")
        self.assertEqual(set(chosen), {"blanks", "repeats"})

    def test_detected_filters_follow_the_declared_order(self):
        chosen = detect_filters("<!-- page 1 -->\n.. figure:: a.png\nTest Your Knowledge\n")
        self.assertEqual(list(chosen), [n for n in DEFAULT_ORDER if n in chosen])


class TestClean(unittest.TestCase):
    def test_reports_what_it_removed(self):
        text = "prose\n" + "<!-- page 1 -->\n" * 5 + "more prose\n"
        result = clean(text, filters=("pdf",))
        self.assertEqual(result.lines_removed, 5)
        self.assertGreater(result.percent_removed, 0)
        self.assertEqual(result.applied, ("pdf",))

    def test_explicit_filters_are_reordered_not_reinterpreted(self):
        result = clean("x\n", filters=("blanks", "pdf"))
        self.assertEqual(result.applied, ("pdf", "blanks"))

    def test_unknown_filter_name_is_ignored(self):
        result = clean("x\n", filters=("nonexistent",))
        self.assertEqual(result.applied, ())

    def test_every_registered_filter_is_in_the_default_order(self):
        self.assertEqual(set(FILTERS), set(DEFAULT_ORDER))

    def test_output_ends_with_a_single_newline(self):
        self.assertTrue(clean("a\n\n\n").text.endswith("\n"))
        self.assertFalse(clean("a\n\n\n").text.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
