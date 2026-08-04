"""Tests for tools/count_tokens.py.

The regression that motivated this tool: a word-split estimator
(`len(text.split()) / 0.75`) undercounts space-free scripts by orders of
magnitude, which silently defeats Step 2.5's cost gate on CJK sources.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from count_tokens import estimate_tokens, is_dense, strip_frontmatter  # noqa: E402

CHINESE = "本技能用于辅助法官在疑难案件中识别法律价值冲突、确定裁量边界、展开价值衡量。" * 20
ENGLISH = "This skill helps judges identify conflicts of legal value in hard cases. " * 20


def word_split_estimate(text: str) -> int:
    """The upstream estimator this tool replaces, for comparison."""
    return int(len(text.split()) / 0.75)


class TestDensity(unittest.TestCase):
    def test_han_is_dense(self):
        for ch in "法律价值":
            self.assertTrue(is_dense(ch), ch)

    def test_kana_hangul_thai_are_dense(self):
        for ch in "ひらがなカタカナ한글บทที่":
            self.assertTrue(is_dense(ch), ch)

    def test_latin_and_digits_are_not_dense(self):
        for ch in "abcXYZ019 .,-":
            self.assertFalse(is_dense(ch), repr(ch))

    def test_fullwidth_punctuation_is_dense(self):
        for ch in "、。「」":
            self.assertTrue(is_dense(ch), ch)


class TestEstimate(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(estimate_tokens(""), 0)

    def test_english_is_in_the_conventional_range(self):
        # ~4 characters per token is the usual approximation for English prose.
        tokens = estimate_tokens(ENGLISH)
        self.assertAlmostEqual(tokens, len(ENGLISH) / 4, delta=len(ENGLISH) / 40)

    def test_chinese_is_not_undercounted(self):
        # The whole point: Chinese has no spaces, so a word-split estimator
        # collapses this to a handful of tokens.
        tokens = estimate_tokens(CHINESE)
        self.assertGreater(tokens, len(CHINESE) / 2)
        self.assertLess(tokens, len(CHINESE))

    def test_beats_word_split_on_chinese_by_orders_of_magnitude(self):
        self.assertGreater(estimate_tokens(CHINESE), word_split_estimate(CHINESE) * 100)

    def test_agrees_with_word_split_on_english(self):
        # Within 2x — both approximations are in the same ballpark for English,
        # which is why the old estimator's failure went unnoticed.
        ours, theirs = estimate_tokens(ENGLISH), word_split_estimate(ENGLISH)
        self.assertLess(max(ours, theirs) / min(ours, theirs), 2.0)

    def test_mixed_script_lands_between_the_two_rates(self):
        mixed = CHINESE + ENGLISH
        self.assertGreater(estimate_tokens(mixed), estimate_tokens(ENGLISH))
        self.assertEqual(estimate_tokens(mixed),
                         estimate_tokens(CHINESE) + estimate_tokens(ENGLISH))

    def test_monotonic_in_length(self):
        self.assertGreater(estimate_tokens(CHINESE * 2), estimate_tokens(CHINESE))


class TestStripFrontmatter(unittest.TestCase):
    def test_removes_leading_block(self):
        doc = "---\nname: x\ndescription: y\n---\nbody text\n"
        self.assertEqual(strip_frontmatter(doc), "body text\n")

    def test_leaves_document_without_frontmatter_alone(self):
        doc = "# Title\n\nbody\n"
        self.assertEqual(strip_frontmatter(doc), doc)

    def test_does_not_strip_a_later_horizontal_rule(self):
        doc = "# Title\n\n---\n\nmore\n"
        self.assertEqual(strip_frontmatter(doc), doc)

    def test_body_only_lowers_the_count(self):
        doc = "---\nname: x\ndescription: a fairly long description here\n---\nbody\n"
        self.assertLess(estimate_tokens(strip_frontmatter(doc)), estimate_tokens(doc))


if __name__ == "__main__":
    unittest.main()
