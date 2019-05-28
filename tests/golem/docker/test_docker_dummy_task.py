import logging
from pathlib import Path

import os
from os import path
from unittest import mock, skip
from unittest.mock import Mock
from twisted.internet.defer import Deferred

from apps.dummy.task.dummytask import DummyTaskBuilder, DummyTask
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path
from golem.core.deferred import sync_wait
from golem.core.fileshelper import find_file_with_ext
from golem.docker.manager import DockerManager
from golem.resource.dirmanager import symlink_or_copy, \
    rmlink_or_rmtree
from golem.task.localcomputer import LocalComputer
from golem.task.taskcomputer import DockerTaskThread
from golem.task.tasktester import TaskTester
from golem.tools.ci import ci_skip
from golem.tools.testwithreactor import TestWithReactor

from .test_docker_task import DockerTaskTestCase

# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")

WAIT_TIMEOUT = 60


@skip("Disabled because it leaves zombie processes #4165")
class TestDockerDummyTask(
        DockerTaskTestCase[DummyTask, DummyTaskBuilder], TestWithReactor
):

    TASK_FILE = "docker-dummy-test-task.json"
    TASK_CLASS = DummyTask
    TASK_BUILDER_CLASS = DummyTaskBuilder

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data_dir = os.path.join(get_golem_path(),
                                "apps",
                                "dummy",
                                "test_data")
        code_dir = os.path.join(get_golem_path(),
                                "apps",
                                "dummy",
                                "resources",
                                "code_dir")
        cls.test_tmp = os.path.join(get_golem_path(),
                                    "apps",
                                    "dummy",
                                    "test_tmp")
        os.mkdir(cls.test_tmp)

        cls.code_link = os.path.join(cls.test_tmp, "code")
        cls.data_link = os.path.join(cls.test_tmp, "data")

        symlink_or_copy(code_dir, cls.code_link)
        symlink_or_copy(data_dir, cls.data_link)
        DockerManager.install(ClientConfigDescriptor())
        cls.TASK_CLASS.VERIFICATION_QUEUE.resume()

    @classmethod
    def tearDownClass(cls):
        rmlink_or_rmtree(cls.code_link)
        rmlink_or_rmtree(cls.data_link)
        os.rmdir(cls.test_tmp)
        super().tearDownClass()

    def _extract_results(self, computer: LocalComputer, subtask_id: str) \
            -> Path:
        """
        Since the local computer uses temp dir, you should copy files out of
        there before you use local computer again.
        Otherwise the files would get overwritten (during the verification
        process).
        This is a problem only in test suite. In real life provider and
        requestor are separate machines
        """
        assert isinstance(computer.tt, DockerTaskThread)

        dirname = path.dirname(computer.tt.result['data'][0])
        result = Path(find_file_with_ext(dirname, [".result"]))
        self.assertTrue(result.is_file())

        new_file_dir = result.parent / subtask_id
        new_result = self._copy_file(result, new_file_dir / "new.result")

        return new_result

    @mock.patch('golem.core.common.deadline_to_timeout')
    def test_dummy_real_task(self, mock_dtt):
        mock_dtt.return_value = 1.0

        task = self._get_test_task()
        ctd = task.query_extra_data(1.0).ctd

        print(ctd)
        print(type(ctd))

        d = Deferred()

        computer = LocalComputer(
            root_path=self.tempdir,
            success_callback=Mock(),
            error_callback=Mock(),
            compute_task_def=ctd,
            resources=task.task_resources,
        )

        computer.run()
        computer.tt.join()

        output = self._extract_results(computer, ctd['subtask_id'])

        def success(*args, **kwargs):
            # pylint: disable=unused-argument
            is_subtask_verified = task.verify_subtask(ctd['subtask_id'])
            self.assertTrue(is_subtask_verified)
            self.assertEqual(task.num_tasks_received, 1)
            d.callback(True)

        # assert good results - should pass
        self.assertEqual(task.num_tasks_received, 0)
        task.computation_finished(ctd['subtask_id'], [str(output)],
                                  verification_finished=success)

        sync_wait(d, WAIT_TIMEOUT)

        b = Deferred()

        def failure(*args, **kwargs):
            # pylint: disable=unused-argument
            self.assertFalse(task.verify_subtask(ctd['subtask_id']))
            self.assertEqual(task.num_tasks_received, 1)
            b.callback(True)

        # assert bad results - should fail
        bad_output = output.parent / "badfile.result"
        ctd = task.query_extra_data(10000.).ctd
        task.computation_finished(ctd['subtask_id'], [str(bad_output)],
                                  verification_finished=failure)
        sync_wait(b, WAIT_TIMEOUT)

    def test_dummytask_TaskTester_should_pass(self):
        task = self._get_test_task()

        computer = TaskTester(task, self.tempdir, Mock(), Mock())
        computer.run()
        computer.tt.join(float(WAIT_TIMEOUT))

        dirname = os.path.dirname(computer.tt.result[0]['data'][0])
        result = find_file_with_ext(dirname, [".result"])

        assert path.isfile(result)

    def test_dummy_subtask(self):
        task = self._get_test_task()
        task_thread = self._run_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertEqual(task_thread.error_msg, '')

        # Check the number and type of result files:
        result = task_thread.result
        self.assertGreaterEqual(len(result["data"]), 3)
        self.assertTrue(any(path.basename(f) == DockerTaskThread.STDOUT_FILE
                            for f in result["data"]))
        self.assertTrue(any(path.basename(f) == DockerTaskThread.STDERR_FILE
                            for f in result["data"]))
        self.assertTrue(any(f.endswith(DummyTask.RESULT_EXT) and "out" in f
                            for f in result["data"]))
