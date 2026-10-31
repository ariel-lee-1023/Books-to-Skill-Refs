"""Tests for tools/validate_library.py — the SKILL.md contracts as assertions."""

import sys
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from reference_budget import measure_library, reference_cap  # noqa: E402
from validate_library import (  # noqa: E402
    detect_book_type,
    declared_depth,
    sections_of,
    validate,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOOD = FIXTURES / "good-library"
BAD = FIXTURES / "bad-library"
GOOD_SKILL = GOOD / ".agents" / "skills" / "test-persuasion-library"


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

    def test_project_wraps_one_discoverable_skill(self):
        self.assertEqual(
            self.rep.facts["skill_root"],
            ".agents/skills/test-persuasion-library",
        )
        self.assertTrue((GOOD_SKILL / "SKILL.md").is_file())
        self.assertTrue((GOOD_SKILL / "references").is_dir())
        self.assertEqual(
            sorted(p.name for p in (GOOD_SKILL / "references").glob("reference-*.md")),
            ["reference-carnegie-persuasion.md", "reference-cialdini-influence.md"],
        )

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

    def test_rejects_a_subdirectory_other_than_references(self):
        self.assertIn("only subdirectory", self.blob)
        self.assertIn("chapters", self.blob)

    def test_rejects_a_reference_file_left_at_the_skill_root(self):
        self.assertIn("reference-stray-book.md sits at the skill root", self.blob)

    def test_rejects_invalid_name_slug(self):
        self.assertIn("Bad_Library", self.blob)

    def test_rejects_directory_name_mismatch(self):
        self.assertIn("must match its skill directory name `bad-library`", self.blob)

    def test_rejects_short_description(self):
        self.assertIn("description", self.blob)

    def test_reports_router_link_to_missing_file(self):
        self.assertIn("reference-ghost.md", self.blob)

    def test_reports_orphan_reference_file(self):
        self.assertIn("references/reference-orphan-book.md is not linked", self.blob)

    def test_reports_single_book_topic_index_entry(self):
        self.assertIn("Solo Term", self.blob)

    def test_reports_missing_required_section(self):
        self.assertIn("Key Takeaways", self.blob)

    def test_reports_worked_example_at_reference_depth(self):
        self.assertIn("DEPTH=reference but contains a Worked Example", self.blob)


class TestExpertMaster(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "library"
        shutil.copytree(GOOD, self.project)
        self.master = (self.project / ".agents" / "skills" /
                       "test-persuasion-library" / "SKILL.md")

    def rewrite(self, old, new):
        text = self.master.read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.master.write_text(text.replace(old, new), encoding="utf-8")

    def test_expert_fixture_passes_and_budget_tools_agree(self):
        rep = validate(self.project)
        _, measured = measure_library(self.project)
        self.assertEqual(rep.errors, [], messages(rep))
        self.assertEqual(rep.warnings, [], messages(rep))
        self.assertEqual(rep.facts["master_capabilities"], 3)
        self.assertEqual(rep.facts["master_capabilities"], measured["capabilities"])
        self.assertEqual(rep.facts["master_budget"], measured["budget"])

    def test_trigger_links_still_detect_missing_and_orphan_sources(self):
        self.rewrite("references/reference-cialdini-influence.md",
                     "references/reference-missing.md")
        rep = validate(self.project)
        self.assertIn("reference-missing.md, which does not exist", messages(rep))
        self.assertIn("reference-cialdini-influence.md is not linked", messages(rep))

    def test_empty_core_is_rejected(self):
        text = self.master.read_text(encoding="utf-8")
        frontmatter = text[:text.index("\n---\n", 4) + 5]
        loading = text[text.index("## Loading depth"):]
        self.master.write_text(frontmatter + "\n# Expert\n\n" + loading, encoding="utf-8")
        self.assertIn("no expert core before Loading depth", messages(validate(self.project)))

    def test_legacy_router_remains_valid_with_migration_warning(self):
        self.rewrite("## Loading depth (host-agent note)", "## Which book for which job")
        rep = validate(self.project)
        self.assertEqual(rep.errors, [], messages(rep))
        self.assertIn("legacy book-router format", messages(rep))

    def test_optional_index_can_be_omitted(self):
        text = self.master.read_text(encoding="utf-8").split("## Cross-book Topic Index")[0]
        self.master.write_text(text, encoding="utf-8")
        rep = validate(self.project)
        self.assertEqual(rep.errors, [], messages(rep))
        self.assertEqual(rep.facts.get("topic_index_entries", 0), 0)


class TestPublishedRepository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "published-library"
        shutil.copytree(GOOD_SKILL, self.project)
        self.alias = self.project / ".agents" / "skills" / GOOD_SKILL.name
        self.alias.parent.mkdir(parents=True)
        self.alias.symlink_to("../..", target_is_directory=True)
        for name in ("README.md", "AGENTS.md", "LICENSE", ".gitignore"):
            (self.project / name).write_text("Project documentation\n", encoding="utf-8")
        ledger = self.project / "fidelity-ledger"
        ledger.mkdir()
        (ledger / "coverage.md").write_text("Source coverage\n", encoding="utf-8")

    def test_validates_canonical_content_and_matches_budget_tool(self):
        rep = validate(self.project, layout="published-repo")
        self.assertEqual(rep.errors, [], messages(rep))
        self.assertEqual(rep.warnings, [], messages(rep))
        self.assertEqual(rep.facts["skill_root"], ".")
        self.assertEqual(rep.facts["books"], 2)
        _, budget = measure_library(self.project)
        self.assertEqual(rep.facts["master_body_tokens"], budget["tokens"])

    def test_published_repo_allows_ci_and_attribution_scaffolding(self):
        workflow = self.project / ".github" / "workflows" / "validate.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: Validate\n")
        for name in ("CHANGELOG.md", "NOTICE.md"):
            (self.project / name).write_text("Project maintenance documentation\n")
        rep = validate(self.project, layout="published-repo")
        self.assertEqual(rep.errors, [], messages(rep))
        self.assertEqual(rep.warnings, [], messages(rep))
        (self.project / "chapters").mkdir()
        self.assertIn("chapters/", messages(validate(self.project, layout="published-repo")))
        self.assertTrue(validate(self.project).errors)

    def test_default_nested_contract_is_not_relaxed(self):
        self.assertTrue(validate(self.project).errors)

    def test_standard_mit_license_and_wrapping(self):
        license_text = (FIXTURES.parent.parent / "LICENSE").read_text()
        for body in (license_text, license_text.replace("\nof this software", " of this software")):
            with self.subTest(body=body):
                (self.project / "LICENSE").write_text(body)
                rep = validate(self.project, layout="published-repo")
                self.assertEqual(rep.errors, [], messages(rep))
                self.assertEqual(rep.facts["license"]["spdx_id"], "MIT")
                self.assertEqual(rep.facts["license"]["copyright_notices"],
                                 ["Copyright (c) 2026 Ariel Lee"])

    def test_mit_rejects_scope_notes_and_modified_terms(self):
        original = (FIXTURES.parent.parent / "LICENSE").read_text()
        invalid = {
            "appended scope": original + "\nScope: excludes source books.\n",
            "prepended scope": "Scope: original text only.\n\n" + original,
            "modified terms": original.replace("and/or sell", "but not sell"),
            "missing notice": original.replace("Copyright (c) 2026 Ariel Lee", ""),
        }
        for case, body in invalid.items():
            with self.subTest(case=case):
                (self.project / "LICENSE").write_text(body)
                rep = validate(self.project, layout="published-repo")
                self.assertIn("MIT LICENSE must contain only", messages(rep))

    def test_mit_preserves_other_owners_and_existing_notices(self):
        original = (FIXTURES.parent.parent / "LICENSE").read_text()
        (self.project / "LICENSE").write_text(original.replace(
            "Copyright (c) 2026 Ariel Lee",
            "Copyright (c) 2020-2025 Original Author\nCopyright (c) 2026 New Author"))
        rep = validate(self.project, layout="published-repo")
        self.assertEqual(rep.errors, [], messages(rep))
        self.assertEqual(len(rep.facts["license"]["copyright_notices"]), 2)

    def test_does_not_apply_mit_contract_to_other_licenses(self):
        (self.project / "LICENSE").write_text("BSD 3-Clause License\nExisting terms\n")
        rep = validate(self.project, layout="published-repo")
        self.assertEqual(rep.errors, [], messages(rep))
        self.assertNotIn("license", rep.facts)

    def test_rejects_missing_packaging_and_wrong_ledger_name(self):
        (self.project / "LICENSE").unlink()
        (self.project / "fidelity-ledger").rename(self.project / "docs")
        rep = validate(self.project, layout="published-repo")
        self.assertIn("nonempty LICENSE", messages(rep))
        self.assertIn("records in fidelity-ledger/", messages(rep))

    def test_rejects_nested_copy_instead_of_root_alias(self):
        self.alias.unlink()
        shutil.copytree(GOOD_SKILL, self.alias)
        self.assertIn("symlink resolving to the project root",
                      messages(validate(self.project, layout="published-repo")))

    def test_rejects_alias_to_another_repository(self):
        self.alias.unlink()
        self.alias.symlink_to(GOOD_SKILL.resolve(), target_is_directory=True)
        self.assertIn("symlink resolving to the project root",
                      messages(validate(self.project, layout="published-repo")))

    def test_retains_missing_and_orphan_reference_checks(self):
        master = self.project / "SKILL.md"
        master.write_text(master.read_text().replace("references/reference-cialdini-influence.md",
                                                     "references/reference-missing.md"))
        rep = validate(self.project, layout="published-repo")
        self.assertIn("reference-missing.md, which does not exist", messages(rep))
        self.assertIn("reference-cialdini-influence.md is not linked", messages(rep))


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
        self.assertEqual(reference_cap("reference", "text"), 8_500)
        self.assertEqual(reference_cap("study", "text"), 14_000)
        self.assertEqual(reference_cap("reference", "technical"), 11_000)
        self.assertEqual(reference_cap("study", "technical"), 19_500)

    def test_technical_caps_exceed_text_caps(self):
        for depth in ("reference", "study"):
            self.assertGreater(reference_cap(depth, "technical"),
                               reference_cap(depth, "text"))


class TestMissingLibrary(unittest.TestCase):
    def test_nonexistent_directory_errors(self):
        rep = validate(FIXTURES / "does-not-exist")
        self.assertTrue(rep.errors)

    def test_legacy_root_level_skill_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKILL.md").write_text("---\nname: legacy\n---\n", encoding="utf-8")
            rep = validate(root)
            self.assertIn("legacy root-level SKILL.md", messages(rep))


if __name__ == "__main__":
    unittest.main()
