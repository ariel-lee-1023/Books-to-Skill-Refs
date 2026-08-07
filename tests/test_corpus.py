"""Tests for bookrefs/corpus.py — ordering and consolidation of multi-file sources."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.corpus import (  # noqa: E402
    build_plan,
    detect_order,
    natural_key,
    parse_toctrees,
    plan_jupyter_book,
    plan_natural,
    plan_sphinx,
    render,
)


class TempTree(unittest.TestCase):
    """Builds throwaway source trees; fixtures stay reviewable in the diff."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, rel, text=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class TestNaturalKey(unittest.TestCase):
    def test_digits_compare_numerically(self):
        names = ["ch10.md", "ch2.md", "ch1.md", "ch20.md"]
        self.assertEqual(sorted(names, key=natural_key),
                         ["ch1.md", "ch2.md", "ch10.md", "ch20.md"])

    def test_case_insensitive(self):
        self.assertEqual(sorted(["B.md", "a.md"], key=natural_key), ["a.md", "B.md"])


class TestToctreeParsing(unittest.TestCase):
    def test_entries_options_and_caption(self):
        text = (
            "Title\n=====\n\n"
            ".. toctree::\n"
            "   :maxdepth: 2\n"
            "   :caption: Getting started\n"
            "\n"
            "   intro\n"
            "   sub/overview\n"
            "\n"
            "Body text that is not an entry.\n"
        )
        blocks = parse_toctrees(text)
        self.assertEqual(len(blocks), 1)
        caption, entries = blocks[0]
        self.assertEqual(caption, "Getting started")
        self.assertEqual(entries, ["intro", "sub/overview"])

    def test_titled_entry_uses_the_path(self):
        text = ".. toctree::\n\n   Nice Title <guide/setup>\n"
        self.assertEqual(parse_toctrees(text)[0][1], ["guide/setup"])

    def test_block_ends_at_dedent(self):
        text = ".. toctree::\n\n   inside\n\nOutside paragraph\n"
        self.assertEqual(parse_toctrees(text)[0][1], ["inside"])

    def test_multiple_blocks(self):
        text = ".. toctree::\n\n   a\n\n.. toctree::\n   :caption: Two\n\n   b\n"
        blocks = parse_toctrees(text)
        self.assertEqual([b[1] for b in blocks], [["a"], ["b"]])


class TestSphinxRecursion(TempTree):
    """The failure this module exists to prevent: a flat read of nested toctrees."""

    def build_nested(self):
        self.write("index.rst",
                   ".. toctree::\n   :caption: Part One\n\n   intro\n   sub/overview\n")
        self.write("intro.rst", "Intro\n=====\n")
        self.write("sub/overview.rst",
                   "Overview\n========\n\n.. toctree::\n   :caption: Deep\n\n"
                   "   deep_one\n   deep_two\n")
        self.write("sub/deep_one.rst", "One\n")
        self.write("sub/deep_two.rst", "Two\n")

    def test_reaches_second_level(self):
        self.build_nested()
        plan = plan_sphinx(self.root / "index.rst", self.root)
        self.assertEqual([p.rel for p in plan.parts],
                         ["intro.rst", "sub/overview.rst",
                          "sub/deep_one.rst", "sub/deep_two.rst"])

    def test_captions_follow_the_block(self):
        self.build_nested()
        plan = plan_sphinx(self.root / "index.rst", self.root)
        by_rel = {p.rel: p.caption for p in plan.parts}
        self.assertEqual(by_rel["intro.rst"], "Part One")
        self.assertEqual(by_rel["sub/deep_one.rst"], "Deep")

    def test_root_is_not_emitted_as_a_part(self):
        self.build_nested()
        plan = plan_sphinx(self.root / "index.rst", self.root)
        self.assertNotIn("index.rst", [p.rel for p in plan.parts])

    def test_unreached_files_are_reported_not_included(self):
        self.build_nested()
        self.write("orphan.rst", "Orphan\n")
        plan = plan_sphinx(self.root / "index.rst", self.root)
        self.assertNotIn("orphan.rst", [p.rel for p in plan.parts])
        self.assertIn("orphan.rst", plan.unreached)

    def test_cycle_terminates(self):
        self.write("index.rst", ".. toctree::\n\n   a\n")
        self.write("a.rst", "A\n=\n\n.. toctree::\n\n   b\n")
        self.write("b.rst", "B\n=\n\n.. toctree::\n\n   a\n")
        plan = plan_sphinx(self.root / "index.rst", self.root)
        self.assertEqual([p.rel for p in plan.parts], ["a.rst", "b.rst"])

    def test_entry_relative_to_containing_document(self):
        self.write("index.rst", ".. toctree::\n\n   sub/overview\n")
        self.write("sub/overview.rst", "O\n=\n\n.. toctree::\n\n   sibling\n")
        self.write("sub/sibling.rst", "S\n")
        plan = plan_sphinx(self.root / "index.rst", self.root)
        self.assertIn("sub/sibling.rst", [p.rel for p in plan.parts])


class TestJupyterBook(TempTree):
    def test_root_then_files_in_declared_order(self):
        self.write("_toc.yml",
                   "format: jb-book\nroot: intro\nparts:\n"
                   "- caption: The tools\n  chapters:\n"
                   "  - file: to_code\n  - file: nested/deep\n")
        for rel in ("intro.md", "to_code.md", "nested/deep.md"):
            self.write(rel, f"# {rel}\n")
        plan = plan_jupyter_book(self.root / "_toc.yml", self.root)
        self.assertEqual([p.rel for p in plan.parts],
                         ["intro.md", "to_code.md", "nested/deep.md"])

    def test_caption_attaches_to_following_files_only(self):
        self.write("_toc.yml",
                   "root: intro\nparts:\n- caption: Tools\n  chapters:\n  - file: a\n")
        self.write("intro.md", "i")
        self.write("a.md", "a")
        plan = plan_jupyter_book(self.root / "_toc.yml", self.root)
        captions = {p.rel: p.caption for p in plan.parts}
        self.assertIsNone(captions["intro.md"])
        self.assertEqual(captions["a.md"], "Tools")

    def test_entry_without_extension_resolves(self):
        self.write("_toc.yml", "root: intro\n")
        self.write("intro.Rmd", "x")
        plan = plan_jupyter_book(self.root / "_toc.yml", self.root)
        self.assertEqual([p.rel for p in plan.parts], ["intro.Rmd"])


class TestOrderDetection(TempTree):
    def test_prefers_toc_yml(self):
        self.write("_toc.yml", "root: intro\n")
        self.write("index.rst", ".. toctree::\n\n   a\n")
        self.assertEqual(detect_order(self.root), "jupyter-book")

    def test_sphinx_needs_a_toctree_not_just_an_index(self):
        self.write("index.rst", "Just a title\n============\n")
        self.assertEqual(detect_order(self.root), "natural")

    def test_falls_back_to_natural(self):
        self.write("a.md", "a")
        self.assertEqual(detect_order(self.root), "natural")

    def test_build_plan_honours_explicit_order(self):
        self.write("_toc.yml", "root: intro\n")
        self.write("intro.md", "i")
        self.write("zz.md", "z")
        plan = build_plan(self.root, order="natural")
        self.assertEqual(plan.order, "natural")
        self.assertEqual(len(plan.parts), 2)


class TestNaturalPlan(TempTree):
    def test_include_and_exclude(self):
        for rel in ("keep/a.md", "keep/b.md", "drop/c.md"):
            self.write(rel, rel)
        plan = plan_natural(self.root, include=("keep/*",))
        self.assertEqual([p.rel for p in plan.parts], ["keep/a.md", "keep/b.md"])

        plan = plan_natural(self.root, include=("**/*",), exclude=("drop/*",))
        self.assertEqual([p.rel for p in plan.parts], ["keep/a.md", "keep/b.md"])

    def test_unsupported_extensions_ignored(self):
        self.write("a.md", "a")
        self.write("logo.png", "binary-ish")
        plan = plan_natural(self.root)
        self.assertEqual([p.rel for p in plan.parts], ["a.md"])


class TestRender(TempTree):
    def test_marker_and_caption_headings(self):
        self.write("_toc.yml", "root: intro\nparts:\n- caption: Tools\n  chapters:\n  - file: a\n")
        self.write("intro.md", "# Intro\n")
        self.write("a.md", "# A\n")
        plan = plan_jupyter_book(self.root / "_toc.yml", self.root)
        text = render(plan, title="My Book")

        self.assertTrue(text.startswith("# My Book"))
        self.assertIn("<!-- FILE: intro.md -->", text)
        self.assertIn("<!-- FILE: a.md -->", text)
        self.assertIn("# Part: Tools", text)
        # Order is preserved in the rendered text, not just in the plan.
        self.assertLess(text.index("<!-- FILE: intro.md -->"),
                        text.index("<!-- FILE: a.md -->"))

    def test_html_parts_are_converted_not_embedded_raw(self):
        """A docs site consolidated raw would put markup into the corpus."""
        self.write("index.html",
                   "<html><body><h1>Chapter One</h1><p>Prose body.</p></body></html>")
        plan = plan_natural(self.root, include=("*.html",))
        text = render(plan)
        self.assertIn("Chapter One", text)
        self.assertIn("Prose body.", text)
        self.assertNotIn("<body>", text)

    def test_caption_emitted_once_per_run(self):
        self.write("_toc.yml",
                   "root: r\nparts:\n- caption: One\n  chapters:\n  - file: a\n  - file: b\n")
        for rel in ("r.md", "a.md", "b.md"):
            self.write(rel, rel)
        text = render(plan_jupyter_book(self.root / "_toc.yml", self.root))
        self.assertEqual(text.count("# Part: One"), 1)


if __name__ == "__main__":
    unittest.main()
