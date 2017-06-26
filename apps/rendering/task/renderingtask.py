from __future__ import division

import logging
import math
import os
from copy import deepcopy

from PIL import Image, ImageChops
from pathlib import Path

from apps.core.task.coretask import CoreTask, CoreTaskBuilder
from apps.rendering.resources.imgrepr import load_as_pil
from apps.rendering.task.renderingtaskstate import RendererDefaults
from apps.rendering.task.verificator import RenderingVerificator
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.fileshelper import format_cmd_line_path
from golem.core.simpleexccmd import is_windows, exec_cmd
from golem.docker.job import DockerJob
from golem.task.taskbase import ComputeTaskDef
from golem.task.taskstate import SubtaskStatus

MIN_TIMEOUT = 2200.0
SUBTASK_TIMEOUT = 220.0
PREVIEW_EXT = "PNG"
PREVIEW_X = 1280
PREVIEW_Y = 720

logger = logging.getLogger("apps.rendering")


class RenderingTask(CoreTask):

    VERIFICATOR_CLASS = RenderingVerificator

    @classmethod
    def _get_task_collector_path(cls):
        if is_windows():
            task_collector_name = "taskcollector.exe"
        else:
            task_collector_name = "taskcollector"
        return os.path.normpath(os.path.join(get_golem_path(), "apps", "rendering", "resources",
                                             "taskcollector", "Release", task_collector_name))

    ################
    # Task methods #
    ################

    def __init__(self, node_name, task_definition, total_tasks, root_path, owner_address="",
                 owner_port=0, owner_key_id=""):

        environment = self.ENVIRONMENT_CLASS()
        if task_definition.docker_images is None:
            task_definition.docker_images = environment.docker_images

        main_program_file = environment.main_program_file
        try:
            with open(main_program_file, "r") as src_file:
                src_code = src_file.read()
        except IOError as err:
            logger.warning("Wrong main program file: {}".format(err))
            src_code = ""
        self.main_program_file = main_program_file

        resource_size = 0
        task_resources = set(filter(os.path.isfile, task_definition.resources))
        for resource in task_resources:
            resource_size += os.stat(resource).st_size

        CoreTask.__init__(
            self,
            src_code=src_code,
            task_definition=task_definition,
            node_name=node_name,
            owner_address=owner_address,
            owner_port=owner_port,
            owner_key_id=owner_key_id,
            environment=environment.get_id(),
            resource_size=resource_size)

        self.main_scene_file = task_definition.main_scene_file
        self.main_scene_dir = str(Path(task_definition.main_scene_file).parent)
        if isinstance(task_definition.output_file, unicode):
            task_definition.output_file = task_definition.output_file.encode('utf-8', 'replace')
        self.outfilebasename = Path(task_definition.output_file).stem
        self.output_file = task_definition.output_file
        self.output_format = task_definition.output_format

        self.total_tasks = total_tasks
        self.res_x, self.res_y = task_definition.resolution

        self.root_path = root_path
        self.preview_file_path = None
        self.preview_task_file_path = None

        self.task_resources = deepcopy(list(task_resources))

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

        self.verificator.res_x = self.res_x
        self.verificator.res_y = self.res_y
        self.verificator.total_tasks = self.total_tasks
        self.verificator.root_path = self.root_path

    @CoreTask.handle_key_error
    def computation_failed(self, subtask_id):
        CoreTask.computation_failed(self, subtask_id)
        self._update_task_preview()

    def restart(self):
        super(RenderingTask, self).restart()
        self.collected_file_names = {}

    @CoreTask.handle_key_error
    def restart_subtask(self, subtask_id):
        if self.subtasks_given[subtask_id]['status'] == SubtaskStatus.finished:
            self._remove_from_preview(subtask_id)
        CoreTask.restart_subtask(self, subtask_id)

    def update_task_state(self, task_state):
        if not self.finished_computation() and self.preview_task_file_path:
            task_state.extra_data['result_preview'] = self.preview_task_file_path
        elif self.preview_file_path:
            task_state.extra_data['result_preview'] = self.preview_file_path

    #########################
    # Specific task methods #
    #########################

    def get_subtasks(self, part):
        return self.subtasks_given

    def get_preview_file_path(self):
        return self.preview_file_path

    def _update_preview(self, new_chunk_file_path, num_start):
        img = load_as_pil(new_chunk_file_path)

        img_current = self._open_preview()
        img_current = ImageChops.add(img_current, img)
        img_current.save(self.preview_file_path, PREVIEW_EXT)
        img.close()

    @CoreTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        empty_color = (0, 0, 0)
        if isinstance(self.preview_file_path, list):  # FIXME Add possibility to remove subtask from frame
            return
        img = self._open_preview()
        self._mark_task_area(self.subtasks_given[subtask_id], img, empty_color)
        img.save(self.preview_file_path, PREVIEW_EXT)

    def _update_task_preview(self):
        sent_color = (0, 255, 0)
        failed_color = (255, 0, 0)

        preview_name = "current_task_preview.{}".format(PREVIEW_EXT)
        preview_task_file_path = "{}".format(os.path.join(self.tmp_dir,
                                                          preview_name))

        img_task = self._open_preview()

        for sub in self.subtasks_given.values():
            if SubtaskStatus.is_computed(sub['status']):
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
               format_cmd_line_path(output_file_name)] + [format_cmd_line_path(f) for f in files]
        exec_cmd(cmd)

    def _new_compute_task_def(self, hash, extra_data, working_directory, perf_index):
        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        ctd.subtask_id = hash
        ctd.extra_data = extra_data
        ctd.short_description = self._short_extra_data_repr(perf_index, extra_data)
        ctd.src_code = self.src_code
        ctd.performance = perf_index
        ctd.working_directory = working_directory
        ctd.docker_images = self.header.docker_images
        ctd.deadline = timeout_to_deadline(self.header.subtask_timeout)
        return ctd

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

    def _get_working_directory(self):
        common_path_prefix = os.path.commonprefix(self.task_resources)
        common_path_prefix = os.path.dirname(common_path_prefix)
        working_directory = os.path.relpath(self.main_scene_file, common_path_prefix)
        working_directory = os.path.dirname(working_directory)
        logger.debug("Working directory {}".format(working_directory))
        return self.__get_path(working_directory)

    def _get_scene_file_rel_path(self):
        """Returns the path to the secene file relative to the directory where
        the task srcipt is run.
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

    def _short_extra_data_repr(self, perf_index, extra_data):
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
            img = Image.new(mode, (int(round(self.res_x * self.scale_factor)),
                                   int(round(self.res_y * self.scale_factor))))
            logger.debug('Saving new preview: %r', self.preview_file_path)
            img.save(self.preview_file_path, ext)
            img.close()

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

    def _set_verification_options(self, new_task):
        new_task.verificator.set_verification_options(
            self.task_definition.verification_options)

    @staticmethod
    def _scene_file(type, resources):
        extensions = type.output_file_ext
        candidates = filter(lambda res: any(res.lower().endswith(ext.lower())
                                            for ext in extensions),
                            resources)
        if not candidates:
            raise Exception("Scene file was not found.")

        candidates.sort(key=len)
        return candidates[0]

    def get_task_kwargs(self, **kwargs):
        # super() when ready
        kwargs['node_name'] = self.node_name
        kwargs['task_definition'] = self.task_definition
        kwargs['total_tasks'] = self._calculate_total(self.DEFAULTS())
        kwargs['root_path'] = self.root_path
        return kwargs

    def build(self):
        task = super(RenderingTaskBuilder, self).build()
        self._set_verification_options(task)
        task.initialize(self.dir_manager)
        return task

    @classmethod
    def build_dictionary(cls, definition):
        parent = super(RenderingTaskBuilder, cls)

        dictionary = parent.build_dictionary(definition)
        dictionary[u'options'][u'format'] = definition.output_format
        dictionary[u'options'][u'resolution'] = definition.resolution
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
        return definition

    @classmethod
    def get_output_path(cls, dictionary, definition):
        parent = super(RenderingTaskBuilder, cls)
        path = parent.get_output_path(dictionary, definition)

        if definition.legacy:
            return path
        return '{}.{}'.format(path, dictionary['options']['format'])
