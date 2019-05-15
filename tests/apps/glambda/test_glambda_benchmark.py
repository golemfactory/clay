from unittest import TestCase

from mock import mock_open, patch

from apps.glambda.benchmark.benchmark import GLambdaTaskBenchmark
from apps.glambda.task.glambdatask import GLambdaTask


class GLambdaBenchmarkTestCase(TestCase):
    def setUp(self):
        self.benchmark = GLambdaTaskBenchmark()

    def test_definition(self):
        task_def = self.benchmark.task_definition
        self.assertEqual(task_def.subtasks_count, 1)
        self.assertCountEqual(
            task_def.resources,
            []
        )

        self.assertEqual(task_def.options.outputs,
                         ['result.json', 'stdout.log', 'stderr.log'])
        self.assertEqual(task_def.options.verification, {
            'type': GLambdaTask.VerificationMethod.NO_VERIFICATION})

    def test_verification(self):
        self.assertFalse(
            self.benchmark.verify_result(['no', 'expected', 'output', 'file'])
        )

        with patch('builtins.open', mock_open(read_data='wrong_content')):
            self.assertFalse(
                self.benchmark.verify_result(['/path/result.json']))

        good_content = GLambdaTaskBenchmark.EXPECTED_FILE_OUTPUT
        with patch('builtins.open', mock_open(read_data=good_content)):
            self.assertTrue(
                self.benchmark.verify_result(['/path/to/result.json']))
