import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import acceptance_suite
import test_evaluation_runner as helpers


class FinalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.f = helpers.RunnerTests('test_prediction_isolation_retrieval_capture_and_sealed_grade_export')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def run_final(self):
        f, runner = self.f, helpers.runner
        pred = f.run_prediction('final')
        grade = runner.grade(pred, f.suite_path, f.rubric, f.root / 'runs', 'https://example.invalid', 'mock', 'judge', client=f.model)
        return pred, runner.export_books(pred, grade)

    def test_verified_final_run_and_targeted_metrics(self):
        pred, records = self.run_final()
        f, runner = self.f, helpers.runner
        report = acceptance_suite.validate(f.suite, records, f.skill, runner.digest(f.suite_path.read_bytes()), runner.verify(pred))
        self.assertTrue(report['passed'])
        self.assertTrue(report['independent_final'])
        self.assertEqual(report['retrieval_experiment']['core_targeted']['missed_qualifications'], 0)
        self.assertGreater(report['retrieval_experiment']['core_references']['retrieved_characters'], report['retrieval_experiment']['core_targeted']['retrieved_characters'])

    def test_operator_claim_cannot_substitute_for_verified_final_records(self):
        _, records = self.run_final()
        with self.assertRaisesRegex(ValueError, 'verified prediction'):
            acceptance_suite.validate(self.f.suite, records, self.f.skill, helpers.runner.digest(self.f.suite_path.read_bytes()))

    def test_targeted_lost_condition_is_reported_even_if_whole_book_passes(self):
        pred, records = self.run_final()
        records['runs']['core_targeted'][0]['criteria']['condition'] = False
        report = acceptance_suite.validate(self.f.suite, records, self.f.skill, helpers.runner.digest(self.f.suite_path.read_bytes()), helpers.runner.verify(pred))
        self.assertEqual(report['retrieval_experiment']['core_targeted']['missed_qualifications'], 1)
        self.assertTrue(report['passed'])

    def test_related_scenarios_cannot_cross_development_final_partitions(self):
        self.f.suite['tasks'][-1]['group'] = self.f.suite['tasks'][0]['group']
        with self.assertRaisesRegex(ValueError, 'crosses partitions'):
            helpers.runner.validate_tasks(self.f.suite, 'final')


if __name__ == '__main__':
    unittest.main()
