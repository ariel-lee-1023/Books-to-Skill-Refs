import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / 'tools' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


acceptance = module('acceptance_suite')
reading = module('reading_audit')


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'references').mkdir()
        (self.root / 'SKILL.md').write_text('Expert core')
        (self.root / 'references/book.md').write_text('Methods and their limits.')
        self.suite = {'version': 1, 'defined_before_extraction': True, 'tasks': [
            {'id': kind, 'kind': kind, 'prompt': 'A concrete task: ' + kind, 'criteria': {'judgment': 'Demonstrates the specified decision.'}, 'references_required': kind == 'apply'} for kind in sorted(acceptance.KINDS)]}
        self.results = {'suite_hash': 'frozen', 'content_hash': acceptance.runtime_hash(self.root), 'model': 'fixture', 'settings': 'temperature 0', 'baseline_prompt': 'Act as a subject expert.', 'runs': {}}
        for condition in acceptance.CONDITIONS:
            self.results['runs'][condition] = [{'id': t['id'], 'fresh_context': True, 'answer': 'Recorded answer.', 'criteria': {'judgment': condition != 'baseline'}, 'rationale': 'Observable criterion judgment.', 'references_loaded': ['references/book.md'] if condition == 'core_references' and t['references_required'] else []} for t in self.suite['tasks']]

    def test_computes_added_value_and_checks_retrieval(self):
        result = acceptance.validate(self.suite, self.results, self.root, 'frozen')
        self.assertTrue(result['passed'])
        self.assertEqual(result['core_gain'], 4)
        self.results['runs']['core_references'][0]['references_loaded'] = []
        with self.assertRaisesRegex(ValueError, 'did not load'):
            acceptance.validate(self.suite, self.results, self.root, 'frozen')

    def test_suite_without_reference_dependent_task_is_rejected(self):
        for task in self.suite['tasks']:
            task['references_required'] = False
        for row in self.results['runs']['core_references']:
            row['references_loaded'] = []
        with self.assertRaisesRegex(ValueError, 'at least one reference-dependent task'):
            acceptance.validate(self.suite, self.results, self.root, 'frozen')

    def test_incidental_retrieval_does_not_replace_reference_dependent_task(self):
        for task in self.suite['tasks']:
            task['references_required'] = False
        # Retain the actual retrieval on the apply task, but no task requires it.
        with self.assertRaisesRegex(ValueError, 'at least one reference-dependent task'):
            acceptance.validate(self.suite, self.results, self.root, 'frozen')

    def test_changed_runtime_or_suite_requires_rerun(self):
        with self.assertRaisesRegex(ValueError, 'suite hash'):
            acceptance.validate(self.suite, self.results, self.root, 'changed')
        (self.root / 'references/book.md').write_text('Changed method.')
        with self.assertRaisesRegex(ValueError, 'runtime hash'):
            acceptance.validate(self.suite, self.results, self.root, 'frozen')

    def test_missing_criterion_and_failed_behavior_do_not_pass(self):
        altered = copy.deepcopy(self.results)
        altered['runs']['core_references'][0]['criteria'] = {}
        with self.assertRaises(ValueError):
            acceptance.validate(self.suite, altered, self.root, 'frozen')
        altered = copy.deepcopy(self.results)
        altered['runs']['core_references'][0]['criteria']['judgment'] = False
        self.assertFalse(acceptance.validate(self.suite, altered, self.root, 'frozen')['passed'])


class ReadingTests(unittest.TestCase):
    def test_unique_coverage_and_repeated_reading_are_separate(self):
        ledger = {'sources': {'book': {'lines': 100, 'output_budget': 10}}, 'reads': [
            {'source': 'book', 'start': 1, 'end': 20, 'tokens': 25, 'reason': 'initial'},
            {'source': 'book', 'start': 15, 'end': 30, 'tokens': 30, 'reason': 'verification', 'question': 'Does exception apply?', 'resolution': 'Only with condition X.'}]}
        report = reading.summarize(ledger)['book']
        self.assertEqual(report['unique_lines'], 30)
        self.assertEqual(report['repeated_lines'], 6)
        self.assertEqual(report['input_tokens'], 55)
        self.assertTrue(report['budget_alert'])
        self.assertEqual(report['unresolved'], [])

    def test_unseen_reading_can_exceed_alert_without_rereading(self):
        report = reading.summarize({'sources': {'b': {'lines': 100, 'output_budget': 1}}, 'reads': [
            {'source': 'b', 'start': 1, 'end': 80, 'tokens': 10, 'reason': 'audit'}]})['b']
        self.assertTrue(report['budget_alert'])
        self.assertEqual(report['repeated_lines'], 0)


if __name__ == '__main__':
    unittest.main()
