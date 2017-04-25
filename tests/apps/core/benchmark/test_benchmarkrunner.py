from apps.core.benchmark import benchmarkrunner
import golem.task.taskbase
from golem.testutils import TempDirFixture
import mock
import time


class BenchmarkRunnerTest(TempDirFixture):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.benchmark = mock.MagicMock()
        self.instance = benchmarkrunner.BenchmarkRunner(
            task=golem.task.taskbase.Task(None, None),
            root_path=self.tempdir,
            success_callback=lambda: self._success(),
            error_callback=lambda *args: self._error(args),
            benchmark=self.benchmark,
        )

    def _success(self):
        """Instance success_callback."""
        pass

    def _error(self, *args):
        """Instance error_callback."""
        pass

    def test_task_thread_getter(self):
        """When docker_images is empty."""
        ctd = mock.MagicMock()
        ctd.docker_images = []
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

    def test_task_computed(self):
        """Processing of computed task."""
        task_thread = mock.MagicMock()

        # False result and False error_msg
        task_thread.result = None
        task_thread.error_msg = error_msg = None
        self.instance.error_callback = error_mock = mock.MagicMock()
        self.instance.task_computed(task_thread)
        error_mock.assert_called_once_with(error_msg)

        # False result and Non-False error_msg
        task_thread.result = None
        task_thread.error_msg = error_msg = "dummy error msg:%s" % (time.time(),)
        self.instance.error_callback = error_mock = mock.MagicMock()
        self.instance.task_computed(task_thread)
        error_mock.assert_called_once_with(error_msg)

        # empty result dict
        result_dict = {}
        task_thread.result = (result_dict, None)
        self.instance.task_computed(task_thread)
        self.assertEquals(self.benchmark.verify_result.call_count, 0)

        # result dict without res
        result_dict = {'a': None}
        task_thread.result = (result_dict, None)
        self.instance.task_computed(task_thread)
        self.assertEquals(self.benchmark.verify_result.call_count, 0)

        # result dict with data, but failed verification
        result_dict = {
            'data': object(),
        }
        task_thread.result = (result_dict, None)
        self.instance.start_time = time.time()
        self.instance.success_callback = mock.MagicMock()
        self.benchmark.verify_result.return_value = False
        self.instance.task_computed(task_thread)
        self.benchmark.verify_result.assert_called_once_with(result_dict['data'])
        self.assertEquals(self.instance.success_callback.call_count, 0)

        # result dict with data, and successful verification
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
        self.benchmark.verify_result.assert_called_once_with(result_dict['data'])
        self.instance.success_callback.assert_called_once_with(mock.ANY)

    def test_is_success(self):
        task_thread = mock.MagicMock()
        self.instance.start_time = time.time()
        self.instance.end_time = self.instance.start_time + 4
        self.benchmark.verify_result.return_value = True

        # Task thread result is not a tuple
        task_thread.result = 5
        assert not self.instance.is_success(task_thread)

        # Task thread result first arg is None
        task_thread.result = None, 30
        assert not self.instance.is_success(task_thread)

        # Task thread result first arg doesn't have data in dictionary
        task_thread.result = {'abc': 20}, 30
        assert not self.instance.is_success(task_thread)

        # Is success
        task_thread.result = {'data': "some data"}, 30
        assert self.instance.is_success(task_thread)

        # End time not measured
        self.instance.end_time = None
        assert not self.instance.is_success(task_thread)

        # Start time not measured
        self.instance.end_time = self.instance.start_time
        self.instance.start_time = None
        assert not self.instance.is_success(task_thread)

        # Not verified properly
        self.instance.start_time = self.instance.end_time - 5
        self.benchmark.verify_result.return_value = False
        assert not self.instance.is_success(task_thread)


class WrongTask(golem.task.taskbase.Task):
    def query_extra_data(self, perf_index):
        raise ValueError("Wrong task")


class BenchmarkRunnerWrongTaskTest(TempDirFixture):

    def test_run_with_error(self):
        benchmark = mock.MagicMock()
        instance = benchmarkrunner.BenchmarkRunner(
            task=WrongTask(None, None),
            root_path=self.tempdir,
            success_callback=mock.Mock(),
            error_callback=mock.Mock(),
            benchmark=benchmark,
        )
        instance.run()
        instance.success_callback.assert_not_called()
        instance.error_callback.assert_called_once()
