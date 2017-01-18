from apps.core.benchmark import benchmarkrunner
import golem.task.taskbase
from golem.testutils import TempDirFixture
import mock
import time
import unittest

class BenchmarkRunnerTest(TempDirFixture):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.benchmark = mock.MagicMock()
        self.instance = benchmarkrunner.BenchmarkRunner(
            task=golem.task.taskbase.Task(None, None),
            root_path=self.tempdir,
            success_callback=lambda: self._success(),
            error_callback=lambda: self._error(),
            benchmark=self.benchmark,
        )

    def _success(self):
        """Instance success_callback."""
        pass

    def _error(self):
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
        with mock.patch.multiple(self.instance, start=mock.DEFAULT, tt=None) as values:
            self.instance.run()
            values['start'].assert_called_once_with()

        with mock.patch.multiple(self.instance, start=mock.DEFAULT, tt=mock.DEFAULT) as values:
            self.instance.run()
            values['start'].assert_called_once_with()
            values['tt'].join.assert_called_once_with()

    def test_task_computed(self):
        """Processing of computed task."""
        task_thread = mock.MagicMock()
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
