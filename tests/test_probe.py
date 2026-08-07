"""Tests for bookrefs/probe.py — candidate chapter boundaries in converted sources."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.probe import (  # noqa: E402
    PLAUSIBLE_MIN,
    STRATEGIES,
    probe,
    score_candidates,
)
from bookrefs.probe import Candidate  # noqa: E402


def academic_pdf_text(chapters=6, sections=3, body=10):
    """A converted edited volume: DOI markers, Abstract blocks, numbered sections.

    Deliberately contains no "Chapter N" heading, which is the case the
    canonical detector cannot see and this module exists for.
    """
    lines = []
    for ch in range(1, chapters + 1):
        lines += ["", f"### {ch} Title Of Chapter {ch}", "", "A. Author and B. Author", "",
                  "##### Abstract", f"This chapter covers topic {ch}.", "",
                  f"Link: [https://doi.org/10.1007/978-3-031-45271-0_{ch}](x)", ""]
        for sec in range(1, sections + 1):
            lines += [f"{ch}.{sec} A SECTION HEADING", ""]
            lines += [f"Prose line {i} of {ch}.{sec}." for i in range(body)]
            lines += [""]
    return "\n".join(lines)


class TestStrategiesOnAcademicText(unittest.TestCase):
    def setUp(self):
        self.text = academic_pdf_text(chapters=6)
        self.result = probe(self.text)
        self.by_name = {r.name: r for r in self.result.results}

    def test_canonical_detector_finds_nothing(self):
        """The premise: heading dialects do not appear in converted academic PDFs."""
        self.assertEqual(self.by_name["canonical"].count, 0)

    def test_doi_recovers_the_chapter_count(self):
        self.assertEqual(self.by_name["doi"].count, 6)

    def test_abstract_recovers_the_chapter_count(self):
        self.assertEqual(self.by_name["abstract"].count, 6)

    def test_abstract_labels_use_the_heading_not_the_byline(self):
        labels = [c.label for c in self.by_name["abstract"].candidates]
        self.assertTrue(all(label.startswith(("1 Title", "2 Title", "3 Title",
                                              "4 Title", "5 Title", "6 Title"))
                            for label in labels), labels)

    def test_numbered_finds_sections_not_chapters(self):
        self.assertEqual(self.by_name["numbered"].count, 18)   # 6 x 3

    def test_markdown_level_is_configurable(self):
        shallow = probe(self.text, strategies=("markdown",), max_level=2)
        deep = probe(self.text, strategies=("markdown",), max_level=3)
        self.assertEqual(shallow.results[0].count, 0)
        self.assertEqual(deep.results[0].count, 6)

    def test_best_is_a_strategy_that_found_the_chapters(self):
        self.assertIsNotNone(self.result.best)
        self.assertIn(self.result.best.name, {"doi", "abstract", "numbered"})

    def test_results_are_ranked_by_score(self):
        scores = [r.score for r in self.result.results]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestCanonicalStillWorks(unittest.TestCase):
    def test_trade_book_headings_are_found(self):
        text = "\n".join(
            [f"Chapter {n}: A Title\n\nBody paragraph for chapter {n}.\n" for n in range(1, 6)]
        )
        result = probe(text, strategies=("canonical",))
        self.assertEqual(result.results[0].count, 5)


class TestDoiStrategy(unittest.TestCase):
    def test_first_hit_per_chapter_number_only(self):
        text = "\n".join([f"Link: 10.1007/978-3-031-45271-0_{n}" for n in (1, 1, 1, 2, 2, 3)])
        result = probe(text, strategies=("doi",))
        self.assertEqual(result.results[0].count, 3)

    def test_implausible_numbers_ignored(self):
        text = "10.1007/978-3-031-45271-0_500\n"
        result = probe(text, strategies=("doi",))
        self.assertEqual(result.results[0].count, 0)


class TestNumberedStrategy(unittest.TestCase):
    def test_only_two_level_numbers(self):
        text = "1.1 A Heading\n2.4.1 Deeper Heading\n3.2 Another Heading\n"
        result = probe(text, strategies=("numbered",))
        labels = [c.label for c in result.results[0].candidates]
        self.assertEqual(len(labels), 2)
        self.assertTrue(all("2.4.1" not in label for label in labels))

    def test_lowercase_titles_are_not_headings(self):
        text = "1.1 a sentence continuing the paragraph\n"
        result = probe(text, strategies=("numbered",))
        self.assertEqual(result.results[0].count, 0)


class TestScoring(unittest.TestCase):
    def test_too_few_candidates_scores_zero(self):
        few = [Candidate(line=i, label="x") for i in range(PLAUSIBLE_MIN - 1)]
        self.assertEqual(score_candidates(few, 1000), 0.0)

    def test_even_spread_beats_clustered(self):
        even = [Candidate(line=i, label="x", number=float(i)) for i in range(1, 1000, 100)]
        clustered = [Candidate(line=i, label="x", number=float(i)) for i in range(1, 30, 3)]
        self.assertGreater(score_candidates(even, 1000), score_candidates(clustered, 1000))

    def test_descending_numbers_score_below_ascending(self):
        lines = list(range(1, 1000, 100))
        ascending = [Candidate(line=l, label="x", number=float(i))
                     for i, l in enumerate(lines)]
        descending = [Candidate(line=l, label="x", number=float(-i))
                      for i, l in enumerate(lines)]
        self.assertGreater(score_candidates(ascending, 1000),
                           score_candidates(descending, 1000))

    def test_outline_sized_hit_count_is_penalised(self):
        """Hundreds of boundaries is an outline, not a chapter list."""
        many = [Candidate(line=i * 2, label="x") for i in range(1, 400)]
        few = [Candidate(line=i * 100, label="x") for i in range(1, 9)]
        self.assertLess(score_candidates(many, 40_000), score_candidates(few, 1000))


class TestProbeShape(unittest.TestCase):
    def test_unknown_strategy_is_skipped_not_fatal(self):
        result = probe("body\n" * 50, strategies=("doi", "no-such-strategy"))
        self.assertEqual([r.name for r in result.results], ["doi"])

    def test_every_registered_strategy_runs(self):
        result = probe(academic_pdf_text())
        self.assertEqual({r.name for r in result.results}, set(STRATEGIES))

    def test_best_is_none_when_nothing_plausible(self):
        self.assertIsNone(probe("just one line\n").best)


if __name__ == "__main__":
    unittest.main()
