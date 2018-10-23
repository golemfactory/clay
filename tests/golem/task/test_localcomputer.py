import os
import stat
import unittest.mock as mock
from pathlib import Path

from golem_messages.message import ComputeTaskDef
from golem_messages import factories as msg_factories

from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import Task
from golem.tools.ci import ci_skip
from golem.tools.testdirfixture import TestDirFixture

from apps.blender.blenderenvironment import BlenderEnvironment


@ci_skip
@mock.patch.multiple(Task, __abstractmethods__=frozenset())
class TestLocalComputer(TestDirFixture):
    last_error = None
    last_result = None
    error_counter = 0
    success_counter = 0

    class TestTaskThread(object):
        def __init__(self, result, error_msg):
            self.result = result
            self.error = False
            self.error_msg = error_msg

    def test_computer(self):

        files = self.additional_dir_content([1])
        lc = LocalComputer(root_path=self.path,
                           success_callback=self._success_callback,
                           error_callback=self._failure_callback,
                           get_compute_task_def=self._get_bad_task_def)
        self.assertIsInstance(lc, LocalComputer)
        lc.run()
        assert self.last_error is not None
        assert self.last_result is None
        assert self.error_counter == 1

        lc = LocalComputer(root_path=self.path,
                           success_callback=self._success_callback,
                           error_callback=self._failure_callback,
                           get_compute_task_def=self._get_better_task_def,
                           resources=[],
                           additional_resources=files)
        lc.run()
        lc.tt.join(60.0)
        path_ = os.path.join(lc.test_task_res_path, os.path.basename(files[0]))
        assert os.path.isfile(path_)
        assert self.error_counter == 1
        assert self.success_counter == 1

        tt = self.TestTaskThread({'data': "some data"}, "some error")
        lc.task_computed(tt)
        assert self.last_result == {"data": "some data"}
        assert self.last_result != "some error"
        assert self.error_counter == 1
        assert self.success_counter == 2

        tt = self.TestTaskThread({}, "some error")
        lc.task_computed(tt)
        assert self.last_error == "some error"
        assert self.error_counter == 2
        assert self.success_counter == 2

        tt = self.TestTaskThread({}, None)
        lc.task_computed(tt)
        assert self.last_error is None
        assert self.error_counter == 3
        assert self.success_counter == 2

        tt = self.TestTaskThread({'data': "some data"}, None)
        tt.error = True
        lc.task_computed(tt)
        assert self.last_error is None
        assert self.error_counter == 4
        assert self.success_counter == 2

    def test_prepare_resources_onerror(self):

        def remove_permissions(_path):
            perms = stat.S_IMODE(os.lstat(_path).st_mode)
            os.chmod(_path, perms & ~stat.S_IWUSR & ~stat.S_IWRITE)

        def reset_permissions(_path):
            perms = stat.S_IMODE(os.lstat(_path).st_mode)
            os.chmod(_path, perms | stat.S_IWUSR | stat.S_IWRITE)

        lc = LocalComputer(root_path=self.path,
                           success_callback=self._success_callback,
                           error_callback=self._failure_callback,
                           get_compute_task_def=self._get_better_task_def)

        task_dir = lc.dir_manager.get_task_test_dir("")
        resource_dir = os.path.join(self.path, 'subdir')
        existing_file = os.path.join(task_dir, 'file')

        os.makedirs(resource_dir)
        resources = [os.path.join(resource_dir, 'file')]

        Path(existing_file).touch()
        for resource in resources:
            Path(resource).touch()

        remove_permissions(existing_file)

        lc._prepare_resources(resources)

        Path(existing_file).touch()
        remove_permissions(existing_file)

        with mock.patch('shutil.os.unlink', side_effect=OSError):
            with self.assertRaises(OSError):
                lc._prepare_resources(resources)

        reset_permissions(existing_file)

    def _get_bad_task_def(self):
        ctd = ComputeTaskDef(
            task_type='Blender',
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
        )
        return ctd

    def _get_better_task_def(self):
        ctd = ComputeTaskDef(
            task_type='Blender',
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
        )
        ctd['docker_images'] = [
            di.to_dict() for di in BlenderEnvironment().docker_images
        ]
        return ctd

    def _success_callback(self, result, time_spent):
        self.last_result = result
        self.success_counter += 1

    def _failure_callback(self, error):
        self.last_error = error
        self.error_counter += 1
