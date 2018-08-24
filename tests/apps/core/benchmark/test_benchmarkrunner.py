import time
import unittest.mock as mock

from apps.core.benchmark import benchmarkrunner
from golem.task.taskbase import Task
from golem.testutils import TempDirFixture


class DummyTask(Task):
    def initialize(self, dir_manager):
        pass

    def query_extra_data(self, perf_index, num_cores, node_id, node_name):
        pass

    def short_extra_data_repr(self, extra_data):
        pass

    def needs_computation(self):
        pass

    def finished_computation(self):
        pass

    def computation_finished(self, subtask_id, task_result, result_type,
                             verification_finished):
        pass

    def computation_failed(self, subtask_id):
        pass

    def verify_subtask(self, subtask_id):
        pass

    def verify_task(self):
        pass

    def get_total_tasks(self):
        pass

    def get_active_tasks(self):
        pass

    def get_tasks_left(self):
        pass

    def restart(self):
        pass

    def restart_subtask(self, subtask_id):
        pass

    def abort(self):
        pass

    def get_progress(self):
        pass

    def update_task_state(self, task_state):
        pass

    def get_trust_mod(self, subtask_id):
        pass

    def add_resources(self, resources):
        pass

    def copy_subtask_results(self, subtask_id, old_subtask_info, results):
        pass

    def should_accept_client(self, node_id):
        pass


class BenchmarkRunnerFixture(TempDirFixture):
    def _success(self):
        """Instance success_callback."""
        pass

    def _error(self, *args):
        """Instance error_callback."""
        pass

    def setUp(self):
        super().setUp()
        self.benchmark = mock.MagicMock()
        self.instance = benchmarkrunner.BenchmarkRunner(
            task=DummyTask(None, None, None),
            root_path=self.tempdir,
            success_callback=self._success,
            error_callback=self._error,
            benchmark=self.benchmark,
        )


class TestBenchmarkRunner(BenchmarkRunnerFixture):
    def test_task_thread_getter(self):
        """When docker_images is empty."""
        ctd = {}
        ctd['docker_images'] = []
        with self.assertRaises(Exception):
            self.instance._get_task_thread(ctd)

    def test_tt_cases(self):
        """run() with different tt values."""
        with mock.patch.multiple(self.instance, run=mock.DEFAULT, tt=None) as values:
            self.instance.run()
            values['run'].assert_called_once_with()

        with mock.patch.multiple(self.instance, tt=mock.DEFAULT) as values:
            self.instance.run()

    def test_task_computed_immidiately(self):
        """Special case when start_time and stop_time are identical.
        It's higly unprobable on *NIX but happens a lot on Windows
        wich has lower precision of time.time()."""

        task_thread = mock.MagicMock()
        task_thread.error = False

        # result dict with data, and successful verification
        result_dict = {
            'data': object(),
        }
        task_thread.result = (result_dict, None)
        try:
            self.instance.__class__.start_time = property(lambda self: self.end_time)
            self.instance.success_callback = mock.MagicMock()
            self.benchmark.verify_result.return_value = True
            self.benchmark.normalization_constant = 1
            self.instance.task_computed(task_thread)
            self.instance.success_callback.assert_called_once_with(mock.ANY)
        finally:
            del self.instance.__class__.start_time

        # now try what happens when user moves the clock back!
        try:
            self.instance.__class__.start_time = property(lambda self: self.end_time+10)
            self.instance.success_callback = mock.MagicMock()
            self.benchmark.verify_result.return_value = True
            self.benchmark.normalization_constant = 1
            self.instance.task_computed(task_thread)
            self.instance.success_callback.assert_called_once_with(mock.ANY)
        finally:
            del self.instance.__class__.start_time

    def test_task_computed_false_result_and_false_error_msg(self):
        task_thread = mock.MagicMock()
        task_thread.result = None
        task_thread.error = False
        task_thread.error_msg = error_msg = None
        self.instance.error_callback = error_mock = mock.MagicMock()
        self.instance.task_computed(task_thread)
        error_mock.assert_called_once_with(error_msg)

    def test_task_computed_false_resulst_and_non_false_error_msg(self):
        task_thread = mock.MagicMock()
        task_thread.result = None
        task_thread.error = True
        task_thread.error_msg = error_msg = \
            "dummy error msg:{}".format(time.time())
        self.instance.error_callback = error_mock = mock.MagicMock()
        self.instance.task_computed(task_thread)
        error_mock.assert_called_once_with(error_msg)

    def test_task_computed_empty_result_dict(self):
        task_thread = mock.MagicMock()
        task_thread.error = False
        result_dict = {}
        task_thread.result = (result_dict, None)
        self.instance.task_computed(task_thread)
        self.assertEqual(self.benchmark.verify_result.call_count, 0)

    def test_task_computed_result_dict_without_res(self):
        task_thread = mock.MagicMock()
        task_thread.error = False
        result_dict = {'a': None}
        task_thread.result = (result_dict, None)
        self.instance.task_computed(task_thread)
        self.assertEqual(self.benchmark.verify_result.call_count, 0)

    def test_task_computed_result_dict_with_data_but_failed_verification(self):
        task_thread = mock.MagicMock()
        task_thread.error = False
        result_dict = {
            'data': object(),
        }
        task_thread.result = (result_dict, None)
        self.instance.start_time = time.time()
        self.instance.success_callback = mock.MagicMock()
        self.benchmark.verify_result.return_value = False
        self.instance.task_computed(task_thread)
        self.benchmark.verify_result.assert_called_once_with(
            result_dict['data'])
        self.assertEqual(self.instance.success_callback.call_count, 0)

    def test_task_computed_result_dict_with_data_and_successful_verification(
            self):
        task_thread = mock.MagicMock()
        task_thread.error = False
        result_dict = {
            'data': object(),
        }
        task_thread.result = (result_dict, None)
        self.instance.start_time = time.time()
        self.instance.success_callback = mock.MagicMock()
        self.benchmark.verify_result.reset_mock()
        self.benchmark.verify_result.return_value = True
        self.benchmark.normalization_constant = 1
        self.instance.task_computed(task_thread)
        self.benchmark.verify_result.assert_called_once_with(
            result_dict['data'])
        self.instance.success_callback.assert_called_once_with(mock.ANY)


class TestBenchmarkRunnerIsSuccess(BenchmarkRunnerFixture):
    def setUp(self):
        super().setUp()
        self.task_thread = mock.MagicMock()
        self.task_thread.error = False
        self.instance.start_time = time.time()
        self.instance.end_time = self.instance.start_time + 4
        self.benchmark.verify_result.return_value = True

    def test_result_is_not_a_tuple(self):
        self.task_thread.result = 5
        assert not self.instance.is_success(self.task_thread)

    def test_result_first_arg_is_none(self):
        self.task_thread.result = None, 30
        assert not self.instance.is_success(self.task_thread)

    def test_result_first_arg_doesnt_have_data_in_dictionary(self):
        self.task_thread.result = {'abc': 20}, 30
        assert not self.instance.is_success(self.task_thread)

    def test_is_success(self):
        self.task_thread.result = {'data': "some data"}, 30
        assert self.instance.is_success(self.task_thread)

    def test_end_time_not_measured(self):
        self.instance.end_time = None
        assert not self.instance.is_success(self.task_thread)

    def test_start_time_not_measured(self):
        self.instance.end_time = self.instance.start_time
        self.instance.start_time = None
        assert not self.instance.is_success(self.task_thread)

    def test_not_verified_properly(self):
        self.instance.start_time = self.instance.end_time - 5
        self.benchmark.verify_result.return_value = False
        assert not self.instance.is_success(self.task_thread)


class WrongTask(DummyTask):
    def query_extra_data(self, perf_index, num_cores, node_id, node_name):
        raise ValueError("Wrong task")


class BenchmarkRunnerWrongTaskTest(TempDirFixture):

    def test_run_with_error(self):
        benchmark = mock.MagicMock()
        instance = benchmarkrunner.BenchmarkRunner(
            task=WrongTask(None, None, None),
            root_path=self.tempdir,
            success_callback=mock.Mock(),
            error_callback=mock.Mock(),
            benchmark=benchmark,
        )
        instance.run()
        instance.success_callback.assert_not_called()
        instance.error_callback.assert_called_once()
