import logging
import random
import os
import tempfile
import subprocess
import shutil
from collections import OrderedDict
from PIL import Image, ImageChops

from golem.core.common import get_golem_path
from golem.core.simpleexccmd import exec_cmd
from golem.core.common import get_golem_path
from golem.task.taskstate import SubtaskStatus
from golem.environments.environment import Environment

from gnr.renderingtaskstate import RendererDefaults, RendererInfo
from gnr.renderingenvironment import LuxRenderEnvironment
from gnr.renderingdirmanager import get_test_task_path, find_task_script, get_tmp_path
from gnr.task.imgrepr import load_img, blend
from gnr.task.gnrtask import GNROptions, check_subtask_id_wrapper
from gnr.task.renderingtask import RenderingTask, RenderingTaskBuilder
from gnr.task.scenefileeditor import regenerate_lux_file

logger = logging.getLogger(__name__)


def merge_flm_files(flm_to_verify_and_merge_filename, output_flm_filename):
    p = subprocess.Popen(["luxmerger", output_flm_filename, flm_to_verify_and_merge_filename, "-o", output_flm_filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if "ERROR" in err:
        return False
    else:
        return True


class LuxRenderDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "EXR"
        self.main_program_file = find_task_script("luxtask.py")
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 5


def build_lux_render_info(dialog, customizer):
    defaults = LuxRenderDefaults()

    renderer = RendererInfo("LuxRender", defaults, LuxRenderTaskBuilder, dialog, customizer, LuxRenderOptions)
    renderer.output_formats = ["EXR", "PNG", "TGA"]
    renderer.scene_file_ext = ["lxs"]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_boarder = get_task_boarder

    return renderer


def get_task_boarder(start_task, end_task, total_tasks, res_x=300, res_y=200, num_subtasks=20):
    boarder = []
    for i in range(0, res_y):
        boarder.append((0, i))
        boarder.append((res_x - 1, i))
    for i in range(0, res_x):
        boarder.append((i, 0))
        boarder.append((i, res_y - 1))
    return boarder


def get_task_num_from_pixels(p_x, p_y, total_tasks, res_x=300, res_y=200):
    return 1


class LuxRenderOptions(GNROptions):
    def __init__(self):
        self.environment = LuxRenderEnvironment()
        self.halttime = 600
        self.haltspp = 1
        self.send_binaries = False
        self.luxconsole = self.environment.get_lux_console()

    def add_to_resources(self, resources):
        if self.send_binaries and os.path.isfile(self.luxconsole):
            resources.add(os.path.normpath(self.luxconsole))
        return resources

    def remove_from_resources(self, resources):
        if self.send_binaries and os.path.normpath(self.luxconsole) in resources:
            resources.remove(os.path.normpath(self.luxconsole))
        return resources


class LuxRenderTaskBuilder(RenderingTaskBuilder):
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)

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
                           self.task_definition.renderer_options.halttime,
                           self.task_definition.renderer_options.haltspp,
                           self.task_definition.renderer_options.send_binaries,
                           self.task_definition.renderer_options.luxconsole,
                           )

        return self._set_verification_options(lux_task)


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
                 own_binaries,
                 luxconsole,
                 return_address="",
                 return_port=0,
                 key_id=""):
        
        RenderingTask.__init__(self, node_name, task_id, return_address, return_port, key_id,
                               LuxRenderEnvironment.get_id(), full_task_timeout, subtask_timeout,
                               main_program_file, task_resources, main_scene_dir, main_scene_file,
                               total_tasks, res_x, res_y, outfilebasename, output_file, output_format,
                               root_path, estimated_memory, max_price)
        self.undeletable.append(os.path.join(get_tmp_path(self.header.node_name, self.header.task_id, self.root_path), "test_result.flm"))
        self.halttime = halttime
        self.haltspp = haltspp
        self.own_binaries = own_binaries
        self.luxconsole = luxconsole

        try:
            with open(main_scene_file) as f:
                self.scene_file_src = f.read()
        except IOError as err:
            logger.error("Wrong scene file: {}".format(err))
            self.scene_file_src = ""

        self.output_file, _ = os.path.splitext(self.output_file)
        self.numAdd = 0

        self.preview_exr = None
        if self.own_binaries:
            self.header.environment = Environment.get_id()

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):
        if not self._accept_client(node_id):
            logger.warning(" Client {} banned from this task ".format(node_name))
            return None

        start_task, end_task = self._get_next_task()
        if start_task is None or end_task is None:
            logger.error("Task already computed")
            return None

        working_directory = self._get_working_directory()
        min_x = 0
        max_x = 1
        min_y = (start_task - 1) * (1.0 / float(self.total_tasks))
        max_y = (end_task) * (1.0 / float(self.total_tasks))

        if self.halttime > 0:
            write_interval = int(self.halttime / 2)
        else:
            write_interval = 60
        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, self.halttime, self.haltspp,
                                        write_interval, [0, 1, 0, 1], "PNG")
        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        if self.own_binaries:
            lux_console = self._get_lux_console_rel_path()
        else:
            lux_console = 'luxconsole.exe'

        num_threads = max(num_cores, 1)

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file_src": scene_src,
                      "scene_dir": scene_dir,
                      "num_threads": num_threads,
                      "own_binaries": self.own_binaries,
                      "lux_console": lux_console
                      }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[hash] = extra_data
        self.subtasks_given[hash]['status'] = SubtaskStatus.starting
        self.subtasks_given[hash]['perf'] = perf_index
        self.subtasks_given[hash]['node_id'] = node_id

        return self._new_compute_task_def(hash, extra_data, working_directory, perf_index)

    def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):
        tmp_dir = get_tmp_path(self.header.node_name, self.header.task_id, self.root_path)
        self.tmp_dir = tmp_dir
        env = LuxRenderEnvironment()
        lux_merger = env.get_lux_merger()
        test_result_flm = os.path.join(tmp_dir, "test_result.flm")

        self.interpret_task_results(subtask_id, task_result, result_type, tmp_dir)
        tr_files = self.results[subtask_id]

        if len(tr_files) > 0:
            num_start = self.subtasks_given[subtask_id]['start_task']
            self.subtasks_given[subtask_id]['status'] = SubtaskStatus.finished
            for tr_file in tr_files:
                _, ext = os.path.splitext(tr_file)
                if ext == '.flm':
                    self.collected_file_names[num_start] = tr_file
                    self.num_tasks_received += 1
                    self.counting_nodes[self.subtasks_given[subtask_id]['node_id']] = 1
                    if self.advanceVerification and not os.path.isfile(test_result_flm):
                        logger.warning("Advanced verification set, but couldn't find test result!")
                        logger.info("Skipping verification")
                    elif self.advanceVerification and (lux_merger is not None):
                        if not merge_flm_files(tr_file, test_result_flm):
                            logger.info("Subtask " + str(subtask_id) + " rejected.")
                            self._mark_subtask_failed(subtask_id)
                        else:
                            logger.info("Subtask " + str(subtask_id) + " successfuly verified.")
                elif ext != '.log':
                    self.subtasks_given[subtask_id]['previewFile'] = tr_file
                    self._update_preview(tr_file, num_start)
        else:
            self._mark_subtask_failed(subtask_id)
        if self.num_tasks_received == self.total_tasks:
            if self.advanceVerification and os.path.isfile(test_result_flm):
                self.__generate_final_flm_advanced_verification()
            else:
                self.__generate_final_flm()
            self.__generate_final_file()

    ###################
    # GNRTask methods #
    ###################

    def query_extra_data_for_test_task(self):
        self.test_task_res_path = get_test_task_path(self.root_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, 1, 0, 1, [0, 1, 0, 1], "PNG")
        working_directory = self._get_working_directory()
        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        if self.own_binaries:
            lux_console = self._get_lux_console_rel_path()
        else:
            lux_console = 'luxconsole.exe'

        extra_data = {
            "path_root": self.main_scene_dir,
            "start_task": 1,
            "end_task": 1,
            "total_tasks": 1,
            "outfilebasename": self.header.task_id,
            "scene_file_src": scene_src,
            "scene_dir": scene_dir,
            "num_threads": 1,
            "own_binaries": self.own_binaries,
            "lux_console": lux_console
        }

        hash = "{}".format(random.getrandbits(128))

        return self._new_compute_task_def(hash, extra_data, working_directory, 0)

    def _short_extra_data_repr(self, perf_index, extra_data):
        return "start_task: {start_task}, outfilebasename: {outfilebasename}, " \
               "scene_file_src: {scene_file_src}".format(**extra_data)

    def _update_preview(self, new_chunk_file_path, chunk_num):
        self.numAdd += 1
        if new_chunk_file_path.endswith(".exr"):
            self.__update_preview_from_exr(new_chunk_file_path)
        else:
            self.__update_preview_from_pil_file(new_chunk_file_path)

    @check_subtask_id_wrapper
    def _remove_from_preview(self, subtask_id):
        preview_files = []
        for subId, task in self.subtasks_given.iteritems():
            if subId != subtask_id and task['status'] == 'Finished' and 'previewFile' in task:
                preview_files.append(task['previewFile'])

        self.preview_file_path = None
        self.numAdd = 0
        for f in preview_files:
            self._update_preview(f, None)

    def _get_lux_console_rel_path(self):
        luxconsole_rel = os.path.relpath(os.path.dirname(self.luxconsole), os.path.dirname(self.main_scene_file))
        luxconsole_rel = os.path.join(luxconsole_rel, os.path.basename(self.luxconsole))
        return luxconsole_rel

    def __update_preview_from_pil_file(self, new_chunk_file_path):
        img = Image.open(new_chunk_file_path)

        img_current = self._open_preview()
        img_current = ImageChops.blend(img_current, img, 1.0 / float(self.numAdd))
        img_current.save(self.preview_file_path, "BMP")

    def __update_preview_from_exr(self, new_chunk_file):
        if self.preview_exr is None:
            self.preview_exr = load_img(new_chunk_file)
        else:
            self.preview_exr = blend(self.preview_exr, load_img(new_chunk_file), 1.0 / float(self.numAdd))

        img_current = self._open_preview()
        img = self.preview_exr.to_pil()
        img.save(self.preview_file_path, "BMP")

    def __format_lux_render_cmd(self, scene_file):
        env = LuxRenderEnvironment()
        cmd_file = env.get_lux_console()
        logger.debug("Luxconsole file name: " + str(cmd_file))
        output_flm = "{}.flm".format(self.output_file)
        cmd = '"{}" "{}" -R "{}" -o "{}" '.format(cmd_file, scene_file, output_flm, self.output_file)
        logger.debug("Last flm cmd {}".format(cmd))
        prev_path = os.getcwd()
        os.chdir(os.path.dirname(self.main_scene_file))
        exec_cmd(cmd)
        os.chdir(prev_path)

    def __generate_final_file(self):

        if self.halttime > 0:
            write_interval = int(self.halttime / 2)
        else:
            write_interval = 60

        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, self.halttime, self.haltspp,
                                        write_interval, [0, 1, 0, 1], self.output_format)
        dir_name = os.path.dirname(self.main_scene_file)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lxs", dir=dir_name, delete=False) as tmp_scene_file:
            tmp_scene_file.write(scene_src)
        self.__format_lux_render_cmd(tmp_scene_file.name)

        os.remove(tmp_scene_file.name)

    def __generate_final_flm(self):
        # output flm
        output_file_name = u"{}".format(self.output_file, self.output_format)
        self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
        files = " ".join(self.collected_file_names.values())
        env = LuxRenderEnvironment()
        lux_merger = env.get_lux_merger()
        if lux_merger is not None:
            cmd = "{} -o {}.flm {}".format(lux_merger, self.output_file, files)

            logger.debug("Lux Merger cmd: {}".format(cmd))
            exec_cmd(cmd)

    def __generate_final_flm_advanced_verification(self):
        # the file containing result of task test
        test_result_flm = os.path.join(self.tmp_dir, "test_result.flm")
        
        shutil.copy(test_result_flm, self.output_file + ".flm")
        logger.debug("Copying " + test_result_flm + " to " + self.output_file + ".flm")

