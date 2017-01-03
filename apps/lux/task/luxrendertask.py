import logging
import os
import random
import shutil

from collections import OrderedDict
from PIL import Image, ImageChops, ImageOps

from golem.core.common import timeout_to_deadline, get_golem_path
from golem.core.fileshelper import find_file_with_ext, common_dir
from golem.resource.dirmanager import get_test_task_path, find_task_script, get_tmp_path
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ComputeTaskDef
from golem.task.taskstate import SubtaskStatus

from apps.core.task.gnrtask import GNROptions
from apps.lux.luxenvironment import LuxRenderEnvironment
from apps.lux.resources.scenefileeditor import regenerate_lux_file
from apps.rendering.resources.imgrepr import load_img, blend
from apps.rendering.task.renderingtask import RenderingTask, RenderingTaskBuilder, AcceptClientVerdict
from apps.rendering.task.renderingtaskstate import RendererDefaults, RendererInfo

logger = logging.getLogger("apps.lux")

MERGE_TIMEOUT = 7200

APP_DIR = os.path.join(get_golem_path(), 'apps', 'lux')


class LuxRenderDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "exr"
        self.main_program_file = find_task_script(APP_DIR, "docker_luxtask.py")
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 5


def build_lux_render_info(dialog, customizer):
    defaults = LuxRenderDefaults()

    renderer = RendererInfo("LuxRender", defaults, LuxRenderTaskBuilder, dialog, customizer, LuxRenderOptions)
    renderer.output_formats = ["exr", "png", "tga"]
    renderer.scene_file_ext = ["lxs"]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_border = get_task_border

    return renderer


def get_task_border(subtask, definition, total_subtasks, output_num=1):
    preview_x = 300
    preview_y = 200
    res_x, res_y = definition.resolution
    if res_x != 0 and res_y != 0:
        if float(res_x) / float(res_y) > float(preview_x) / float(preview_y):
            scale_factor = float(preview_x) / float(res_x)
        else:
            scale_factor = float(preview_y) / float(res_y)
        scale_factor = min(1.0, scale_factor)
    else:
        scale_factor = 1.0
    border = []
    x = int(round(res_x * scale_factor))
    y = int(round(res_y * scale_factor))
    for i in range(0, y):
        border.append((0, i))
        border.append((x - 1, i))
    for i in range(0, x):
        border.append((i, 0))
        border.append((i, y - 1))
    return border


def get_task_num_from_pixels(p_x, p_y, definition, total_subtasks, output_num=1):
    return 1


class LuxRenderOptions(GNROptions):
    def __init__(self):
        super(LuxRenderOptions, self).__init__()
        self.environment = LuxRenderEnvironment()
        self.halttime = 0
        self.haltspp = 1


class LuxRenderTaskBuilder(RenderingTaskBuilder):
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)
        if self.task_definition.docker_images is None:
            self.task_definition.docker_images = LuxRenderEnvironment().docker_images

        lux_task = LuxTask(self.node_name,
                           self.task_definition.task_id,
                           main_scene_dir,
                           self.task_definition.main_scene_file,
                           self.task_definition.main_program_file,
                           self._calculate_total(LuxRenderDefaults(), self.task_definition),
                           self.task_definition.resolution[0],
                           self.task_definition.resolution[1],
                           os.path.splitext(os.path.basename(self.task_definition.output_file))[0],
                           self.task_definition.output_file,
                           self.task_definition.output_format,
                           self.task_definition.full_task_timeout,
                           self.task_definition.subtask_timeout,
                           self.task_definition.resources,
                           self.task_definition.estimated_memory,
                           self.root_path,
                           self.task_definition.max_price,
                           self.task_definition.options.halttime,
                           self.task_definition.options.haltspp,
                           docker_images=self.task_definition.docker_images
                           )

        self._set_verification_options(lux_task)
        lux_task.initialize(self.dir_manager)
        return lux_task


class LuxTask(RenderingTask):

    ################
    # Task methods #
    ################

    def __init__(self,
                 node_name,
                 task_id,
                 main_scene_dir,
                 main_scene_file,
                 main_program_file,
                 total_tasks,
                 res_x,
                 res_y,
                 outfilebasename,
                 output_file,
                 output_format,
                 full_task_timeout,
                 subtask_timeout,
                 task_resources,
                 estimated_memory,
                 root_path,
                 max_price,
                 halttime,
                 haltspp,
                 return_address="",
                 return_port=0,
                 key_id="",
                 docker_images=None):
        
        RenderingTask.__init__(self, node_name, task_id, return_address, return_port, key_id,
                               LuxRenderEnvironment.get_id(), full_task_timeout, subtask_timeout,
                               main_program_file, task_resources, main_scene_dir, main_scene_file,
                               total_tasks, res_x, res_y, outfilebasename, output_file, output_format,
                               root_path, estimated_memory, max_price, docker_images)

        self.tmp_dir = get_tmp_path(self.header.task_id, self.root_path)
        self.undeletable.append(self.__get_test_flm())
        self.halttime = halttime
        self.haltspp = haltspp
        self.verification_error = False
        self.merge_timeout = MERGE_TIMEOUT

        try:
            with open(main_scene_file) as f:
                self.scene_file_src = f.read()
        except IOError as err:
            logger.error("Wrong scene file: {}".format(err))
            self.scene_file_src = ""

        self.output_file, _ = os.path.splitext(self.output_file)
        self.output_format = self.output_format.lower()
        self.numAdd = 0

        self.preview_exr = None

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

        working_directory = self._get_working_directory()
        min_x = 0
        max_x = 1
        min_y = (start_task - 1) * (1.0 / float(self.total_tasks))
        max_y = end_task * (1.0 / float(self.total_tasks))

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

        ctd = self._new_compute_task_def(hash, extra_data, working_directory, perf_index)
        return self.ExtraData(ctd=ctd)

    def computation_finished(self, subtask_id, task_result, result_type=0):
        test_result_flm = self.__get_test_flm()

        self.interpret_task_results(subtask_id, task_result, result_type)
        tr_files = self.results[subtask_id]

        if len(tr_files) > 0:
            num_start = self.subtasks_given[subtask_id]['start_task']
            self.subtasks_given[subtask_id]['status'] = SubtaskStatus.finished
            for tr_file in tr_files:
                tr_file = os.path.normpath(tr_file)
                if tr_file.upper().endswith('.FLM'):
                    self.collected_file_names[num_start] = tr_file
                    self.counting_nodes[self.subtasks_given[subtask_id]['node_id']].accept()
                    self.num_tasks_received += 1
                    if self.advanceVerification:
                        if not os.path.isfile(test_result_flm):
                            logger.warning("Advanced verification set, but couldn't find test result!")
                            logger.info("Skipping verification")
                        else:
                            if not self.merge_flm_files(tr_file, test_result_flm):
                                logger.info("Subtask " + str(subtask_id) + " rejected.")
                                self._mark_subtask_failed(subtask_id)
                                self.num_tasks_received -= 1
                            else:
                                logger.info("Subtask " + str(subtask_id) + " successfully verified.")
                elif not tr_file.upper().endswith('.LOG'):
                    self.subtasks_given[subtask_id]['previewFile'] = tr_file
                    self._update_preview(tr_file, num_start)
        else:
            self._mark_subtask_failed(subtask_id)
        if self.num_tasks_received == self.total_tasks:
            if self.advanceVerification and os.path.isfile(test_result_flm):
                self.__generate_final_flm_advanced_verification()
            else:
                self.__generate_final_flm()

    ###################
    # GNRTask methods #
    ###################

    def query_extra_data_for_test_task(self):
        self.test_task_res_path = get_test_task_path(self.root_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, 1, 0, 1, [0, 1, 0, 1], self.output_format)
        working_directory = self._get_working_directory()
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

        return self._new_compute_task_def(hash, extra_data, working_directory, 0)

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

    def merge_flm_files(self, new_flm, output):
        computer = LocalComputer(self, self.root_path, self.__verify_flm_ready, self.__verify_flm_failure,
                                 lambda: self.query_extra_data_for_advance_verification(new_flm),
                                 use_task_resources=False,
                                 additional_resources=[self.__get_test_flm(), new_flm])
        computer.run()
        if computer.tt is not None:
            computer.tt.join()
        else:
            return False
        if self.verification_error:
            return False
        commonprefix = common_dir(computer.tt.result['data'])
        flm = find_file_with_ext(commonprefix, [".flm"])
        logs = find_file_with_ext(commonprefix, [".log"])
        stderr = filter(lambda x: os.path.basename(x) == "stderr.log", computer.tt.result['data'])
        if flm is None or len(stderr) == 0:
            return False
        else:
            try:
                with open(stderr[0]) as f:
                    stderr_in = f.read()
                if "ERROR" in stderr_in:
                    return False
            except (IOError, OSError):
                return False

            shutil.copy(flm, os.path.join(self.tmp_dir, "test_result.flm"))
            return True

    def query_extra_data_for_final_flm(self):
        files = [os.path.basename(x) for x in self.collected_file_names.values()]
        return self.__get_merge_ctd(files)

    def query_extra_data_for_advance_verification(self, new_flm):
        files = [os.path.basename(new_flm), os.path.basename(self.__get_test_flm())]
        return self.__get_merge_ctd(files)

    def __get_merge_ctd(self, files):
        with open(find_task_script(APP_DIR, "docker_luxmerge.py")) as f:
            src_code = f.read()
        if src_code is None:
            logger.error("Cannot find merger script")
            return

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
        self.numAdd += 1
        if new_chunk_file_path.endswith(".exr"):
            self.__update_preview_from_exr(new_chunk_file_path)
        else:
            self.__update_preview_from_pil_file(new_chunk_file_path)
    
    def _update_task_preview(self):
        pass

    @RenderingTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        preview_files = []
        for subId, task in self.subtasks_given.iteritems():
            if subId != subtask_id and task['status'] == 'Finished' and 'previewFile' in task:
                preview_files.append(task['previewFile'])

        self.preview_file_path = None
        self.numAdd = 0

        for f in preview_files:
            self._update_preview(f, None)
        if len(preview_files) == 0:
            img = self._open_preview()
            img.close()

    def __update_preview_from_pil_file(self, new_chunk_file_path):
        img = Image.open(new_chunk_file_path)
        scaled = img.resize((int(round(self.scale_factor * self.res_x)), int(round(self.scale_factor * self.res_y))),
                            resample=Image.BILINEAR)
        img.close()

        img_current = self._open_preview()
        img_current = ImageChops.blend(img_current, scaled, 1.0 / float(self.numAdd))
        img_current.save(self.preview_file_path, "BMP")
        img.close()
        scaled.close()
        img_current.close()

    def __update_preview_from_exr(self, new_chunk_file):
        if self.preview_exr is None:
            self.preview_exr = load_img(new_chunk_file)
        else:
            self.preview_exr = blend(self.preview_exr, load_img(new_chunk_file), 1.0 / float(self.numAdd))

        img_current = self._open_preview()
        img = self.preview_exr.to_pil()
        scaled = ImageOps.fit(img,
                              (int(round(self.scale_factor * self.res_x)), int(round(self.scale_factor * self.res_y))),
                              method=Image.BILINEAR)
        scaled.save(self.preview_file_path, "BMP")
        img.close()
        scaled.close()
        img_current.close()

    def __generate_final_file(self, flm):
        computer = LocalComputer(self, self.root_path, self.__final_img_ready, self.__final_img_error,
                                 self.query_extra_data_for_merge, additional_resources=[flm])
        computer.run()
        computer.tt.join()

    def __verify_flm_ready(self, results):
        logger.info("Advance verification finished")
        self.verification_error = False

    def __verify_flm_failure(self, error):
        logger.info("Advance verification failure {}".format(error))
        self.verification_error = True

    def __final_img_ready(self, results):
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

    def __final_flm_ready(self, results):
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

    def __get_test_flm(self, dir_=None):
        if dir_ is None:
            dir_ = self.tmp_dir
        return os.path.join(dir_, "test_result.flm")
