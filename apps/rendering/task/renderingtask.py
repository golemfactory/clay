import logging
import math
import os
from typing import cast, Optional, Type, TYPE_CHECKING

from pathlib import Path

from apps.core.task.coretask import CoreTask, CoreTaskBuilder
from apps.rendering.resources.imgrepr import OpenCVImgRepr
from apps.rendering.resources.utils import handle_opencv_image_error
from golem.verifier.rendering_verifier import RenderingVerifier
from golem.core.simpleexccmd import is_windows
from golem.docker.job import DockerJob
from golem.task.taskstate import SubtaskStatus

if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from .renderingtaskstate import RenderingTaskDefinition
    from golem.docker.environment import DockerEnvironment


MIN_TIMEOUT = 60
SUBTASK_MIN_TIMEOUT = 60
PREVIEW_EXT = "PNG"
PREVIEW_X = 1280
PREVIEW_Y = 720
# Theoretically it should be 8, but there are some unsolved edge cases,
# so 10 should be safe.
MIN_PIXELS_PER_SUBTASK = 10


logger = logging.getLogger("apps.rendering")


# pylint: disable-msg=too-many-instance-attributes,abstract-method
class RenderingTask(CoreTask):
    VERIFIER_CLASS = RenderingVerifier
    ENVIRONMENT_CLASS: 'Type[DockerEnvironment]'

    ################
    # Task methods #
    ################

    def __init__(self, task_definition: 'RenderingTaskDefinition', root_path,
                 owner):

        CoreTask.__init__(
            self,
            task_definition=task_definition,
            owner=owner,
            root_path=root_path)

        if task_definition.docker_images is None:
            task_definition.docker_images = self.environment.docker_images

        self.main_scene_file = task_definition.main_scene_file
        self.main_scene_dir = str(Path(task_definition.main_scene_file).parent)
        self.outfilebasename = Path(task_definition.output_file).stem
        self.output_file = task_definition.output_file
        self.output_format = task_definition.output_format

        self.res_x, self.res_y = task_definition.resolution

        self.preview_file_path = None
        self.preview_task_file_path = None

        self.collected_file_names = {}

        preview_x = PREVIEW_X
        preview_y = PREVIEW_Y
        if self.res_x != 0 and self.res_y != 0:
            if self.res_x / self.res_y > preview_x / preview_y:
                self.scale_factor = preview_x / self.res_x
            else:
                self.scale_factor = preview_y / self.res_y
            self.scale_factor = min(1.0, self.scale_factor)
        else:
            self.scale_factor = 1.0

        self.test_task_res_path = None

    @CoreTask.handle_key_error
    def computation_failed(self, subtask_id: str, ban_node: bool = True):
        super().computation_failed(subtask_id, ban_node)
        self._update_task_preview()

    def restart(self):
        super().restart()
        self.collected_file_names = {}

    @CoreTask.handle_key_error
    def restart_subtask(
            self,
            subtask_id,
            new_state: Optional[SubtaskStatus] = None,
    ):
        if self.subtasks_given[subtask_id]['status'] == SubtaskStatus.finished:
            self._remove_from_preview(subtask_id)
        super().restart_subtask(subtask_id, new_state=new_state)

    def update_task_state(self, task_state):
        if not self.finished_computation() and self.preview_task_file_path:
            task_state.extra_data['result_preview'] \
                = self.preview_task_file_path
        elif self.preview_file_path:
            task_state.extra_data['result_preview'] = self.preview_file_path

    #########################
    # Specific task methods #
    #########################
    def query_extra_data_for_reference_task(self, *args, **kwargs):
        """
        This method will generate extra data for reference task which will be
        solved on local computer (by requestor) in order to obtain reference
        results. The reference results will be used to validate the output given
        by providers.
        """
        pass

    def get_preview_file_path(self):
        return self.preview_file_path

    @handle_opencv_image_error(logger)
    def _update_preview(self, new_chunk_file_path, num_start):
            img = OpenCVImgRepr.from_image_file(new_chunk_file_path)
            img_current = self._open_preview()
            img_current.add(img)
            img_current.save_with_extension(self.preview_file_path, PREVIEW_EXT)

    @CoreTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        subtask = self.subtasks_given[subtask_id]
        empty_color = (0, 0, 0)
        with handle_opencv_image_error(logger):
            img = self._open_preview()
            self._mark_task_area(subtask, img, empty_color)
            img.save_with_extension(self.preview_file_path, PREVIEW_EXT)

    def _update_task_preview(self):
        sent_color = (0, 255, 0)
        failed_color = (255, 0, 0)

        preview_name = "current_task_preview.{}".format(PREVIEW_EXT)
        preview_task_file_path = "{}".format(os.path.join(self.tmp_dir,
                                                          preview_name))

        with handle_opencv_image_error(logger):
            img_task = self._open_preview()
            subtasks_given = dict(self.subtasks_given)
            for sub in subtasks_given.values():
                if sub['status'].is_active():
                    self._mark_task_area(sub, img_task, sent_color)
                if sub['status'] in [SubtaskStatus.failure,
                                     SubtaskStatus.restarted]:
                    self._mark_task_area(sub, img_task, failed_color)

            img_task.save_with_extension(preview_task_file_path, PREVIEW_EXT)

        self._update_preview_task_file_path(preview_task_file_path)

    def _update_preview_task_file_path(self, preview_task_file_path):
        self.preview_task_file_path = preview_task_file_path

    def _mark_task_area(self, subtask, img_task, color):
        x = int(round(self.res_x * self.scale_factor))
        y = int(round(self.res_y * self.scale_factor))
        upper = max(0,
                    int(math.floor(y / self.get_total_tasks()
                                   * (subtask['start_task'] - 1))))
        lower = min(
            int(math.floor(y / self.get_total_tasks()
                           * (subtask['start_task']))),
            y,
        )
        for i in range(0, x):
            for j in range(upper, lower):
                img_task.set_pixel((i, j), color)

    def _get_next_task(self):
        logger.debug("_get_next_task. last_task=%d, total_tasks=%d, "
                     "num_failed_subtasks=%d",
                     self.last_task,
                     self.get_total_tasks(),
                     self.num_failed_subtasks,
        )
        if self.last_task != self.get_total_tasks():
            self.last_task += 1
            start_task = self.last_task
            return start_task
        else:
            for sub in self.subtasks_given.values():
                if sub['status'] \
                        in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                    sub['status'] = SubtaskStatus.resent
                    start_task = sub['start_task']
                    self.num_failed_subtasks -= 1
                    return start_task
        return None

    def _get_scene_file_rel_path(self):
        """Returns the path to the scene file relative to the directory where
        the task script is run.
        """
        if self.is_docker_task():
            # In a Docker container we know the absolute path:
            # First compute the path relative to the resources root dir:
            rel_scene_path = os.path.relpath(self.main_scene_file,
                                             self._get_resources_root_dir())
            # Then prefix with the resources dir in the container:
            abs_scene_path = DockerJob.get_absolute_resource_path(
                rel_scene_path)
            return abs_scene_path
        else:
            return ''

    def _open_preview(self, mode=OpenCVImgRepr.RGB, ext=PREVIEW_EXT):
        """ If preview file doesn't exist create a new empty one with given mode
         and extension. Extension should be compatible with selected mode. """
        if self.preview_file_path is None or not os.path.exists(
                self.preview_file_path):
            preview_name = "current_preview.{}".format(ext)
            self.preview_file_path = "{}".format(os.path.join(self.tmp_dir,
                                                              preview_name))

            with handle_opencv_image_error(logger):
                img = OpenCVImgRepr.empty(
                    int(round(self.res_x * self.scale_factor)),
                    int(round(self.res_y * self.scale_factor)), channels=mode)
                logger.debug('Saving new preview: %r', self.preview_file_path)
                img.save_with_extension(self.preview_file_path, ext)

        logger.debug(
            'Opening preview: %r, exists?: %s',
            self.preview_file_path,
            os.path.exists(self.preview_file_path)
        )
        return OpenCVImgRepr.from_image_file(self.preview_file_path)

    def __get_path(self, path):
        if is_windows():
            return self.__get_path_windows(path)
        return path

    def __get_path_windows(self, path):
        return path.replace("\\", "/")


class RenderingTaskBuilderError(Exception):
    pass


class RenderingTaskBuilder(CoreTaskBuilder):
    TASK_CLASS: Type[RenderingTask]

    @staticmethod
    def _scene_file(type, resources):
        extensions = type.output_file_ext
        candidates = [res for res in resources
                      if any(res.lower().endswith(ext.lower())
                             for ext in extensions)]
        if not candidates:
            raise RenderingTaskBuilderError("Scene file was not found.")

        candidates.sort(key=len)
        return candidates[0]

    @classmethod
    def build_dictionary(cls, definition):
        parent = cast(Type[CoreTaskBuilder], super(RenderingTaskBuilder, cls))

        dictionary = parent.build_dictionary(definition)
        dictionary['options']['format'] = definition.output_format
        dictionary['options']['resolution'] = definition.resolution
        return dictionary

    @classmethod
    def build_minimal_definition(cls, task_type, dictionary) \
            -> 'RenderingTaskDefinition':
        parent = cast(Type[CoreTaskBuilder], super(RenderingTaskBuilder, cls))
        resources = dictionary['resources']

        definition = cast(
            'RenderingTaskDefinition',
            parent.build_minimal_definition(task_type, dictionary))

        if 'main_scene_file' in dictionary:
            main_scene_file = dictionary['main_scene_file']
        else:
            main_scene_file = cls._scene_file(task_type, resources)

        definition.main_scene_file = main_scene_file
        return definition

    @classmethod
    def build_full_definition(cls, task_type, dictionary) \
            -> 'RenderingTaskDefinition':
        parent = cast(Type[CoreTaskBuilder], super(RenderingTaskBuilder, cls))
        options = dictionary['options']

        definition = cast(
            'RenderingTaskDefinition',
            parent.build_full_definition(task_type, dictionary))
        definition.output_format = options['format'].upper()

        definition.resolution = \
            [int(val) for val in dictionary['options']['resolution']]
        if any(dim < MIN_PIXELS_PER_SUBTASK for dim in definition.resolution):
            raise ValueError("resolution too small")

        if definition.timeout < MIN_TIMEOUT:
            logger.warning(
                "Timeout %d too short for this task. "
                "Changing to %f",
                definition.timeout,
                MIN_TIMEOUT,
            )
            definition.timeout = MIN_TIMEOUT
        if definition.subtask_timeout < SUBTASK_MIN_TIMEOUT:
            logger.warning(
                "Subtask timeout %d too short for this task. "
                "Changing to %f",
                definition.subtask_timeout,
                SUBTASK_MIN_TIMEOUT,
            )
            definition.subtask_timeout = SUBTASK_MIN_TIMEOUT
        return definition

    @classmethod
    def get_output_path(cls, dictionary, definition):
        parent = cast(Type[CoreTaskBuilder], super(RenderingTaskBuilder, cls))
        path = parent.get_output_path(dictionary, definition)

        return '{}.{}'.format(path, dictionary['options']['format'])
