"""Tests for bookrefs/parsers — one per format family."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.exceptions import ParseFailure, UnsupportedFormat  # noqa: E402
from bookrefs.parsers import parse, parser_for  # noqa: E402
from bookrefs.parsers.base import decode  # noqa: E402
from bookrefs.parsers.html import html_to_text  # noqa: E402
from bookrefs.parsers.rtf import rtf_to_text  # noqa: E402
from tests.builders import write_docx, write_epub, write_rtf  # noqa: E402


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)


class TestDispatch(unittest.TestCase):
    def test_known_extensions(self):
        self.assertEqual(parser_for(Path("a.md")), "text")
        self.assertEqual(parser_for(Path("a.EPUB")), "epub")
        self.assertEqual(parser_for(Path("a.pdf")), "pdf")
        self.assertEqual(parser_for(Path("a.azw3")), "calibre")

    def test_unknown_extension_names_the_supported_set(self):
        with self.assertRaises(UnsupportedFormat) as ctx:
            parser_for(Path("a.pages"))
        self.assertIn(".epub", str(ctx.exception))


class TestDecoding(unittest.TestCase):
    def test_utf8(self):
        self.assertEqual(decode("法律".encode("utf-8")), "法律")

    def test_legacy_chinese_encoding_is_not_mojibake(self):
        # gb18030 is tried before the latin fallback, so this decodes as
        # Chinese rather than as bytes that merely "succeed".
        self.assertEqual(decode("法律推理".encode("gb18030")), "法律推理")

    def test_bom_is_stripped(self):
        self.assertEqual(decode("hi".encode("utf-8-sig")), "hi")

    def test_never_raises(self):
        self.assertIsInstance(decode(b"\xff\xfe\x00garbage"), str)


class TestHtml(unittest.TestCase):
    def test_headings_become_markdown(self):
        self.assertIn("# Title", html_to_text("<h1>Title</h1>"))
        self.assertIn("### Sub", html_to_text("<h3>Sub</h3>"))

    def test_script_and_style_are_dropped(self):
        out = html_to_text("<style>p{color:red}</style><script>x=1</script><p>Body</p>")
        self.assertNotIn("color", out)
        self.assertNotIn("x=1", out)
        self.assertIn("Body", out)

    def test_tables_become_pipe_rows(self):
        self.assertIn("| a | b |", html_to_text("<table><tr><td>a</td><td>b</td></tr></table>"))

    def test_pre_becomes_a_fenced_block(self):
        self.assertIn("```", html_to_text("<pre>def f(): pass</pre>"))

    def test_inline_tags_do_not_insert_a_space_before_punctuation(self):
        self.assertIn("world.", html_to_text("<p>Hello <b>world</b>.</p>"))

    def test_entities_are_resolved(self):
        self.assertIn("A&B", html_to_text("<p>A&amp;B</p>"))


class TestDocx(TempDirCase):
    def test_paragraphs_and_heading_styles(self):
        path = write_docx(self.tmp / "d.docx", [
            ("Chapter One", "Heading1"),
            ("Body text here.", None),
            ("A Subsection", "Heading2"),
        ])
        text = parse(path).text
        self.assertIn("# Chapter One", text)
        self.assertIn("## A Subsection", text)
        self.assertIn("Body text here.", text)

    def test_tables_become_pipe_rows(self):
        path = write_docx(self.tmp / "t.docx", [("Intro", None)],
                          table=[["h1", "h2"], ["v1", "v2"]])
        text = parse(path).text
        self.assertIn("| h1 | h2 |", text)
        self.assertIn("| v1 | v2 |", text)

    def test_cjk_content_survives(self):
        path = write_docx(self.tmp / "cn.docx", [("第一章 绪论", "Heading1"), ("法律推理。", None)])
        self.assertIn("第一章 绪论", parse(path).text)

    def test_corrupt_file_fails_clearly(self):
        bad = self.tmp / "bad.docx"
        bad.write_bytes(b"not a zip")
        with self.assertRaises(ParseFailure):
            parse(bad)


class TestEpub(TempDirCase):
    def test_reads_chapters(self):
        path = write_epub(self.tmp / "b.epub", [
            ("c1.xhtml", "<h1>Chapter 1: One</h1><p>First.</p>"),
            ("c2.xhtml", "<h1>Chapter 2: Two</h1><p>Second.</p>"),
        ])
        text = parse(path).text
        self.assertIn("First.", text)
        self.assertIn("Second.", text)

    def test_follows_spine_order_not_zip_order(self):
        path = write_epub(self.tmp / "s.epub", [
            ("c1.xhtml", "<p>FIRST</p>"),
            ("c2.xhtml", "<p>SECOND</p>"),
        ], shuffle_zip=True)
        text = parse(path).text
        self.assertLess(text.index("FIRST"), text.index("SECOND"))

    def test_corrupt_file_fails_clearly(self):
        bad = self.tmp / "bad.epub"
        bad.write_bytes(b"not a zip")
        with self.assertRaises(ParseFailure):
            parse(bad)


class TestRtf(TempDirCase):
    def test_control_words_are_stripped(self):
        self.assertEqual(rtf_to_text(r"{\rtf1\ansi Hello world}").strip(), "Hello world")

    def test_unicode_escapes_are_decoded(self):
        # Word stores all non-Latin text this way; dropping it would silently
        # empty a Chinese document while appearing to succeed.
        # U+6CD5 法 = 27861, U+5F8B 律 = 24459.
        self.assertEqual(rtf_to_text("\\u27861?\\u24459?").strip(), "法律")

    def test_metadata_groups_are_discarded(self):
        path = write_rtf(self.tmp / "a.rtf", r"\par Visible body.")
        text = parse(path).text
        self.assertIn("Visible body.", text)
        self.assertNotIn("Ignored", text)
        self.assertNotIn("Times", text)

    def test_paragraph_breaks_become_newlines(self):
        self.assertIn("\n", rtf_to_text(r"{\rtf1 one\par two}"))


class TestText(TempDirCase):
    def test_markup_is_preserved(self):
        # Markdown headings feed structure detection and fenced code feeds the
        # technical/text tripwire, so neither may be flattened away.
        path = self.tmp / "a.md"
        path.write_text("# Title\n\n```py\nx = 1\n```\n", encoding="utf-8")
        text = parse(path).text
        self.assertIn("# Title", text)
        self.assertIn("```", text)


if __name__ == "__main__":
    unittest.main()
