import pathlib
import os
import logging
from typing import List

from apps.rendering.task.framerenderingtask import FrameRenderingTaskBuilder
from golem.core.common import get_golem_path
from golem.testutils_app_integration import TestTaskIntegration
from golem.tools.ci import ci_skip
from golem.task.taskbase import Task

logger = logging.getLogger(__name__)


@ci_skip
class TestBlenderIntegration(TestTaskIntegration):

    @classmethod
    def _get_test_scene(cls) -> str:
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
            samples: int = 150,
            subtasks_count: int = 2,
            output_path=None,
            output_format="PNG",
            frames=None
    ) -> dict:

        if output_path is None:
            output_path = self.tempdir

        if frames is not None and len(frames) > 1:
            frames = FrameRenderingTaskBuilder.frames_to_string(frames)
            use_frames = True
        else:
            use_frames = False
            frames = "1"

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

    def check_outputs_existence(self, task: Task):
        result = task.task_definition.output_file

        if task.task_definition.options.use_frames:
            # For multiple frames we must build frame path.
            base, ext = os.path.splitext(task.task_definition.output_file)

            for frame in task.task_definition.options.frames:
                path = base + "{:04d}".format(frame) + ext

                logger.info("Expected result path [{}]".format(path))
                self.assertTrue(os.path.isfile(path))
        else:
            # For single frame, blender generates file with the same name
            # as in task_definition.
            logger.info("Expected result path [{}]".format(result))
            self.assertTrue(os.path.isfile(result))

    def test_full_task_flow_multiframes(self):
        task_def = self._task_dictionary(
            scene_file=self._get_chessboard_scene(),
            resolution=[400, 400],
            subtasks_count=2,
            frames=[1, 2])

        task: Task = self.execute_task(task_def)
        self.check_outputs_existence(task)

    def test_full_task_flow_singleframe(self):
        task_def = self._task_dictionary(
            scene_file=self._get_chessboard_scene(),
            resolution=[400, 400],
            subtasks_count=3)

        task: Task = self.execute_task(task_def)

        result = task.task_definition.output_file
        self.assertTrue(os.path.isfile(result))

    def test_failing_case_uneven_divisions(self):
        task_def = self._task_dictionary(
            scene_file=self._get_chessboard_scene(),
            resolution=[400, 400],
            subtasks_count=6,
            frames=[1, 2])

        task: Task = self.execute_task(task_def)
        self.check_outputs_existence(task)

    def test_failing_case_one_subtask(self):
        task_def = self._task_dictionary(
            scene_file=self._get_chessboard_scene(),
            resolution=[400, 400],
            subtasks_count=1,
            frames=[1, 2])

        task: Task = self.execute_task(task_def)
        self.check_outputs_existence(task)
