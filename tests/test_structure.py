"""Tests for bookrefs/structure.py — chapter and ToC detection."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.structure import (  # noqa: E402
    detect_structure,
    parse_arabic,
    parse_chinese,
    parse_roman,
    parse_thai,
)


class TestNumerals(unittest.TestCase):
    def test_arabic_including_fullwidth(self):
        self.assertEqual(parse_arabic("7"), 7)
        self.assertEqual(parse_arabic("１２"), 12)
        self.assertIsNone(parse_arabic("seven"))

    def test_roman(self):
        self.assertEqual(parse_roman("IV"), 4)
        self.assertEqual(parse_roman("XIV"), 14)
        self.assertEqual(parse_roman("MCM"), 1900)
        self.assertIsNone(parse_roman("ABC"))

    def test_chinese_units(self):
        for token, expected in [("三", 3), ("十", 10), ("十二", 12), ("二十", 20),
                                ("二十三", 23), ("一百零八", 108), ("两", 2)]:
            self.assertEqual(parse_chinese(token), expected, token)

    def test_chinese_accepts_fullwidth_digits(self):
        self.assertEqual(parse_chinese("１２"), 12)

    def test_thai_digits(self):
        self.assertEqual(parse_thai("๑๒"), 12)
        self.assertEqual(parse_thai("12"), 12)


class TestHeadingDetection(unittest.TestCase):
    def detect(self, text):
        return detect_structure(text).headings

    def test_english_chapters(self):
        found = self.detect("Chapter 1: Beginnings\nbody\n\nChapter 2. Middles\nbody\n")
        self.assertEqual([h.number for h in found], [1, 2])
        self.assertEqual(found[0].title, "Beginnings")

    def test_rejects_prose_cross_reference(self):
        # "Chapter 6 explores..." is a sentence, not a heading.
        self.assertEqual(self.detect("As Chapter 6 explores in detail, this is prose.\n"), ())
        self.assertEqual(self.detect("Chapter 6 explores something else entirely.\n"), ())

    def test_european_chapter_words(self):
        found = self.detect("Capítulo 3: Título\nKapitel 4. Titel\nChapitre 5: Titre\n")
        self.assertEqual([h.number for h in found], [3, 4, 5])

    def test_roman_standalone_needs_a_title(self):
        self.assertEqual([h.number for h in self.detect("IV. The Carpet-Bag\n")], [4])
        self.assertEqual(self.detect("V.\n"), ())

    def test_chinese_chapters(self):
        found = self.detect("第一章 绪论\n第2章 演绎\n第十二节 结论\n")
        self.assertEqual([h.number for h in found], [1, 2, 12])
        self.assertEqual(found[0].title, "绪论")

    def test_chinese_classifiers(self):
        for line in ["第三回 回目", "第四卷 卷名", "第五篇 篇名", "第六讲 讲名", "第七部 部名"]:
            self.assertTrue(self.detect(line + "\n"), line)

    def test_chinese_markdown_heading(self):
        self.assertTrue(self.detect("## 第三讲 论证\n"))
        self.assertTrue(self.detect("## 一 · 缘起\n"))

    def test_thai_chapters(self):
        self.assertEqual([h.number for h in self.detect("บทที่ ๓ บทนำ\nตอนที่ 12 สรุป\n")], [3, 12])

    def test_dedupes_toc_entry_and_body_heading(self):
        # The same chapter number appearing in the ToC and again in the body is
        # one chapter, not two.
        text = "目录\n第一章 绪论\n第二章 推理\n\n第一章 绪论\n正文\n\n第二章 推理\n正文\n"
        self.assertEqual([h.number for h in self.detect(text)], [1, 2])

    def test_records_line_numbers_for_slicing(self):
        found = self.detect("intro\nChapter 1: One\nbody\nChapter 2: Two\n")
        self.assertEqual([h.line for h in found], [2, 4])

    def test_rejects_out_of_range_numbers(self):
        self.assertEqual(self.detect("Chapter 2025. A Year\n"), ())

    def test_mixed_scripts_in_one_document(self):
        found = self.detect("Chapter 1: Intro\n第二章 推理\nบทที่ 3 สรุป\n")
        self.assertEqual(len(found), 3)


class TestTocDetection(unittest.TestCase):
    def test_detects_english_and_cjk_toc(self):
        for header in ["Table of Contents", "Contents", "目录", "目錄", "目次", "สารบัญ", "차례"]:
            self.assertTrue(detect_structure(f"{header}\n\nChapter 1: X\n").has_toc, header)

    def test_ignores_inline_mention(self):
        self.assertFalse(detect_structure("the contents of this chapter are listed\n").has_toc)

    def test_markdown_toc_heading(self):
        self.assertTrue(detect_structure("## 目录\n").has_toc)


if __name__ == "__main__":
    unittest.main()
