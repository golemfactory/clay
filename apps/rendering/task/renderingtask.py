import logging
import math
import os
from typing import Type

from PIL import Image, ImageChops
from pathlib import Path

from apps.core.task.coretask import CoreTask, CoreTaskBuilder
from apps.rendering.resources.imgrepr import load_as_pil
from apps.rendering.resources.utils import handle_image_error, handle_none
from apps.rendering.task.renderingtaskstate import RendererDefaults
from golem_verificator.rendering_verifier import RenderingVerifier
from golem.core.common import get_golem_path
from golem.core.simpleexccmd import is_windows, exec_cmd
from golem.docker.environment import DockerEnvironment
from golem.docker.job import DockerJob
from golem.task.taskstate import SubtaskStatus

MIN_TIMEOUT = 60
SUBTASK_MIN_TIMEOUT = 60
PREVIEW_EXT = "PNG"
PREVIEW_X = 1280
PREVIEW_Y = 720

logger = logging.getLogger("apps.rendering")

class RenderingTask(CoreTask):

    VERIFIER_CLASS = RenderingVerifier
    ENVIRONMENT_CLASS = None # type: Type[DockerEnvironment]

    @classmethod
    def _get_task_collector_path(cls):
        if is_windows():
            build_path = os.path.join("x64", "Release", "taskcollector.exe")
        else:
            build_path = os.path.join("Release", "taskcollector")

        return os.path.normpath(os.path.join(get_golem_path(), "apps",
                                             "rendering", "resources",
                                             "taskcollector", build_path))

    ################
    # Task methods #
    ################

    def __init__(self, task_definition, total_tasks, root_path, owner):

        CoreTask.__init__(
            self,
            task_definition=task_definition,
            owner=owner,
            root_path=root_path,
            total_tasks=total_tasks)

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
    def computation_failed(self, subtask_id):
        super().computation_failed(subtask_id)
        self._update_task_preview()

    def restart(self):
        super().restart()
        self.collected_file_names = {}

    @CoreTask.handle_key_error
    def restart_subtask(self, subtask_id):
        if self.subtasks_given[subtask_id]['status'] == SubtaskStatus.finished:
            self._remove_from_preview(subtask_id)
        super().restart_subtask(subtask_id)

    def update_task_state(self, task_state):
        if not self.finished_computation() and self.preview_task_file_path:
            task_state.extra_data['result_preview'] = self.preview_task_file_path
        elif self.preview_file_path:
            task_state.extra_data['result_preview'] = self.preview_file_path

    #########################
    # Specific task methods #
    #########################
    def query_extra_data_for_reference_task(self, *args, **kwargs):
        """
        This method will generate extra data for reference task which will be solved on local computer (by requestor)
        in order to obtain reference results.
        The reference results will be used to validate the output given by providers.
        """
        pass

    def get_preview_file_path(self):
        return self.preview_file_path

    @handle_image_error(logger)
    def _update_preview(self, new_chunk_file_path, num_start):
        with handle_none(load_as_pil(new_chunk_file_path),
                         raise_if_none=IOError("load_as_pil failed")) as img, \
                self._open_preview() as img_current, \
                ImageChops.add(img_current, img) as img_added:
            img_added.save(self.preview_file_path, PREVIEW_EXT)

    @CoreTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        subtask = self.subtasks_given[subtask_id]
        empty_color = (0, 0, 0)
        with handle_image_error(logger), \
                self._open_preview() as img:
            self._mark_task_area(subtask, img, empty_color)
            img.save(self.preview_file_path, PREVIEW_EXT)

    def _update_task_preview(self):
        sent_color = (0, 255, 0)
        failed_color = (255, 0, 0)

        preview_name = "current_task_preview.{}".format(PREVIEW_EXT)
        preview_task_file_path = "{}".format(os.path.join(self.tmp_dir,
                                                          preview_name))

        with handle_image_error(logger), \
                self._open_preview() as img_task:

            subtasks_given = dict(self.subtasks_given)
            for sub in subtasks_given.values():
                if sub['status'].is_active():
                    self._mark_task_area(sub, img_task, sent_color)
                if sub['status'] in [SubtaskStatus.failure,
                                     SubtaskStatus.restarted]:
                    self._mark_task_area(sub, img_task, failed_color)

            img_task.save(preview_task_file_path, PREVIEW_EXT)

        self._update_preview_task_file_path(preview_task_file_path)

    def _update_preview_task_file_path(self, preview_task_file_path):
        self.preview_task_file_path = preview_task_file_path

    def _mark_task_area(self, subtask, img_task, color):
        x = int(round(self.res_x * self.scale_factor))
        y = int(round(self.res_y * self.scale_factor))
        upper = max(0, int(math.floor(y / self.total_tasks * (subtask['start_task'] - 1))))
        lower = min(int(math.floor(y / self.total_tasks * (subtask['end_task']))), y)
        for i in range(0, x):
            for j in range(upper, lower):
                img_task.putpixel((i, j), color)

    def _put_collected_files_together(self, output_file_name, files, arg):
        task_collector_path = self._get_task_collector_path()

        cmd = ["{}".format(task_collector_path),
               "{}".format(arg),
               "{}".format(self.res_x),
               "{}".format(self.res_y),
               output_file_name] + [f for f in files]
        exec_cmd(cmd)

    def _get_next_task(self):
        if self.last_task != self.total_tasks:
            self.last_task += 1
            start_task = self.last_task
            end_task = self.last_task
            return start_task, end_task
        else:
            for sub in self.subtasks_given.values():
                if sub['status'] in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                    sub['status'] = SubtaskStatus.resent
                    end_task = sub['end_task']
                    start_task = sub['start_task']
                    self.num_failed_subtasks -= 1
                    return start_task, end_task
        return None, None

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

    def short_extra_data_repr(self, extra_data):
        l = extra_data
        return "path_root: {path_root}, start_task: {start_task}, end_task: {end_task}, total_tasks: {total_tasks}, " \
               "outfilebasename: {outfilebasename}, scene_file: {scene_file}".format(**l)

    def _open_preview(self, mode="RGB", ext=PREVIEW_EXT):
        """ If preview file doesn't exist create a new empty one with given mode and extension.
        Extension should be compatibile with selected mode. """
        if self.preview_file_path is None or not os.path.exists(
                self.preview_file_path):
            preview_name = "current_preview.{}".format(ext)
            self.preview_file_path = "{}".format(os.path.join(self.tmp_dir,
                                                              preview_name))

            with handle_image_error(logger), \
                    Image.new(mode,
                              (int(round(self.res_x * self.scale_factor)),
                               int(round(self.res_y * self.scale_factor)))) \
                    as img:
                logger.debug('Saving new preview: %r', self.preview_file_path)
                img.save(self.preview_file_path, ext)

        return Image.open(self.preview_file_path)

    def _use_outer_task_collector(self):
        unsupported_formats = ['EXR', 'EPS']
        if self.output_format.upper() in unsupported_formats:
            return True
        return False

    def __get_path(self, path):
        if is_windows():
            return self.__get_path_windows(path)
        return path

    def __get_path_windows(self, path):
        return path.replace("\\", "/")


class RenderingTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = RenderingTask
    DEFAULTS = RendererDefaults

    def _calculate_total(self, defaults):
        if self.task_definition.optimize_total:
            return defaults.default_subtasks

        total = self.task_definition.total_subtasks

        if defaults.min_subtasks <= total <= defaults.max_subtasks:
            return total
        else:
            logger.warning("Cannot set total subtasks to {}. Changing to {}"
                           .format(total, defaults.default_subtasks))
            return defaults.default_subtasks

    @staticmethod
    def _scene_file(type, resources):
        extensions = type.output_file_ext
        candidates = [res for res in resources if any(res.lower().endswith(ext.lower())
                                            for ext in extensions)]
        if not candidates:
            raise Exception("Scene file was not found.")

        candidates.sort(key=len)
        return candidates[0]

    def get_task_kwargs(self, **kwargs):
        kwargs = super().get_task_kwargs(**kwargs)
        kwargs['total_tasks'] = self._calculate_total(self.DEFAULTS())
        return kwargs

    def build(self):
        task = super(RenderingTaskBuilder, self).build()
        return task

    @classmethod
    def build_dictionary(cls, definition):
        parent = super(RenderingTaskBuilder, cls)

        dictionary = parent.build_dictionary(definition)
        dictionary['options']['format'] = definition.output_format
        dictionary['options']['resolution'] = definition.resolution
        return dictionary

    @classmethod
    def build_minimal_definition(cls, task_type, dictionary):
        parent = super(RenderingTaskBuilder, cls)
        resources = dictionary['resources']

        definition = parent.build_minimal_definition(task_type, dictionary)
        definition.main_scene_file = cls._scene_file(task_type, resources)
        return definition

    @classmethod
    def build_full_definition(cls, task_type, dictionary):
        parent = super(RenderingTaskBuilder, cls)
        options = dictionary['options']

        definition = parent.build_full_definition(task_type, dictionary)
        definition.output_format = options['format'].upper()
        definition.resolution = [int(val) for val in options['resolution']]
        if definition.full_task_timeout < MIN_TIMEOUT:
            logger.warning("Timeout %d too short for this task. "
                           "Changing to %d" % (definition.full_task_timeout,
                                               MIN_TIMEOUT))
            definition.full_task_timeout = MIN_TIMEOUT
        if definition.subtask_timeout < SUBTASK_MIN_TIMEOUT:
            logger.warning("Subtask timeout %d too short for this task. "
                           "Changing to %d" % (definition.subtask_timeout,
                                               SUBTASK_MIN_TIMEOUT))
            definition.subtask_timeout = SUBTASK_MIN_TIMEOUT
        return definition

    @classmethod
    def get_output_path(cls, dictionary, definition):
        parent = super(RenderingTaskBuilder, cls)
        path = parent.get_output_path(dictionary, definition)

        return '{}.{}'.format(path, dictionary['options']['format'])
