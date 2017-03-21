from copy import deepcopy
import logging
import math
import os

from pathlib import Path
from PIL import Image, ImageChops


from golem.core.common import get_golem_path, timeout_to_deadline

from golem.core.simpleexccmd import is_windows, exec_cmd
from golem.docker.job import DockerJob
from golem.task.taskbase import ComputeTaskDef
from golem.task.taskstate import SubtaskStatus

from apps.core.task.coretask import CoreTask, CoreTaskBuilder
from apps.rendering.resources.imgrepr import load_img
from apps.rendering.task.renderingtaskstate import RendererDefaults
from apps.rendering.task.verificator import RenderingVerificator


MIN_TIMEOUT = 2200.0
SUBTASK_TIMEOUT = 220.0

logger = logging.getLogger("apps.rendering")


class RenderingTask(CoreTask):

    VERIFICATOR_CLASS = RenderingVerificator

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

        preview_x = 300
        preview_y = 200
        if self.res_x != 0 and self.res_y != 0:
            if float(self.res_x) / float(self.res_y) > float(preview_x) / float(preview_y):
                self.scale_factor = float(preview_x) / float(self.res_x)
            else:
                self.scale_factor = float(preview_y) / float(self.res_y)
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

    def get_preview_file_path(self):
        return self.preview_file_path

    def _update_preview(self, new_chunk_file_path, num_start):
        img_repr = load_img(new_chunk_file_path)
        img = img_repr.to_pil()

        img_current = self._open_preview()
        img_current = ImageChops.add(img_current, img)
        img_current.save(self.preview_file_path, "BMP")
        img.close()

    @CoreTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        empty_color = (0, 0, 0)
        if isinstance(self.preview_file_path, list):  # FIXME Add possibility to remove subtask from frame
            return
        img = self._open_preview()
        self._mark_task_area(self.subtasks_given[subtask_id], img, empty_color)
        img.save(self.preview_file_path, "BMP")

    def _update_task_preview(self):
        sent_color = (0, 255, 0)
        failed_color = (255, 0, 0)

        self.preview_task_file_path = "{}".format(os.path.join(self.tmp_dir, "current_task_preview"))

        img_task = self._open_preview()

        for sub in self.subtasks_given.values():
            if sub['status'] == SubtaskStatus.starting:
                self._mark_task_area(sub, img_task, sent_color)
            if sub['status'] in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                self._mark_task_area(sub, img_task, failed_color)

        img_task.save(self.preview_task_file_path, "BMP")
        self._update_preview_task_file_path(self.preview_task_file_path)

    def _update_preview_task_file_path(self, preview_task_file_path):
        self.preview_task_file_path = preview_task_file_path

    def _mark_task_area(self, subtask, img_task, color):
        upper = max(0, int(math.floor(self.scale_factor * self.res_y / self.total_tasks * (subtask['start_task'] - 1))))
        lower = min(int(math.floor(self.scale_factor * self.res_y / self.total_tasks * (subtask['end_task']))), int(round(self.res_y * self.scale_factor)))
        for i in range(0, int(round(self.res_x * self.scale_factor))):
            for j in range(int(round(upper)), int(round(lower))):
                img_task.putpixel((i, j), color)

    def _put_collected_files_together(self, output_file_name, files, arg):
        task_collector_path = self._get_task_collector_path()

        cmd = ["{}".format(task_collector_path),
               "{}".format(arg),
               "{}".format(self.res_x),
               "{}".format(self.res_y),
               "{}".format(output_file_name)] + files

        exec_cmd(cmd)

    @staticmethod
    def _get_task_collector_path():
        if is_windows():
            task_collector_name = "taskcollector.exe"
        else:
            task_collector_name = "taskcollector"
        return os.path.normpath(os.path.join(get_golem_path(), "apps", "rendering", "resources",
                                             "taskcollector", "Release", task_collector_name))

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

    def _open_preview(self, mode="RGB", ext="BMP"):
        """ If preview file doesn't exist create a new empty one with given mode and extension.
        Extension should be compatibile with selected mode. """
        if self.preview_file_path is None or not os.path.exists(self.preview_file_path):
            self.preview_file_path = "{}".format(os.path.join(self.tmp_dir, "current_preview"))
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

    def _calculate_total(self, defaults, definition):
        if definition.optimize_total:
            return defaults.default_subtasks

        if defaults.min_subtasks <= definition.total_subtasks <= defaults.max_subtasks:
            return definition.total_subtasks
        else:
            logger.warning("Cannot set total subtasks to {}. Changing to {}".format(
                definition.total_subtasks, defaults.default_subtasks))
            return defaults.default_subtasks

    def _set_verification_options(self, new_task):
        new_task.verificator.set_verification_options(self.task_definition.verification_options)

    def get_task_kwargs(self, **kwargs):
        # super() when ready
        kwargs['node_name'] = self.node_name
        kwargs['task_definition'] = self.task_definition
        kwargs['total_tasks'] = self._calculate_total(self.DEFAULTS(), self.task_definition)
        kwargs['root_path'] = self.root_path
        return kwargs

    def build(self):
        task = super(RenderingTaskBuilder, self).build()
        self._set_verification_options(task)
        task.initialize(self.dir_manager)
        return task
