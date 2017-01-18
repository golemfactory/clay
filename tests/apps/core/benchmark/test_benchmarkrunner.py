from apps.core.benchmark import benchmarkrunner
import golem.task.taskbase
from golem.testutils import TempDirFixture
import mock
import unittest

class BenchmarkRunnerTest(TempDirFixture):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.instance = benchmarkrunner.BenchmarkRunner(
            task=golem.task.taskbase.Task(None, None),
            root_path=self.tempdir,
            success_callback=lambda: self._success(),
            error_callback=lambda: self._error(),
            benchmark=None,
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

    def test_empty_tt(self):
        """run() wher tt is None."""
        with mock.patch.multiple(self.instance, start=mock.DEFAULT, tt=None):
            self.instance.run()
