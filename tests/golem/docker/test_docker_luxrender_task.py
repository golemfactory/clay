import logging
import os
from os import path
from pathlib import Path
import shutil
from typing import Tuple
from unittest.mock import Mock, patch

import pytest

from apps.lux.task.luxrendertask import LuxRenderTaskBuilder, LuxTask
from golem.core.fileshelper import find_file_with_ext
from golem.docker.job import DockerJob
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ResultType
from golem.task.taskcomputer import DockerTaskThread
from golem.task.tasktester import TaskTester
from golem.tools.ci import ci_skip
from .test_docker_task import DockerTaskTestCase

# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")


@ci_skip
class TestDockerLuxrenderTask(
        DockerTaskTestCase[LuxTask, LuxRenderTaskBuilder]):

    TASK_FILE = "docker-luxrender-test-task.json"
    TASK_CLASS = LuxTask
    TASK_BUILDER_CLASS = LuxRenderTaskBuilder

    def _extract_results(
            self, computer: LocalComputer, task: LuxTask, subtask_id: str) \
            -> Tuple[Path, Path]:
        """
        Since the local computer use temp dir, you should copy files
        out of there before you use local computer again.
        Otherwise the files would get overwritten
        (during the verification process).
        This is a problem only in test suite.
        In real life provider and requestor are separate machines
        """
        dirname = os.path.dirname(computer.tt.result['data'][0])

        flm = Path(find_file_with_ext(dirname, [".flm"]))

        self.assertTrue(flm.is_file())

        if task.output_format == "exr":
            exr = Path(find_file_with_ext(dirname, [".exr"]))
            self.assertTrue(exr.is_file())
        else:
            png = Path(find_file_with_ext(dirname, [".png"]))
            self.assertTrue(png.is_file())

        # getattr used to silence typechecker errors
        test_file = Path(getattr(task, '_LuxTask__get_test_flm')())
        shutil.copy(flm, test_file)

        self.dirs_to_remove.append(test_file.parent)
        self.assertTrue(test_file.is_file())

        # copy to new location
        new_file_dir = test_file.parent / subtask_id

        new_flm_file = self._copy_file(
            test_file, new_file_dir / "newflmfile.flm")

        if task.output_format == "exr":
            new_file = self._copy_file(
                exr, new_file_dir / "newexrfile.exr")
        else:
            new_file = self._copy_file(
                png, new_file_dir / "newpngfile.png")

        return new_flm_file, new_file

    @patch('golem.core.common.deadline_to_timeout')
    def test_luxrender_real_task_png(self, mock_dtt):
        mock_dtt.return_value = 1.0
        task = self._get_test_task()
        task.output_format = "png"
        task.res_y = 200
        task.res_x = 200
        task.haltspp = 20
        # 1) to make it deterministic,
        # 2) depending on the kernel, small cropwindow can generate darker img,
        # this is a know issue in lux:
        # http: // www.luxrender.net / forum / viewtopic.php?f = 16 & t = 13389
        task.random_crop_window_for_verification = (0.05, 0.95, 0.05, 0.95)
        self._test_luxrender_real_task(task)

    @pytest.mark.slow
    @patch('golem.core.common.deadline_to_timeout')
    def test_luxrender_real_task_exr(self, mock_dtt):
        mock_dtt.return_value = 1.0
        task = self._get_test_task()
        task.output_format = "exr"
        task.res_y = 200
        task.res_x = 200
        task.haltspp = 20
        # 1) to make it deterministic,
        # 2) depending on the kernel, small cropwindow can generate darker img,
        # this is a known issue in lux:
        # http: // www.luxrender.net / forum / viewtopic.php?f = 16 & t = 13389
        task.random_crop_window_for_verification = (0.05, 0.95, 0.05, 0.95)
        self._test_luxrender_real_task(task)

    def _test_luxrender_real_task(self, task: LuxTask):
        ctd = task.query_extra_data(10000).ctd

        ctd["extra_data"].update(DockerJob.PATH_PARAMS)

        # act
        computer = LocalComputer(
            root_path=self.tempdir,
            success_callback=Mock(),
            error_callback=Mock(),
            compute_task_def=ctd,
            resources=task.task_resources
        )

        computer.run()
        computer.tt.join()

        new_flm_file, new_preview_file = self._extract_results(
            computer, task, ctd['subtask_id'])

        task.create_reference_data_for_task_validation()

        # assert good results - should pass
        self.assertEqual(task.num_tasks_received, 0)
        task.computation_finished(ctd['subtask_id'],
                                  [str(new_flm_file), str(new_preview_file)],
                                  result_type=ResultType.FILES,
                                  verification_finished_=lambda: None)

        is_subtask_verified = task.verify_subtask(ctd['subtask_id'])
        self.assertTrue(is_subtask_verified)
        self.assertEqual(task.num_tasks_received, 1)

        # assert bad results - should fail
        bad_flm_file = new_flm_file.parent / "badfile.flm"
        ctd = task.query_extra_data(10000).ctd
        task.computation_finished(ctd['subtask_id'],
                                  [str(bad_flm_file), str(new_preview_file)],
                                  result_type=ResultType.FILES,
                                  verification_finished_=lambda: None)

        self.assertFalse(task.verify_subtask(ctd['subtask_id']))
        self.assertEqual(task.num_tasks_received, 1)

    def test_luxrender_TaskTester_should_pass(self):
        task = self._get_test_task()

        computer = TaskTester(task, self.tempdir, Mock(), Mock())
        computer.run()
        computer.tt.join(60.0)

        dirname = os.path.dirname(computer.tt.result[0]['data'][0])
        flm = find_file_with_ext(dirname, [".flm"])
        png = find_file_with_ext(dirname, [".png"])

        assert path.isfile(flm)
        assert path.isfile(png)

    def test_luxrender_subtask(self):
        task = self._get_test_task()
        task_thread = self._run_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertEqual(task_thread.error_msg, '')

        # Check the number and type of result files:
        result = task_thread.result
        self.assertEqual(result["result_type"], ResultType.FILES)
        self.assertGreaterEqual(len(result["data"]), 3)
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDOUT_FILE
                for f in result["data"]))
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDERR_FILE
                for f in result["data"]))
        self.assertTrue(
            any(f.endswith(".flm") for f in result["data"]))
