import logging
import math
import os
import random
import uuid
from copy import deepcopy, copy

from PIL import Image, ImageChops

from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.fileshelper import find_file_with_ext
from golem.core.keysauth import get_random, get_random_float
from golem.core.simpleexccmd import is_windows, exec_cmd
from golem.docker.job import DockerJob
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ComputeTaskDef
from golem.task.taskclient import TaskClient
from golem.task.taskstate import SubtaskStatus

from apps.core.task.gnrtask import GNRTask, GNRTaskBuilder
from apps.rendering.resources.imgrepr import verify_img, advance_verify_img
from apps.rendering.resources.renderingtaskcollector import exr_to_pil


MIN_TIMEOUT = 2200.0
SUBTASK_TIMEOUT = 220.0

logger = logging.getLogger("apps.rendering")


MAX_PENDING_CLIENT_RESULTS = 1


class RenderingTaskBuilder(GNRTaskBuilder):
    def _calculate_total(self, defaults, definition):
        if definition.optimize_total:
            return defaults.default_subtasks

        if defaults.min_subtasks <= definition.total_subtasks <= defaults.max_subtasks:
            return definition.total_subtasks
        else:
            return defaults.default_subtasks

    def _set_verification_options(self, new_task):
        if self.task_definition.verification_options is None:
            new_task.advanceVerification = False
        else:
            new_task.advanceVerification = True
            new_task.verification_options.type = self.task_definition.verification_options.type
            new_task.verification_options.box_size = self.task_definition.verification_options.box_size
            new_task.verification_options.probability = self.task_definition.verification_options.probability
        return new_task


class AcceptClientVerdict(object):
    ACCEPTED = 0
    REJECTED = 1
    SHOULD_WAIT = 2


class RenderingTask(GNRTask):

    ################
    # Task methods #
    ################

    def __init__(self, node_id, task_id, owner_address, owner_port, owner_key_id, environment, timeout,
                 subtask_timeout, main_program_file, task_resources, main_scene_dir, main_scene_file,
                 total_tasks, res_x, res_y, outfilebasename, output_file, output_format, root_path,
                 estimated_memory, max_price, docker_images=None,
                 max_pending_client_results=MAX_PENDING_CLIENT_RESULTS):

        try:
            with open(main_program_file, "r") as src_file:
                src_code = src_file.read()
        except IOError as err:
            logger.error("Wrong main program file: {}".format(err))
            src_code = ""

        resource_size = 0
        task_resources = set(filter(os.path.isfile, task_resources))
        for resource in task_resources:
            resource_size += os.stat(resource).st_size

        GNRTask.__init__(self, src_code, node_id, task_id, owner_address, owner_port, owner_key_id, environment,
                         timeout, subtask_timeout, resource_size, estimated_memory, max_price, docker_images)

        self.main_program_file = main_program_file
        self.main_scene_file = main_scene_file
        self.main_scene_dir = main_scene_dir
        self.outfilebasename = outfilebasename
        self.output_file = output_file
        self.output_format = output_format

        self.total_tasks = total_tasks
        self.res_x = res_x
        self.res_y = res_y

        self.root_path = root_path
        self.preview_file_path = None
        self.preview_task_file_path = None

        self.task_resources = deepcopy(list(task_resources))

        self.collected_file_names = {}

        self.advanceVerification = False

        self.verified_clients = list()
        self.max_pending_client_results = max_pending_client_results
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

    @GNRTask.handle_key_error
    def computation_failed(self, subtask_id):
        GNRTask.computation_failed(self, subtask_id)
        self._update_task_preview()

    def restart(self):
        super(RenderingTask, self).restart()
        self.collected_file_names = {}

    @GNRTask.handle_key_error
    def restart_subtask(self, subtask_id):
        if subtask_id in self.subtasks_given:
            if self.subtasks_given[subtask_id]['status'] == SubtaskStatus.finished:
                self._remove_from_preview(subtask_id)
        GNRTask.restart_subtask(self, subtask_id)

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

    def _get_part_size(self, subtask_id):
        return self.res_x, self.res_y

    @GNRTask.handle_key_error
    def _get_part_img_size(self, subtask_id, adv_test_file):
        num_task = self.subtasks_given[subtask_id]['start_task']
        img_height = int(math.floor(float(self.res_y) / float(self.total_tasks)))
        return 0, (num_task - 1) * img_height, self.res_x, num_task * img_height

    def _update_preview(self, new_chunk_file_path):

        if new_chunk_file_path.upper().endswith(".EXR"):
            img = exr_to_pil(new_chunk_file_path)
        else:
            img = Image.open(new_chunk_file_path)

        img_current = self._open_preview()
        img_current = ImageChops.add(img_current, img)
        img_current.save(self.preview_file_path, "BMP")
        img.close()

    @GNRTask.handle_key_error
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
        if is_windows():
            task_collector_path = os.path.normpath(
                os.path.join(get_golem_path(), "apps", "rendering", "resources", "taskcollector", "Release", "taskcollector.exe"))
        else:
            task_collector_path = os.path.normpath(
                os.path.join(get_golem_path(), "apps", "rendering", "resources", "taskcollector", "Release",
                             "taskcollector"))
        cmd = ["{}".format(task_collector_path), "{}".format(arg), "{}".format(self.res_x), "{}".format(self.res_y), "{}".format(output_file_name)] + files
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
        working_directory = os.path.relpath(self.main_program_file, common_path_prefix)
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
            scene_file = os.path.relpath(os.path.dirname(self.main_scene_file), os.path.dirname(self.main_program_file))
            scene_file = os.path.normpath(os.path.join(scene_file, os.path.basename(self.main_scene_file)))
            return self.__get_path(scene_file)

    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        return "path_root: {path_root}, start_task: {start_task}, end_task: {end_task}, total_tasks: {total_tasks}, " \
               "outfilebasename: {outfilebasename}, scene_file: {scene_file}".format(**l)

    def _verify_img(self, file_, res_x, res_y):
        return verify_img(file_, res_x, res_y)

    def _open_preview(self):

        if self.preview_file_path is None or not os.path.exists(self.preview_file_path):
            self.preview_file_path = "{}".format(os.path.join(self.tmp_dir, "current_preview"))
            img = Image.new("RGB", (int(round(self.res_x * self.scale_factor)), int(round(self.res_y * self.scale_factor))))
            img.save(self.preview_file_path, "BMP")
            img.close()

        return Image.open(self.preview_file_path)

    def _use_outer_task_collector(self):
        unsupported_formats = ['EXR', 'EPS']
        if self.output_format.upper() in unsupported_formats:
            return True
        return False

    def _accept_client(self, node_id):
        client = TaskClient.assert_exists(node_id, self.counting_nodes)
        finishing = client.finishing()
        max_finishing = self.max_pending_client_results

        # if client.rejected():
        #     return AcceptClientVerdict.REJECTED
        # elif finishing >= max_finishing or client.started() - finishing >= max_finishing:

        if finishing >= max_finishing or client.started() - finishing >= max_finishing:
            return AcceptClientVerdict.SHOULD_WAIT

        client.start()
        return AcceptClientVerdict.ACCEPTED

    def _choose_adv_ver_file(self, tr_files, subtask_id):
        adv_test_file = None
        if self.advanceVerification:
            if self.__use_adv_verification(subtask_id):
                adv_test_file = random.sample(tr_files, 1)
        return adv_test_file

    @GNRTask.handle_key_error
    def _verify_imgs(self, subtask_id, tr_files):
        res_x, res_y = self._get_part_size(subtask_id)

        adv_test_file = self._choose_adv_ver_file(tr_files, subtask_id)
        x0, y0, x1, y1 = self._get_part_img_size(subtask_id, adv_test_file)

        for tr_file in tr_files:
            if adv_test_file is not None and tr_file in adv_test_file:
                start_box = self._get_box_start(x0, y0, x1, y1)
                logger.debug('testBox: {}'.format(start_box))
                cmp_file, cmp_start_box = self._get_cmp_file(tr_file, start_box, subtask_id)
                logger.debug('cmp_start_box {}'.format(cmp_start_box))
                if not advance_verify_img(tr_file, res_x, res_y, start_box, self.verification_options.box_size,
                                          cmp_file, cmp_start_box):
                    return False
                else:
                    self.verified_clients.append(self.subtasks_given[subtask_id]['node_id'])
            if not self._verify_img(tr_file, res_x, res_y):
                return False

        return True

    def _get_cmp_file(self, tr_file, start_box, subtask_id):
        extra_data, new_start_box = self._change_scope(subtask_id, start_box, tr_file)
        cmp_file = self._run_task(extra_data)
        return cmp_file, new_start_box

    def _get_box_start(self, x0, y0, x1, y1):
        ver_x = min(self.verification_options.box_size[0], x1 - x0)
        ver_y = min(self.verification_options.box_size[1], y1 - y0)
        start_x = get_random(x0, x1 - ver_x)
        start_y = get_random(y0, y1 - ver_y)
        return start_x, start_y

    @GNRTask.handle_key_error
    def _change_scope(self, subtask_id, start_box, tr_file):
        extra_data = copy(self.subtasks_given[subtask_id])
        extra_data['outfilebasename'] = str(uuid.uuid4())
        extra_data['tmp_path'] = os.path.join(self.tmp_dir, str(self.subtasks_given[subtask_id]['start_task']))
        if not os.path.isdir(extra_data['tmp_path']):
            os.mkdir(extra_data['tmp_path'])
        return extra_data, start_box

    def _run_task(self, extra_data):
        computer = LocalComputer(self, self.root_path,
                                 self.__box_rendered,
                                 self.__box_render_error,
                                 lambda: self.query_extra_data_for_advance_verification(extra_data),
                                 additional_resources=[])
        computer.run()
        computer.tt.join()
        results = computer.tt.result.get("data")
        if results:
            commonprefix = os.path.commonprefix(results)
            img = find_file_with_ext(commonprefix, ["." + self.output_format])
            if img is None:
                logger.error("No image file created")
            return img

    def __box_rendered(self, results):
        logger.info("Box for advance verification created")

    def __box_render_error(self, error):
        logger.error("Cannot verify img: {}".format(error))

    @GNRTask.handle_key_error
    def __use_adv_verification(self, subtask_id):
        if self.verification_options.type == 'forAll':
            return True
        if self.verification_options.type == 'forFirst':
            if self.subtasks_given[subtask_id]['node_id'] not in self.verified_clients:
                return True
        if self.verification_options.type == 'random' and get_random_float() < self.verification_options.probability:
            return True
        return False

    def __get_path(self, path):
        if is_windows():
            return self.__get_path_windows(path)
        return path

    def __get_path_windows(self, path):
        return path.replace("\\", "/")