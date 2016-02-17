import os
import random
import logging
import math

from golem.task.taskstate import SubtaskStatus

from gnr.renderingenvironment import PBRTEnvironment
from gnr.renderingdirmanager import get_test_task_path, find_task_script
from gnr.renderingtaskstate import RendererDefaults, RendererInfo, RenderingTaskDefinition
from gnr.task.scenefileeditor import regenerate_pbrt_file
from gnr.task.gnrtask import GNROptions, GNRTaskBuilder
from gnr.task.renderingtask import RenderingTask, RenderingTaskBuilder
from gnr.task.renderingtaskcollector import RenderingTaskCollector

logger = logging.getLogger(__name__)


class PbrtDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "EXR"
        self.main_program_file = find_task_script("pbrttask.py")
        self.min_subtasks = 4
        self.max_subtasks = 200
        self.default_subtasks = 60


def build_pbrt_renderer_info(dialog, customizer):
    defaults = PbrtDefaults()

    renderer = RendererInfo("PBRT", defaults, PbrtTaskBuilder, dialog, customizer, PbrtRendererOptions)
    renderer.output_formats = ["BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF"]
    renderer.scene_file_ext = ["pbrt"]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_boarder = get_task_boarder

    return renderer


class PbrtRendererOptions(GNROptions):
    def __init__(self):
        self.pbrt_path = ''
        self.pixel_filter = "mitchell"
        self.samples_per_pixel_count = 32
        self.algorithm_type = "lowdiscrepancy"
        self.filters = ["box", "gaussian", "mitchell", "sinc", "triangle"]
        self.path_tracers = ["adaptive", "bestcandidate", "halton", "lowdiscrepancy", "random", "stratified"]

    def add_to_resources(self, resources):
        if os.path.isfile(self.pbrt_path):
            resources.add(os.path.normpath(self.pbrt_path))
        return resources

    def remove_from_resources(self, resources):
        if os.path.normpath(self.pbrt_path) in resources:
            resources.remove(os.path.normpath(self.pbrt_path))
        return resources


class PbrtGNRTaskBuilder(GNRTaskBuilder):
    def build(self):
        if isinstance(self.task_definition, RenderingTaskDefinition):
            rtd = self.task_definition
        else:
            rtd = self.__translate_task_definition()

        pbrt_task_builder = PbrtTaskBuilder(self.node_name, rtd, self.root_path)
        return pbrt_task_builder.build()

    def __translate_task_definition(self):
        rtd = RenderingTaskDefinition()
        rtd.task_id = self.task_definition.task_id
        rtd.full_task_timeout = self.task_definition.full_task_timeout
        rtd.subtask_timeout = self.task_definition.subtask_timeout
        rtd.min_subtask_time = self.task_definition.min_subtask_time
        rtd.resources = self.task_definition.resources
        rtd.estimated_memory = self.task_definition.estimated_memory
        rtd.total_subtasks = self.task_definition.total_subtasks
        rtd.optimize_total = self.task_definition.optimize_total
        rtd.main_program_file = self.task_definition.main_program_file
        rtd.task_type = self.task_definition.task_type
        rtd.verification_options = self.task_definition.verification_options

        rtd.resolution = self.task_definition.options.resolution
        rtd.renderer = self.task_definition.task_type
        rtd.main_scene_file = self.task_definition.options.main_scene_file
        rtd.resources.add(rtd.main_scene_file)
        rtd.output_file = self.task_definition.options.output_file
        rtd.output_format = self.task_definition.options.output_format
        rtd.renderer_options = PbrtRendererOptions()
        rtd.renderer_options.pixel_filter = self.task_definition.options.pixel_filter
        rtd.renderer_options.algorithm_type = self.task_definition.options.algorithm_type
        rtd.renderer_options.samples_per_pixel_count = self.task_definition.options.samples_per_pixel_count
        rtd.renderer_options.pbrt_path = self.task_definition.options.pbrt_path
        return rtd


class PbrtTaskBuilder(RenderingTaskBuilder):
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)

        pbrt_task = PbrtRenderTask(self.node_name,
                                   self.task_definition.task_id,
                                   main_scene_dir,
                                   self.task_definition.main_program_file,
                                   self._calculate_total(PbrtDefaults(), self.task_definition),
                                   20,
                                   4,
                                   self.task_definition.resolution[0],
                                   self.task_definition.resolution[1],
                                   self.task_definition.renderer_options.pixel_filter,
                                   self.task_definition.renderer_options.algorithm_type,
                                   self.task_definition.renderer_options.samples_per_pixel_count,
                                   self.task_definition.renderer_options.pbrt_path,
                                   "temp",
                                   self.task_definition.main_scene_file,
                                   self.task_definition.full_task_timeout,
                                   self.task_definition.subtask_timeout,
                                   self.task_definition.resources,
                                   self.task_definition.estimated_memory,
                                   self.task_definition.output_file,
                                   self.task_definition.output_format,
                                   self.root_path
                                   )

        return self._set_verification_options(pbrt_task)

    def _set_verification_options(self, new_task):
        new_task = RenderingTaskBuilder._set_verification_options(self, new_task)
        if new_task.advanceVerification:
            box_x = min(new_task.verification_options.box_size[0], new_task.task_res_x)
            box_y = min(new_task.verification_options.box_size[1], new_task.task_res_y)
            new_task.box_size = (box_x, box_y)
        return new_task

    def _calculate_total(self, defaults, definition):

        if (not definition.optimize_total) and (
                defaults.min_subtasks <= definition.total_subtasks <= defaults.max_subtasks):
            return definition.total_subtasks

        task_base = 1000000
        all_op = definition.resolution[0] * definition.resolution[
            1] * definition.renderer_options.samples_per_pixel_count
        return max(defaults.min_subtasks, min(defaults.max_subtasks, all_op / task_base))


def count_subtask_reg(total_tasks, subtasks, res_x, res_y):
    nx = total_tasks * subtasks
    ny = 1
    while (nx % 2 == 0) and (2 * res_x * ny < res_y * nx):
        nx /= 2
        ny *= 2
    task_res_x = float(res_x) / float(nx)
    task_res_y = float(res_y) / float(ny)
    return nx, ny, task_res_x, task_res_y


class PbrtRenderTask(RenderingTask):

    ################
    # Task methods #
    ################

    def __init__(self,
                 node_name,
                 task_id,
                 main_scene_dir,
                 main_program_file,
                 total_tasks,
                 num_subtasks,
                 num_cores,
                 res_x,
                 res_y,
                 pixel_filter,
                 sampler,
                 samples_per_pixel,
                 pbrt_path,
                 outfilebasename,
                 scene_file,
                 full_task_timeout,
                 subtask_timeout,
                 task_resources,
                 estimated_memory,
                 output_file,
                 output_format,
                 root_path,
                 return_address="",
                 return_port=0,
                 key_id=""
                 ):

        RenderingTask.__init__(self, node_name, task_id, return_address, return_port, key_id,
                               PBRTEnvironment.get_id(), full_task_timeout, subtask_timeout,
                               main_program_file, task_resources, main_scene_dir, scene_file,
                               total_tasks, res_x, res_y, outfilebasename, output_file, output_format,
                               root_path, estimated_memory)

        self.collected_file_names = set()

        self.num_subtasks = num_subtasks
        self.num_cores = num_cores

        try:
            with open(scene_file) as f:
                self.scene_file_src = f.read()
        except IOError as err:
            logger.error("Wrong scene file: {}".format(err))
            self.scene_file_src = ""

        self.res_x = res_x
        self.res_y = res_y
        self.pixel_filter = pixel_filter
        self.sampler = sampler
        self.samples_per_pixel = samples_per_pixel
        self.pbrt_path = pbrt_path
        self.nx, self.ny, self.task_res_x, self.task_res_y = count_subtask_reg(self.total_tasks, self.num_subtasks,
                                                                               self.res_x, self.res_y)

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):
        if not self._accept_client(node_id):
            logger.warning(" Client {} banned from this task ".format(node_name))
            return None

        start_task, end_task = self._get_next_task(perf_index)
        if start_task is None or end_task is None:
            logger.error("Task already computed")
            return None

        if num_cores == 0:
            num_cores = self.num_cores

        working_directory = self._get_working_directory()
        scene_src = regenerate_pbrt_file(self.scene_file_src, self.res_x, self.res_y, self.pixel_filter,
                                         self.sampler, self.samples_per_pixel)

        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        pbrt_path = self.__get_pbrt_rel_path()

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
                      "total_tasks": self.total_tasks,
                      "num_subtasks": self.num_subtasks,
                      "num_cores": num_cores,
                      "outfilebasename": self.outfilebasename,
                      "scene_file_src": scene_src,
                      "scene_dir": scene_dir,
                      "pbrt_path": pbrt_path
                      }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[hash] = extra_data
        self.subtasks_given[hash]['status'] = SubtaskStatus.starting
        self.subtasks_given[hash]['perf'] = perf_index
        self.subtasks_given[hash]['node_id'] = node_id

        self._update_task_preview()

        return self._new_compute_task_def(hash, extra_data, working_directory, perf_index)

    def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):

        if not self.should_accept(subtask_id):
            return

        tmp_dir = dir_manager.get_task_temporary_dir(self.header.task_id, create=False)
        self.tmp_dir = tmp_dir
        tr_files = self.load_task_results(task_result, result_type, tmp_dir)
        tr_files = self.filter_task_results(tr_files, subtask_id)

        if not self._verify_imgs(subtask_id, tr_files):
            self._mark_subtask_failed(subtask_id)
            self._update_task_preview()
            return

        if len(task_result) > 0:
            self.subtasks_given[subtask_id]['status'] = SubtaskStatus.finished
            for tr_file in tr_files:
                self.collected_file_names.add(tr_file)
                self.num_tasks_received += 1
                self.counting_nodes[self.subtasks_given[subtask_id]['node_id']] = 1

                self._update_preview(tr_file)
                self._update_task_preview()
        else:
            self._mark_subtask_failed(subtask_id)
            self._update_task_preview()

        if self.num_tasks_received == self.total_tasks:
            output_file_name = u"{}".format(self.output_file, self.output_format)
            if self.output_format != "EXR":
                collector = RenderingTaskCollector()
                for file in self.collected_file_names:
                    collector.add_img_file(file)
                collector.finalize().save(output_file_name, self.output_format)
                self.preview_file_path = output_file_name
            else:
                self._put_collected_files_together(output_file_name, list(self.collected_file_names), "add")

    def restart(self):
        RenderingTask.restart(self)
        self.collected_file_names = set()

    def restart_subtask(self, subtask_id):
        if self.subtasks_given[subtask_id]['status'] == SubtaskStatus.finished:
            self.num_tasks_received += 1
        RenderingTask.restart_subtask(self, subtask_id)
        self._update_task_preview()

    def get_price_mod(self, subtask_id):
        if subtask_id not in self.subtasks_given:
            logger.error("Not my subtask {}".format(subtask_id))
            return 0
        perf = (self.subtasks_given[subtask_id]['end_task'] - self.subtasks_given[subtask_id]['start_task'])
        perf *= float(self.subtasks_given[subtask_id]['perf']) / 1000
        return perf

    ###################
    # GNRTask methods #
    ###################

    def query_extra_data_for_test_task(self):

        working_directory = self._get_working_directory()

        scene_src = regenerate_pbrt_file(self.scene_file_src, 1, 1, self.pixel_filter, self.sampler,
                                         self.samples_per_pixel)

        pbrt_path = self.__get_pbrt_rel_path()
        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 0,
                      "end_task": 1,
                      "total_tasks": self.total_tasks,
                      "num_subtasks": self.num_subtasks,
                      "num_cores": self.num_cores,
                      "outfilebasename": self.outfilebasename,
                      "scene_file_src": scene_src,
                      "scene_dir": scene_dir,
                      "pbrt_path": pbrt_path
                      }

        hash = "{}".format(random.getrandbits(128))

        self.test_task_res_path = get_test_task_path(self.root_path)
        logger.debug(self.test_task_res_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        return self._new_compute_task_def(hash, extra_data, working_directory, 0)



    def _get_next_task(self, perf_index):
        if self.last_task != self.total_tasks:
            perf = max(int(float(perf_index) / 1500), 1)
            end_task = min(self.last_task + perf, self.total_tasks)
            start_task = self.last_task
            self.last_task = end_task
            return start_task, end_task
        else:
            for sub in self.subtasks_given.values():
                if sub['status'] == SubtaskStatus.failure:
                    sub['status'] = SubtaskStatus.resent
                    end_task = sub['end_task']
                    start_task = sub['start_task']
                    self.num_failed_subtasks -= 1
                    return start_task, end_task
        return None, None

    def _short_extra_data_repr(self, perf_index, extra_data):
        return "path_root: {path_root}, start_task: {start_task}, end_task: {end_task}, total_tasks: {total_tasks}, " \
               "num_subtasks: {num_subtasks}, num_cores: {num_cores}, outfilebasename: {outfilebasename}, " \
               "scene_file_src: {scene_file_src}".format(**extra_data)

    def _get_part_img_size(self, subtask_id, adv_test_file):
        if adv_test_file is not None:
            num_task = self.__get_num_from_file_name(adv_test_file[0], subtask_id)
        else:
            num_task = self.subtasks_given[subtask_id]['start_task']
        num_subtask = random.randint(0, self.num_subtasks - 1)
        num = num_task * self.num_subtasks + num_subtask
        x0 = int(round((num % self.nx) * self.task_res_x))
        x1 = int(round(((num % self.nx) + 1) * self.task_res_x))
        y0 = int(math.floor((num / self.nx) * self.task_res_y))
        y1 = int(math.floor(((num / self.nx) + 1) * self.task_res_y))
        return x0, y0, x1, y1

    def _mark_task_area(self, subtask, img_task, color):
        for num_task in range(subtask['start_task'], subtask['end_task']):
            for sb in range(0, self.num_subtasks):
                num = self.num_subtasks * num_task + sb
                tx = num % self.nx
                ty = num / self.nx
                x_l = tx * self.task_res_x
                x_r = (tx + 1) * self.task_res_x
                y_l = ty * self.task_res_y
                y_r = (ty + 1) * self.task_res_y

                for i in range(int(round(x_l)), int(round(x_r))):
                    for j in range(int(math.floor(y_l)), int(math.floor(y_r))):
                        img_task.putpixel((i, j), color)

    def _change_scope(self, subtask_id, start_box, tr_file):
        extra_data, start_box = RenderingTask._change_scope(self, subtask_id, start_box, tr_file)
        extra_data["outfilebasename"] = str(extra_data["outfilebasename"])
        extra_data["resourcePath"] = os.path.dirname(self.main_program_file)
        extra_data["tmp_path"] = self.tmp_dir
        extra_data["total_tasks"] = self.total_tasks * self.num_subtasks
        extra_data["num_subtasks"] = 1
        extra_data["start_task"] = get_task_num_from_pixels(start_box[0], start_box[1], extra_data["total_tasks"],
                                                            self.res_x, self.res_y, 1) - 1
        extra_data["end_task"] = extra_data["start_task"] + 1

        return extra_data, start_box

    def __get_pbrt_rel_path(self):
        pbrt_rel = os.path.relpath(os.path.dirname(self.pbrt_path), os.path.dirname(self.main_scene_file))
        pbrt_rel = os.path.join(pbrt_rel, os.path.basename(self.pbrt_path))
        return pbrt_rel

    def __get_num_from_file_name(self, file_, subtask_id):
        try:
            file_name = os.path.basename(file_)
            file_name, ext = os.path.splitext(file_name)
            idx = file_name.find(BASENAME)
            return int(file_name[idx + len(BASENAME):])
        except Exception as err:
            logger.error("Wrong output file name {}: {}".format(file_, err))
            return self.subtasks_given[subtask_id]['start_task']


BASENAME = "temp"


def get_task_num_from_pixels(p_x, p_y, total_tasks, res_x=300, res_y=200, subtasks=20):
    nx, ny, task_res_x, task_res_y = count_subtask_reg(total_tasks, subtasks, res_x, res_y)
    num_x = int(math.floor(p_x / task_res_x))
    num_y = int(math.floor(p_y / task_res_y))
    num = (num_y * nx + num_x) / subtasks + 1
    return num


def get_task_boarder(start_task, end_task, total_tasks, res_x=300, res_y=200, num_subtasks=20):
    boarder = []
    new_left = True
    last_right = None
    for num_task in range(start_task, end_task):
        for sb in range(num_subtasks):
            num = num_subtasks * num_task + sb
            nx, ny, task_res_x, task_res_y = count_subtask_reg(total_tasks, num_subtasks, res_x, res_y)
            tx = num % nx
            ty = num / nx
            x_l = int(round(tx * task_res_x))
            x_r = int(round((tx + 1) * task_res_x))
            y_l = int(round(ty * task_res_y))
            y_r = int(round((ty + 1) * task_res_y))
            for i in range(x_l, x_r):
                if (i, y_l) in boarder:
                    boarder.remove((i, y_l))
                else:
                    boarder.append((i, y_l))
                boarder.append((i, y_r))
            if x_l == 0:
                new_left = True
            if new_left:
                for i in range(y_l, y_r):
                    boarder.append((x_l, i))
                new_left = False
            if x_r == res_y:
                for i in range(y_l, y_r):
                    boarder.append((x_r, i))
            last_right = (x_r, y_l, y_r)
    x_r, y_l, y_r = last_right
    for i in range(y_l, y_r):
        boarder.append((x_r, i))
    return boarder
