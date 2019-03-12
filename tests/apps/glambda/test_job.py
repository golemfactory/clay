from contextlib import ExitStack
from json import dumps
from unittest import TestCase
from mock import mock_open, patch

from apps.glambda.resources.scripts import job
from apps.glambda.task.glambdatask import GLambdaTask


class GLambdaJobTestCase(TestCase):
    def test_job_success(self):

        def test_task(args):
            return 1 + args['b']

        test_args = {
            'b': 2
        }

        serializer = GLambdaTask.PythonObjectSerializer()

        params = {
            'method': serializer.serialize(test_task),
            'args': serializer.serialize(test_args)
        }

        env = {
            'OUTPUT_DIR': '',
        }

        with ExitStack() as stack:
            mocked_file = stack.enter_context(
                patch('builtins.open', mock_open(read_data=dumps(params))),
            )
            stack.enter_context(patch.dict('os.environ', env))
            job.run_job()

        expected_result = {
            'data': 3
        }

        file_handle = mocked_file.return_value.__enter__.return_value
        file_handle.write.assert_called_with(dumps(expected_result))


    def test_job_invalid_input_task(self):

        test_task = None

        test_args = {
            'b': 2
        }

        serializer = GLambdaTask.PythonObjectSerializer()

        params = {
            'method': serializer.serialize(test_task),
            'args': serializer.serialize(test_args)
        }

        env = {
            'OUTPUT_DIR': '',
        }

        with ExitStack() as stack:
            mocked_file = stack.enter_context(
                patch('builtins.open', mock_open(read_data=dumps(params))),
            )
            stack.enter_context(patch.dict('os.environ', env))
            job.run_job()

        expected_result = {"error": "<class \'TypeError\'>:\'NoneType\' "
                                    "object is not callable"}

        file_handle = mocked_file.return_value.__enter__.return_value
        file_handle.write.assert_called_with(dumps(expected_result))


    def test_job_non_existent_input_arguments(self):
        def test_task(args):
            return 1 + args['b']

        test_args = {}

        serializer = GLambdaTask.PythonObjectSerializer()

        params = {
            'method': serializer.serialize(test_task),
            'args': serializer.serialize(test_args)
        }

        env = {
            'OUTPUT_DIR': '',
        }

        with ExitStack() as stack:
            mocked_file = stack.enter_context(
                patch('builtins.open', mock_open(read_data=dumps(params))),
            )
            stack.enter_context(patch.dict('os.environ', env))
            job.run_job()

        expected_result = {"error": "<class \'KeyError\'>:\'b\'"}

        file_handle = mocked_file.return_value.__enter__.return_value
        file_handle.write.assert_called_with(dumps(expected_result))


    def test_job_raises_exception(self):
        def test_task(args): # pylint: disable=unused-argument
            raise ValueError('my error!')

        test_args = {}

        serializer = GLambdaTask.PythonObjectSerializer()

        params = {
            'method': serializer.serialize(test_task),
            'args': serializer.serialize(test_args)
        }

        env = {
            'OUTPUT_DIR': '',
        }

        with ExitStack() as stack:
            mocked_file = stack.enter_context(
                patch('builtins.open', mock_open(read_data=dumps(params))),
            )
            stack.enter_context(patch.dict('os.environ', env))
            job.run_job()

        expected_result = {"error": "<class \'ValueError\'>:my error!"}

        file_handle = mocked_file.return_value.__enter__.return_value
        file_handle.write.assert_called_with(dumps(expected_result))


    def test_job_empty_task(self):
        def test_task(args): # pylint: disable=unused-argument
            pass

        test_args = {}

        serializer = GLambdaTask.PythonObjectSerializer()

        params = {
            'method': serializer.serialize(test_task),
            'args': serializer.serialize(test_args)
        }

        env = {
            'OUTPUT_DIR': '',
        }

        with ExitStack() as stack:
            mocked_file = stack.enter_context(
                patch('builtins.open', mock_open(read_data=dumps(params))),
            )
            stack.enter_context(patch.dict('os.environ', env))
            job.run_job()

        expected_result = {"data": None}

        file_handle = mocked_file.return_value.__enter__.return_value
        file_handle.write.assert_called_with(dumps(expected_result))
