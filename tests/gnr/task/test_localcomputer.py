from os import path

from mock import Mock

from golem.task.taskbase import Task, ComputeTaskDef
from golem.tools.testdirfixture import TestDirFixture

from gnr.docker_environments import BlenderEnvironment
from gnr.task.localcomputer import LocalComputer


class TestLocalComputer(TestDirFixture):
    last_error = None
    last_result = None

    class TestTaskThread(object):
        def __init__(self, result, error_msg):
            self.result = result
            self.error_msg = error_msg

    def test_computer(self):
        files = self.additional_dir_content([1])
        task = Task(Mock(), Mock())
        lc = LocalComputer(task, self.path, self._success_callback, self._failure_callback, self._get_bad_task_def)
        self.assertIsInstance(lc, LocalComputer)
        lc.run()
        assert self.last_error is not None
        assert self.last_result is None

        lc = LocalComputer(task, self.path, self._success_callback, self._failure_callback, self._get_better_task_def,
                           use_task_resources=False, additional_resources=files)
        lc.run()
        path_ = path.join(lc.test_task_res_path, path.basename(files[0]))
        assert path.isfile(path_)

        tt = self.TestTaskThread({'data': "some data"}, "some error")
        lc.task_computed(tt)
        assert self.last_result == {"data": "some data"}
        assert self.last_result != "some error"
        tt = self.TestTaskThread({}, "some error")
        lc.task_computed(tt)
        assert self.last_error == "some error"

        tt = self.TestTaskThread({}, None)
        lc.task_computed(tt)
        assert self.last_error is None

    def _get_bad_task_def(self):
        ctd = ComputeTaskDef()
        return ctd

    def _get_better_task_def(self):
        ctd = ComputeTaskDef()
        ctd.docker_images = BlenderEnvironment().docker_images
        return ctd

    def _success_callback(self, result):
        self.last_result = result

    def _failure_callback(self, error):
        self.last_error = error

