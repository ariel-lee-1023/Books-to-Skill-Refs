"""Transport-level workflow tests with a simulated model, not persona quality claims."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / ('tools' if (ROOT / 'tools').exists() else 'scripts')
spec = importlib.util.spec_from_file_location('runner_under_test', HELPERS / 'evaluation_runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / 'skill'
        (self.skill / 'references').mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('Use the documented method and its conditions.')
        (self.skill / 'references/book.md').write_text('# Book\n## Mental Model\nPrerequisite: A.\n## Methods\n### Method X\nSteps: B. Exception: C. Source: chapter 2.\n### Other method\n' + ('Unrelated material. ' * 1000) + '\n## Decision Rules\nStop if D.\n')
        self.suite = {'version': 2, 'defined_before_extraction': True, 'baseline_prompt': 'Act as a domain expert.',
            'tasks': [{'id': phase + '-' + kind, 'partition': phase, 'group': phase + '-' + kind,
                'kind': kind, 'prompt': 'Apply a method to case ' + kind, 'criteria': {'condition': 'Check the qualification'},
                'qualification_criteria': ['condition'], 'references_required': kind == 'apply'}
                for phase in ('development', 'final') for kind in ('apply', 'inapplicable', 'disagreement', 'unsupported')]}
        self.suite_path = self.root / 'suite.json'
        self.suite_path.write_text(runner.dumps(self.suite))
        self.rubric = self.root / 'rubric.json'
        self.rubric.write_text(runner.dumps({t['id']: {'truth': 'GRADING SECRET'} for t in self.suite['tasks']}))
        self.calls = []

    def model(self, endpoint, model, messages, temperature):
        self.calls.append(copy.deepcopy(messages))
        if messages[0]['content'].startswith('Grade the anonymous'):
            task = json.loads(messages[1]['content'])
            value = {'criteria': {k: True for k in task['criteria']}, 'score': 2, 'rationale': 'Matches the supplied qualification.', 'disputed': False}
        elif 'Reference access is disabled.' in messages[0]['content'] or len(messages) > 2:
            value = {'action': 'answer', 'text': 'Method B applies when A holds, except C; stop if D.'}
        else:
            path = 'references/book.md'
            if '#L' in messages[0]['content']:
                catalog = json.loads(messages[0]['content'].split('Allowed references: ', 1)[1])
                path = next(k for k, row in catalog.items() if row['title'] == 'Method X')
            value = {'action': 'read', 'path': path}
        return {'text': runner.dumps(value), 'usage': {'total_tokens': len(runner.dumps(messages)) // 4}}

    def run_prediction(self, phase='development', targeted=True):
        return runner.predict(self.skill, self.suite_path, self.root / 'runs', 'https://example.invalid/chat/completions', 'mock-model', phase, targeted=targeted, client=self.model)

    def test_prediction_isolation_retrieval_capture_and_sealed_grade_export(self):
        pred = self.run_prediction()
        before = copy.deepcopy(self.calls)
        self.assertTrue(all('GRADING SECRET' not in runner.dumps(m) for m in before))
        self.assertEqual(sum(len(m) == 2 for m in before), 16)
        grade = runner.grade(pred, self.suite_path, self.rubric, self.root / 'runs', 'https://example.invalid', 'mock-grader', 'judge1', client=self.model)
        self.assertTrue(all('core_targeted' not in runner.dumps(m) for m in self.calls[len(before):]))
        exported = runner.export_books(pred, grade)
        whole = exported['runs']['core_references'][0]
        targeted = exported['runs']['core_targeted'][0]
        self.assertEqual(targeted['references_loaded'], ['references/book.md'])
        self.assertLess(sum(e['characters'] for e in targeted['retrievals']), sum(e['characters'] for e in whole['retrievals']))
        texts = [m[-1]['content'] for m in before if len(m) > 2 and '#L' in m[0]['content']]
        self.assertTrue(all('Prerequisite: A' in t and 'Exception: C' in t and 'Stop if D' in t for t in texts))
        self.assertTrue(runner.verify(pred).startswith('sha256:'))
        self.assertTrue(runner.verify(grade).startswith('sha256:'))

    def test_final_groups_cannot_be_retested_after_suite_edit(self):
        self.run_prediction('final')
        self.suite['tasks'][4]['prompt'] += ' edited'
        self.suite_path.write_text(runner.dumps(self.suite))
        before = len(self.calls)
        with self.assertRaises(FileExistsError):
            self.run_prediction('final')
        self.assertEqual(len(self.calls), before)

    def test_forbidden_reads_and_tampered_records_are_rejected(self):
        contents, _ = runner.snapshot(self.skill)
        index = runner.section_index(contents)
        for path, condition in (('../rubric.json', 'core_references'), ('references/book.md', 'baseline'),
                                ('references/book.md', 'core_targeted')):
            with self.assertRaises(ValueError):
                runner.read_reference(path, condition, contents, index)
        pred = self.run_prediction()
        target = pred / 'predictions.json'
        target.chmod(0o644)
        target.write_text('[]')
        with self.assertRaisesRegex(ValueError, 'record changed'):
            runner.verify(pred)

    def test_disputed_grades_require_append_only_human_review(self):
        pred = self.run_prediction(targeted=False)
        def disputed(*args):
            answer = self.model(*args)
            data = json.loads(answer['text']); data['disputed'] = True
            answer['text'] = runner.dumps(data)
            return answer
        grade = runner.grade(pred, self.suite_path, self.rubric, self.root / 'runs', 'https://example.invalid', 'mock', 'judge', client=disputed)
        with self.assertRaisesRegex(ValueError, 'disputed'):
            runner.export_books(pred, grade)
        original_hash = runner.verify(grade)
        rows = json.loads((grade / 'grades.json').read_text())
        corrections = {r['id'] + '/' + r['condition']: {'criteria': r['criteria'], 'score': 2, 'reviewer': 'human', 'rationale': 'Resolved against source.'} for r in rows}
        path = self.root / 'corrections.json'; path.write_text(runner.dumps(corrections))
        reviewed = runner.review(grade, path, self.root / 'runs')
        self.assertEqual(runner.verify(grade), original_hash)
        self.assertTrue(runner.export_books(pred, reviewed)['runs'])

    def test_grader_cannot_replace_saved_answer_or_retrievals(self):
        pred = self.run_prediction()
        def forged(*args):
            response = self.model(*args)
            value = json.loads(response['text'])
            value.update(answer='Invented answer', retrievals=[])
            response['text'] = runner.dumps(value)
            return response
        with self.assertRaisesRegex(ValueError, 'metadata'):
            runner.grade(pred, self.suite_path, self.rubric, self.root / 'runs',
                         'https://example.invalid', 'mock', 'judge', client=forged)
        grade = next((self.root / 'runs').glob('grade-*'))
        self.assertTrue(runner.verify(grade))
        self.assertEqual(json.loads((grade / 'status.json').read_text())['status'], 'failed')

    def test_credentials_in_endpoint_rejected_before_records_are_written(self):
        with self.assertRaisesRegex(ValueError, 'credentials'):
            runner.predict(self.skill, self.suite_path, self.root / 'runs',
                           'https://user:secret@example.invalid', 'mock', client=self.model)
        self.assertFalse((self.root / 'runs').exists())
        self.assertFalse(self.calls)

    def test_http_adapter_sends_stateless_messages_and_captures_usage(self):
        reply = {'choices': [{'message': {'content': '{"action":"answer","text":"ok"}'}}], 'usage': {'total_tokens': 10}}
        with patch.object(runner.urllib.request, 'urlopen', return_value=io.StringIO(json.dumps(reply))) as request:
            result = runner.http_client('https://example.invalid/chat/completions', 'model', [{'role': 'user', 'content': 'task'}], 0)
        payload = json.loads(request.call_args.args[0].data)
        self.assertNotIn('conversation_id', payload)
        self.assertEqual(result['usage']['total_tokens'], 10)
        self.assertEqual(payload['messages'], [{'role': 'user', 'content': 'task'}])

    def test_failed_prediction_is_sealed_and_cannot_be_graded(self):
        def invalid(*args):
            return {'text': '{"action":"read","path":"/etc/passwd"}'}
        with self.assertRaises(ValueError):
            runner.predict(self.skill, self.suite_path, self.root / 'runs', 'https://example.invalid', 'mock', client=invalid)
        pred = next((self.root / 'runs').glob('predict-*'))
        self.assertTrue(runner.verify(pred))
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            runner.grade(pred, self.suite_path, self.rubric, self.root / 'runs', 'https://example.invalid', 'mock', 'judge', client=self.model)


if __name__ == '__main__':
    unittest.main()
