from __future__ import division
import logging
import os
import random
import shutil

from collections import OrderedDict
from PIL import Image, ImageChops, ImageOps

from golem.core.common import timeout_to_deadline, get_golem_path
from golem.core.fileshelper import common_dir, find_file_with_ext, has_ext
from golem.resource.dirmanager import get_test_task_path, find_task_script, get_tmp_path
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ComputeTaskDef
from golem.task.taskstate import SubtaskStatus

from apps.core.task.coretask import TaskTypeInfo, AcceptClientVerdict
from apps.core.task.coretaskstate import Options
from apps.lux.luxenvironment import LuxRenderEnvironment
from apps.lux.resources.scenefileeditor import regenerate_lux_file
from apps.lux.task.verificator import LuxRenderVerificator
from apps.rendering.resources.imgrepr import load_img, blend
from apps.rendering.task.renderingtask import RenderingTask, RenderingTaskBuilder
from apps.rendering.task.renderingtaskstate import RendererDefaults, RenderingTaskDefinition

logger = logging.getLogger("apps.lux")

MERGE_TIMEOUT = 7200

APP_DIR = os.path.join(get_golem_path(), 'apps', 'lux')
PREVIEW_EXT = "BMP"


class LuxRenderDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "exr"
        self.main_program_file = LuxRenderEnvironment().main_program_file
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 5


class LuxRenderTaskTypeInfo(TaskTypeInfo):
    def __init__(self, dialog, customizer):
        super(LuxRenderTaskTypeInfo, self).__init__("LuxRender",
                                                    RenderingTaskDefinition,
                                                    LuxRenderDefaults(),
                                                    LuxRenderOptions,
                                                    LuxRenderTaskBuilder,
                                                    dialog,
                                                    customizer)
        self.output_formats = ["exr", "png", "tga"]
        self.output_file_ext = ["lxs"]

    @classmethod
    def get_task_border(cls, subtask, definition, total_subtasks, output_num=1):
        """ Return list of pixels that should be marked as a border of
         a given subtask
        :param SubtaskState subtask: subtask state description
        :param RenderingTaskDefinition definition: task definition
        :param int total_subtasks: total number of subtasks used in this task
        :param int output_num: number of final output files
        :return list: list of pixels that belong to a subtask border
        """
        preview_x = 300.0
        preview_y = 200.0
        res_x, res_y = definition.resolution
        if res_x == 0 or res_y == 0:
            return []

        if res_x / res_y > preview_x / preview_y:
            scale_factor = preview_x / res_x
        else:
            scale_factor = preview_y / res_y
        scale_factor = min(1.0, scale_factor)

        x = int(round(res_x * scale_factor))
        y = int(round(res_y * scale_factor))
        border = [(0, i) for i in range(y)] + [(x - 1, i) for i in range(y)]
        border += [(i, 0) for i in range(x)] + [(i, y - 1) for i in range(x)]
        return border

    @classmethod
    def get_task_num_from_pixels(cls, x, y, definition, total_subtasks,
                                 output_num=1):
        """
        Compute number of subtask that represents pixel (x, y) on preview
        :param int x: x coordinate
        :param int y: y coordiante
        :param TaskDefintion definition: task definition
        :param int total_subtasks: total number of subtasks used in this task
        :param int output_num: number of final output files
        :return int: subtask's number
        """

        return 1


class LuxRenderOptions(Options):
    def __init__(self):
        super(LuxRenderOptions, self).__init__()
        self.environment = LuxRenderEnvironment()
        self.halttime = 0
        self.haltspp = 1


class LuxTask(RenderingTask):
    ENVIRONMENT_CLASS = LuxRenderEnvironment
    VERIFICATOR_CLASS = LuxRenderVerificator

    ################
    # Task methods #
    ################

    def __init__(self, halttime, haltspp, **kwargs):
        RenderingTask.__init__(self, **kwargs)

        self.tmp_dir = get_tmp_path(self.header.task_id, self.root_path)
        self.undeletable.append(self.__get_test_flm())
        self.halttime = halttime
        self.haltspp = haltspp
        self.verification_error = False
        self.merge_timeout = MERGE_TIMEOUT

        # Is it necessary to load scene_file contents here?
        try:
            with open(self.main_scene_file) as f:
                self.scene_file_src = f.read()
        except IOError as err:
            logger.error("Wrong scene file: {}".format(err))
            self.scene_file_src = ""

        self.output_file, _ = os.path.splitext(self.output_file)
        self.output_format = self.output_format.lower()
        self.num_add = 0

        self.preview_exr = None

    def __getstate__(self):
        state = super(LuxTask, self).__getstate__()
        state['preview_exr'] = None
        return state

    def initialize(self, dir_manager):
        super(LuxTask, self).initialize(dir_manager)
        self.verificator.test_flm = self.__get_test_flm()
        self.verificator.merge_ctd = self.__get_merge_ctd([])

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):
        verdict = self._accept_client(node_id)
        if verdict != AcceptClientVerdict.ACCEPTED:

            should_wait = verdict == AcceptClientVerdict.SHOULD_WAIT
            if should_wait:
                logger.warning("Waiting for results from {}".format(node_name))
            else:
                logger.warning("Client {} banned from this task".format(node_name))

            return self.ExtraData(should_wait=should_wait)

        start_task, end_task = self._get_next_task()
        if start_task is None or end_task is None:
            logger.error("Task already computed")
            return self.ExtraData()

        if self.halttime > 0:
            write_interval = int(self.halttime / 2)
        else:
            write_interval = 60
        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, self.halttime, self.haltspp,
                                        write_interval, [0, 1, 0, 1], self.output_format)
        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        num_threads = max(num_cores, 1)

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "output_format": self.output_format,
                      "scene_file_src": scene_src,
                      "scene_dir": scene_dir,
                      "num_threads": num_threads
                      }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[hash] = extra_data
        self.subtasks_given[hash]['status'] = SubtaskStatus.starting
        self.subtasks_given[hash]['perf'] = perf_index
        self.subtasks_given[hash]['node_id'] = node_id

        ctd = self._new_compute_task_def(hash, extra_data, None, perf_index)
        return self.ExtraData(ctd=ctd)

    ###################
    # CoreTask methods #
    ###################

    def query_extra_data_for_test_task(self):
        self.test_task_res_path = get_test_task_path(self.root_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, 1, 0, 1, [0, 1, 0, 1], self.output_format)
        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        extra_data = {
            "path_root": self.main_scene_dir,
            "start_task": 1,
            "end_task": 1,
            "total_tasks": 1,
            "outfilebasename": self.header.task_id,
            "output_format": self.output_format,
            "scene_file_src": scene_src,
            "scene_dir": scene_dir,
            "num_threads": 1
        }

        hash = "{}".format(random.getrandbits(128))

        return self._new_compute_task_def(hash, extra_data, None, 0)

    def after_test(self, results, tmp_dir):
        # Search for flm - the result of testing a lux task
        # It's needed for verification of received results
        flm = find_file_with_ext(tmp_dir, [".flm"])
        if flm is not None:
            try:
                shutil.copy(flm, self.__get_test_flm())
            except (OSError, IOError) as err:
                logger.warning("Couldn't rename and copy .flm file. {}".format(err))
        else:
            logger.warning("Couldn't find flm file.")
        return None

    def query_extra_data_for_merge(self):

        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, 10, 0,
                                        5, [0, 1, 0, 1], self.output_format)

        scene_dir = os.path.dirname(self._get_scene_file_rel_path())
        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 0,
                      "end_task": 0,
                      "total_tasks": 0,
                      "outfilebasename": self.outfilebasename,
                      "output_format": self.output_format,
                      "scene_file_src": scene_src,
                      "scene_dir": scene_dir,
                      "num_threads": 4}

        return self._new_compute_task_def("FINALTASK", extra_data, scene_dir, 0)

    def query_extra_data_for_final_flm(self):
        files = [os.path.basename(x) for x in self.collected_file_names.values()]
        return self.__get_merge_ctd(files)

    def accept_results(self, subtask_id, result_files):
        super(LuxTask, self).accept_results(subtask_id, result_files)
        num_start = self.subtasks_given[subtask_id]['start_task']
        for tr_file in result_files:
            if has_ext(tr_file, ".flm"):
                self.collected_file_names[num_start] = tr_file
                self.counting_nodes[self.subtasks_given[subtask_id]['node_id']].accept()
                self.num_tasks_received += 1
            elif not has_ext(tr_file, '.log'):
                self.subtasks_given[subtask_id]['preview_file'] = tr_file
                self._update_preview(tr_file, num_start)

        if self.num_tasks_received == self.total_tasks:
            if self.verificator.advanced_verification and os.path.isfile(self.__get_test_flm()):
                self.__generate_final_flm_advanced_verification()
            else:
                self.__generate_final_flm()

    def __get_merge_ctd(self, files):
        script_file = find_task_script(APP_DIR, "docker_luxmerge.py")

        if script_file is None:
            logger.error("Cannot find merger script")
            return

        with open(script_file) as f:
            src_code = f.read()

        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        ctd.subtask_id = self.header.task_id
        ctd.extra_data = {'output_flm': self.output_file, 'flm_files': files}
        ctd.src_code = src_code
        ctd.working_directory = "."
        ctd.docker_images = self.header.docker_images
        ctd.deadline = timeout_to_deadline(self.merge_timeout)
        return ctd

    def _short_extra_data_repr(self, perf_index, extra_data):
        return "start_task: {start_task}, outfilebasename: {outfilebasename}, " \
               "scene_file_src: {scene_file_src}".format(**extra_data)

    def _update_preview(self, new_chunk_file_path, chunk_num):
        self.num_add += 1
        if has_ext(new_chunk_file_path, ".exr"):
            self._update_preview_from_exr(new_chunk_file_path)
        else:
            self.__update_preview_from_pil_file(new_chunk_file_path)

    def _update_task_preview(self):
        pass

    @RenderingTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        preview_files = []
        for sub_id, task in self.subtasks_given.iteritems():
            if sub_id != subtask_id and task['status'] == 'Finished' and 'preview_file' in task:
                preview_files.append(task['preview_file'])

        self.preview_file_path = None
        self.num_add = 0

        for f in preview_files:
            self._update_preview(f, None)
        if len(preview_files) == 0:
            img = self._open_preview()
            img.close()

    def __update_preview_from_pil_file(self, new_chunk_file_path):
        img = Image.open(new_chunk_file_path)
        scaled = img.resize((int(round(self.scale_factor * self.res_x)),
                             int(round(self.scale_factor * self.res_y))),
                            resample=Image.BILINEAR)
        img.close()

        img_current = self._open_preview()
        img_current = ImageChops.blend(img_current, scaled, 1.0 / self.num_add)
        img_current.save(self.preview_file_path, PREVIEW_EXT)
        img.close()
        scaled.close()
        img_current.close()

    def _update_preview_from_exr(self, new_chunk_file):
        if self.preview_exr is None:
            self.preview_exr = load_img(new_chunk_file)
        else:
            self.preview_exr = blend(self.preview_exr, load_img(new_chunk_file),
                                     1.0 / self.num_add)

        img_current = self._open_preview()
        img = self.preview_exr.to_pil()
        scaled = ImageOps.fit(img,
                              (int(round(self.scale_factor * self.res_x)), int(round(self.scale_factor * self.res_y))),
                              method=Image.BILINEAR)
        scaled.save(self.preview_file_path, PREVIEW_EXT)
        img.close()
        scaled.close()
        img_current.close()

    def __generate_final_file(self, flm):
        computer = LocalComputer(self, self.root_path, self.__final_img_ready, self.__final_img_error,
                                 self.query_extra_data_for_merge, additional_resources=[flm])
        computer.run()
        computer.tt.join()

    def __final_img_ready(self, results, time_spent):
        commonprefix = common_dir(results['data'])
        img = find_file_with_ext(commonprefix, ["." + self.output_format])
        if img is None:
            # TODO Maybe we should try again?
            logger.error("No final file generated...")
        else:
            try:
                shutil.copy(img, self.output_file + "." + self.output_format)
            except (IOError, OSError) as err:
                logger.warning("Couldn't rename and copy img file. {}".format(err))

        self.notify_update_task()

    def __final_img_error(self, error):
        logger.error("Cannot generate final image: {}".format(error))
        # TODO What should we do in this situation?

    def __generate_final_flm(self):
        self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
        computer = LocalComputer(self, self.root_path, self.__final_flm_ready, self.__final_flm_failure,
                                 self.query_extra_data_for_final_flm, use_task_resources=False,
                                 additional_resources=self.collected_file_names.values())
        computer.run()
        computer.tt.join()

    def __final_flm_ready(self, results, time_spent):
        commonprefix = common_dir(results['data'])
        flm = find_file_with_ext(commonprefix, [".flm"])
        if flm is None:
            self.__final_flm_failure("No flm file created")
            return
        shutil.copy(flm, os.path.dirname(self.output_file))
        new_flm = os.path.join(os.path.dirname(self.output_file), os.path.basename(flm))
        self.__generate_final_file(new_flm)

    def __final_flm_failure(self, error):
        logger.error("Cannot generate final flm: {}".format(error))
        # TODO What should we do in this sitution?

    def __generate_final_flm_advanced_verification(self):
        # the file containing result of task test
        test_result_flm = self.__get_test_flm()

        new_flm = self.output_file + ".flm"
        shutil.copy(test_result_flm, new_flm)
        logger.debug("Copying " + test_result_flm + " to " + new_flm)
        self.__generate_final_file(new_flm)

    def __get_test_flm(self):
        return os.path.join(self.tmp_dir, "test_result.flm")


class LuxRenderTaskBuilder(RenderingTaskBuilder):
    TASK_CLASS = LuxTask
    DEFAULTS = LuxRenderDefaults

    def get_task_kwargs(self, **kwargs):
        kwargs = super(LuxRenderTaskBuilder, self).get_task_kwargs(**kwargs)
        kwargs['halttime'] = self.task_definition.options.halttime
        kwargs['haltspp'] = self.task_definition.options.haltspp
        return kwargs
