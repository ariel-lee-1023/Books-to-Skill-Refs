"""Tests for tools/validate_library.py — the SKILL.md contracts as assertions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from validate_library import (  # noqa: E402
    REFERENCE_CAPS,
    detect_book_type,
    declared_depth,
    sections_of,
    validate,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOOD = FIXTURES / "good-library"
BAD = FIXTURES / "bad-library"


def messages(rep):
    return " || ".join(rep.errors + rep.warnings)


class TestGoodLibrary(unittest.TestCase):
    def setUp(self):
        self.rep = validate(GOOD)

    def test_no_errors(self):
        self.assertEqual(self.rep.errors, [], messages(self.rep))

    def test_counts_books(self):
        self.assertEqual(self.rep.facts["books"], 2)

    def test_master_within_budget(self):
        self.assertLessEqual(self.rep.facts["master_body_tokens"], 3_500)

    def test_every_reference_under_its_cap(self):
        for name, f in self.rep.facts["references"].items():
            self.assertLessEqual(f["tokens"], f["cap"], name)

    def test_reference_metadata_is_read_from_the_file(self):
        f = self.rep.facts["references"]["reference-cialdini-influence.md"]
        self.assertEqual(f["depth"], "study")
        self.assertEqual(f["type"], "text")


class TestBadLibrary(unittest.TestCase):
    def setUp(self):
        self.rep = validate(BAD)
        self.blob = messages(self.rep)

    def test_fails(self):
        self.assertTrue(self.rep.errors)

    def test_rejects_subdirectory(self):
        self.assertIn("flat", self.blob)
        self.assertIn("chapters", self.blob)

    def test_rejects_invalid_name_slug(self):
        self.assertIn("Bad_Library", self.blob)

    def test_rejects_short_description(self):
        self.assertIn("description", self.blob)

    def test_reports_router_link_to_missing_file(self):
        self.assertIn("reference-ghost.md", self.blob)

    def test_reports_orphan_reference_file(self):
        self.assertIn("reference-orphan-book.md is not linked", self.blob)

    def test_reports_single_book_topic_index_entry(self):
        self.assertIn("Solo Term", self.blob)

    def test_reports_missing_required_section(self):
        self.assertIn("Key Takeaways", self.blob)

    def test_reports_worked_example_at_reference_depth(self):
        self.assertIn("DEPTH=reference but contains a Worked Example", self.blob)


class TestHelpers(unittest.TestCase):
    def test_sections_of_splits_on_h2_only(self):
        doc = "# Title\n\n## One\na\n\n### Sub\nb\n\n## Two\nc\n"
        self.assertEqual(list(sections_of(doc)), ["One", "Two"])
        self.assertIn("### Sub", sections_of(doc)["One"])

    def test_detect_book_type_flags_fenced_code(self):
        self.assertEqual(detect_book_type("text\n```py\nx = 1\n```\n"), "technical")

    def test_detect_book_type_ignores_a_small_decision_table(self):
        # Step 7 asks Decision Rules to use compact tables, so tables alone
        # must not push a prose book into the technical cap.
        doc = "\n".join(["| a | b |", "|---|---|"] + ["| x | y |"] * 4)
        self.assertEqual(detect_book_type(doc), "text")

    def test_detect_book_type_flags_a_large_table_block(self):
        doc = "\n".join(["| a | b |"] * 15)
        self.assertEqual(detect_book_type(doc), "technical")

    def test_declared_depth_reads_the_header_line(self):
        self.assertEqual(declared_depth("**Depth**: study", "reference"), "study")

    def test_declared_depth_falls_back(self):
        self.assertEqual(declared_depth("no declaration here", "study"), "study")

    def test_caps_match_skill_md(self):
        self.assertEqual(REFERENCE_CAPS[("text", "reference")], 9_000)
        self.assertEqual(REFERENCE_CAPS[("text", "study")], 14_000)
        self.assertEqual(REFERENCE_CAPS[("technical", "reference")], 12_000)
        self.assertEqual(REFERENCE_CAPS[("technical", "study")], 20_000)

    def test_technical_caps_exceed_text_caps(self):
        for depth in ("reference", "study"):
            self.assertGreater(REFERENCE_CAPS[("technical", depth)],
                               REFERENCE_CAPS[("text", depth)])


class TestMissingLibrary(unittest.TestCase):
    def test_nonexistent_directory_errors(self):
        rep = validate(FIXTURES / "does-not-exist")
        self.assertTrue(rep.errors)


if __name__ == "__main__":
    unittest.main()
