import pathlib
import os
import logging
from typing import List

from golem.core.common import get_golem_path
from golem.testutils import TestTaskIntegration
from golem.tools.ci import ci_skip


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
            output_format: str="PNG"
    ) -> dict:
    
        if output_path is None:
            output_path = self.tempdir

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
                "samples": samples
            }
        }

        return task_def_for_blender

    def test_full_task_flow(self):
        task_def = self._task_dictionary(scene_file=self._get_chessboard_scene(),
                                         resolution=[400, 400],
                                         subtasks_count=3)

        task = self.execute_task(task_def)

        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))

