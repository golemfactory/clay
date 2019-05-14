from contextlib import ExitStack
import json
from json import dumps
import sys
from unittest import TestCase

import pytest
from mock import mock_open, patch

if not sys.platform.startswith('linux'):
    pytest.skip('skipping linux-only tests', allow_module_level=True)

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
        json_str = file_handle.write.call_args[0][0]
        json_obj = json.loads(json_str)
        assert json_obj['data'] == 3
        assert 'usage' in json_obj

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

        file_handle = mocked_file.return_value.__enter__.return_value
        json_str = file_handle.write.call_args[0][0]
        json_obj = json.loads(json_str)
        assert json_obj['data'] is None
        assert 'usage' in json_obj
