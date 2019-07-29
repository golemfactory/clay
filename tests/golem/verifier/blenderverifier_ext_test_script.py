import pathlib
import os
import logging
import string
from typing import List

from golem.core.common import get_golem_path
from golem.testutils import TestTaskIntegration
from golem.tools.ci import ci_skip
from golem.task.taskbase import Task
from tests.apps.blender.task.test_blenderintegration import TestBlenderIntegration


logger = logging.getLogger(__name__)


class ExtendedVerifierTest(TestBlenderIntegration):

    def test_script_for_verifier(self):
        parameters_sets = self._generate_parameters()

        for parameters_set in parameters_sets:
            self._run_for_params_dict(parameters_set)

    def _run_for_params_dict(self, parameters_set):
        resolution = parameters_set['resolution']
        subtasks = parameters_set['subtasks_count']
        frames = parameters_set['frames']
        crops_params = parameters_set['crops_params']

        self._run_for_parameters_set(resolution, subtasks, frames, crops_params)

    def _run_for_parameters_set(self, resolution: List[int], subtasks: int, frames: List[int], crops_params: dict):
        task_def = self._task_dictionary(scene_file=self._get_chessboard_scene(),
                                         resolution=resolution,
                                         subtasks_count=subtasks,
                                         frames=frames)

        task: Task = self.start_task(task_def)

        for i in range(task.task_definition.subtasks_count):
            result, subtask_id, _ = self.compute_next_subtask(task, i)
            self.verify_subtask(task, subtask_id, result)

        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))

    def _generate_parameters(self):
        return []




