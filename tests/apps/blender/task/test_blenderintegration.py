import pathlib
import os
import logging
import string
from typing import List

from golem.core.common import get_golem_path
from golem.testutils import TestTaskIntegration
from golem.tools.ci import ci_skip
from golem.task.taskbase import Task


logger = logging.getLogger(__name__)



@ci_skip
class TestBlenderIntegration(TestTaskIntegration):

    @classmethod
    def _get_test_scene(cls) -> pathlib.Path:
        scene_file = pathlib.Path(get_golem_path())
        scene_file /= "apps/blender/benchmark/test_task/cube.blend"
        return str(scene_file)

    @classmethod
    def _get_chessboard_scene(cls):
        return os.path.join(
            get_golem_path(),
            'tests/apps/blender/verification/test_data/'
            'chessboard_400x400.blend'
        )

    def _task_dictionary(  # pylint: disable=too-many-arguments
            self,
            scene_file: str,
            resolution: List[int],
            samples: int=150,
            subtasks_count: int=2,
            output_path: str=None,
            output_format: str="PNG",
            frames: List[int]=None
    ) -> dict:
    
        if output_path is None:
            output_path = self.tempdir

        if frames is not None:
            use_frames = False
        else:
            use_frames = True

        frames = ["{};".format(frame) for frame in frames]
        frames = ''.join(frames)
        frames = frames[:-1]        # Remove last semicolon.

        logger.info(frames)

        task_def_for_blender = {
            'type': "Blender",
            'name': 'test task',
            'timeout': "0:10:00",
            "subtask_timeout": "0:09:50",
            "subtasks_count": subtasks_count,
            "bid": 1.0,
            "resources": [scene_file],
            "options": {
                "output_path": output_path,
                "format": output_format,
                "resolution": resolution,
                "samples": samples,
                "use_frames": use_frames,
                "frames": frames
            }
        }

        return task_def_for_blender

    def test_full_task_flow(self):
        task_def = self._task_dictionary(scene_file=self._get_chessboard_scene(),
                                         resolution=[400, 400],
                                         subtasks_count=3,
                                         frames=[1,2])

        task = self.execute_task(task_def)

        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))

    def test_script_for_verifier_tmp(self):
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
