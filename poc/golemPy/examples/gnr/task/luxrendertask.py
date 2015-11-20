import logging
import random
import os
import tempfile

from collections import OrderedDict
from PIL import Image, ImageChops

from golem.core.simpleexccmd import exec_cmd
from golem.task.taskstate import SubtaskStatus
from golem.environments.environment import Environment

from  examples.gnr.renderingtaskstate import RendererDefaults, RendererInfo
from examples.gnr.renderingenvironment import LuxRenderEnvironment
from examples.gnr.renderingdirmanager import get_test_task_path
from examples.gnr.task.imgrepr import load_img, blend
from  examples.gnr.task.gnrtask import GNROptions, check_subtask_id_wrapper
from  examples.gnr.task.renderingtask import RenderingTask, RenderingTaskBuilder
from examples.gnr.task.scenefileeditor import regenerate_lux_file
from examples.gnr.ui.luxrenderdialog import LuxRenderDialog
from examples.gnr.customizers.luxrenderdialogcustomizer import LuxRenderDialogCustomizer

logger = logging.getLogger(__name__)

##############################################
def build_lux_render_info():
    defaults = RendererDefaults()
    defaults.output_format = "EXR"
    defaults.main_program_file = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/tasks/luxTask.py'))
    defaults.min_subtasks = 1
    defaults.max_subtasks = 100
    defaults.default_subtasks = 5

    renderer = RendererInfo("LuxRender", defaults, LuxRenderTaskBuilder, LuxRenderDialog, LuxRenderDialogCustomizer, LuxRenderOptions)
    renderer.output_formats = ["EXR", "PNG", "TGA"]
    renderer.scene_file_ext = [ "lxs" ]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_boarder = get_task_boarder

    return renderer

def get_task_boarder(start_task, end_task, total_tasks, res_x = 300 , res_y = 200, num_subtasks = 20):
    boarder = []
    for i in range(0, res_y):
        boarder.append((0, i))
        boarder.append((res_x - 1, i))
    for i in range(0, res_x):
        boarder.append((i, 0))
        boarder.append((i, res_y - 1))
    return boarder

def get_task_num_from_pixels(p_x, p_y, total_tasks, res_x = 300, res_y = 200):
    return 1

##############################################
class LuxRenderOptions(GNROptions):

    #######################
    def __init__(self):
        self.environment = LuxRenderEnvironment()
        self.halttime = 600
        self.haltspp = 1
        self.send_binaries = False
        self.luxconsole = self.environment.get_lux_console()

    #######################
    def add_to_resources(self, resources):
        if self.send_binaries and os.path.isfile(self.luxconsole):
            resources.add(os.path.normpath(self.luxconsole))
        return resources

    #######################
    def remove_from_resources(self, resources):
        if self.send_binaries and os.path.normpath(self.luxconsole) in resources:
            resources.remove(os.path.normpath(self.luxconsole))
        return resources

##############################################
class LuxRenderTaskBuilder(RenderingTaskBuilder):
    #######################
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)

        lux_task = LuxTask( self.client_id,
                            self.task_definition.task_id,
                            main_scene_dir,
                            self.task_definition.main_scene_file,
                            self.task_definition.main_program_file,
                            self._calculate_total(build_lux_render_info(), self.task_definition),
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
                            self.task_definition.renderer_options.halttime,
                            self.task_definition.renderer_options.haltspp,
                            self.task_definition.renderer_options.send_binaries,
                            self.task_definition.renderer_options.luxconsole
       )

        return self._set_verification_options(lux_task)

##############################################
class LuxTask(RenderingTask):
    #######################
    def __init__(  self,
                    client_id,
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
                    halttime,
                    haltspp,
                    own_binaries,
                    luxconsole,
                    return_address = "",
                    return_port = 0,
                    key_id = ""):

        RenderingTask.__init__(self, client_id, task_id, return_address, return_port, key_id,
                                 LuxRenderEnvironment.get_id(), full_task_timeout, subtask_timeout,
                                 main_program_file, task_resources, main_scene_dir, main_scene_file,
                                 total_tasks, res_x, res_y, outfilebasename, output_file, output_format,
                                 root_path, estimated_memory)

        self.halttime = halttime
        self.haltspp = haltspp
        self.own_binaries = own_binaries
        self.luxconsole = luxconsole

        try:
            with open(main_scene_file) as f:
                self.scene_file_src = f.read()
        except Exception, err:
            logger.error("Wrong scene file: {}".format(str(err)))
            self.scene_file_src = ""

        self.output_file, _ = os.path.splitext(self.output_file)
        self.numAdd = 0

        self.preview_exr = None
        if self.own_binaries:
            self.header.environment = Environment.get_id()

    #######################
    def query_extra_data(self, perf_index, num_cores = 0, client_id = None):
        if not self._accept_client(client_id):
            logger.warning(" Client {} banned from this task ".format(client_id))
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
            write_interval =  int(self.halttime / 2)
        else:
            write_interval = 60
        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, self.halttime, self.haltspp, write_interval, [0, 1, 0, 1], "PNG")
        scene_dir= os.path.dirname(self._get_scene_file_rel_path())

        if self.own_binaries:
            lux_console = self._get_lux_console_rel_path()
        else:
            lux_console = 'luxconsole.exe'

        num_threads = max(num_cores, 1)

        extra_data =          {      "path_root" : self.main_scene_dir,
                                    "start_task" : start_task,
                                    "end_task" : end_task,
                                    "total_tasks" : self.total_tasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_file_src" : scene_src,
                                    "scene_dir": scene_dir,
                                    "num_threads": num_threads,
                                    "own_binaries": self.own_binaries,
                                    "lux_console": lux_console
                                }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[ hash ] = extra_data
        self.subtasks_given[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subtasks_given[ hash ][ 'perf' ] = perf_index
        self.subtasks_given[ hash ][ 'client_id' ] = client_id

        return self._new_compute_task_def(hash, extra_data, working_directory, perf_index)


    #######################
    def query_extra_data_for_test_task(self):
        self.test_task_res_path = get_test_task_path(self.root_path)
        logger.debug(self.test_task_res_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        scene_src = regenerate_lux_file(self.scene_file_src, 1, 1, 5, 0, 1, [0, 1, 0, 1 ], "PNG")
        working_directory = self._get_working_directory()
        scene_dir= os.path.dirname(self._get_scene_file_rel_path())

        if self.own_binaries:
            lux_console = self._get_lux_console_rel_path()
        else:
            lux_console = 'luxconsole.exe'

        extra_data = {
            "path_root" : self.main_scene_dir,
            "start_task": 1,
            "end_task": 1,
            "total_tasks": 1,
            "outfilebasename": self.outfilebasename,
            "scene_file_src": scene_src,
            "scene_dir": scene_dir,
            "num_threads": 1,
            "own_binaries": self.own_binaries,
            "lux_console": lux_console
        }

        hash = "{}".format(random.getrandbits(128))


        return self._new_compute_task_def(hash, extra_data, working_directory, 0)

    #######################
    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        return "start_task: {}, outfilebasename: {}, scene_file_src: {}".format(l['start_task'], l['outfilebasename'], l['scene_file_src'])

    #######################
    def computation_finished(self, subtask_id, task_result, dir_manager = None, result_type = 0):
        tmp_dir = dir_manager.get_task_temporary_dir(self.header.task_id, create = False)
        self.tmp_dir = tmp_dir

        tr_files = self.load_task_results(task_result, result_type, tmp_dir)

        if len(task_result) > 0:
            num_start = self.subtasks_given[ subtask_id ][ 'start_task' ]
            self.subtasks_given[ subtask_id ][ 'status' ] = SubtaskStatus.finished
            for tr_file in tr_files:
                _, ext = os.path.splitext(tr_file)
                if ext == '.flm':
                    self.collected_file_names[ num_start ] = tr_file
                    self.num_tasks_received += 1
                    self.counting_nodes[ self.subtasks_given[ subtask_id ][ 'client_id' ] ] = 1
                else:
                    self.subtasks_given[ subtask_id ][ 'previewFile' ] = tr_file
                    self._update_preview(tr_file, num_start)
        else:
            self._mark_subtask_failed(subtask_id)

        if self.num_tasks_received == self.total_tasks:
            self.__generate_final_flm()
            self.__generate_final_file()

    #######################
    def __generate_final_flm(self):
        output_file_name = u"{}".format(self.output_file, self.output_format)
        self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
        files = " ".join(self.collected_file_names.values())
        env = LuxRenderEnvironment()
        lux_merger = env.get_lux_merger()
        if lux_merger is not None:
            cmd = "{} -o {}.flm {}".format(lux_merger, self.output_file, files)

            logger.debug("Lux Merger cmd: {}".format(cmd))
            exec_cmd(cmd)

    #######################
    def __generate_final_file(self):

        if self.halttime > 0:
            write_interval =  int(self.halttime / 2)
        else:
            write_interval = 60

        scene_src = regenerate_lux_file(self.scene_file_src, self.res_x, self.res_y, self.halttime, self.haltspp, write_interval, [0, 1, 0, 1], self.output_format)

        tmp_scene_file = self.__write_tmp_scene_file(scene_src)
        self.__format_lux_render_cmd(tmp_scene_file)

    #######################
    def __write_tmp_scene_file(self, scene_file_src):
        tmp_scene_file = tempfile.TemporaryFile(suffix = ".lxs", dir = os.path.dirname(self.main_scene_file))
        tmp_scene_file.close()
        with open(tmp_scene_file.name, 'w') as f:
            f.write(scene_file_src)
        return tmp_scene_file.name

    #######################
    def __format_lux_render_cmd(self, scene_file):
        cmd_file = LuxRenderEnvironment().get_lux_console()
        output_flm = "{}.flm".format(self.output_file)
        cmd = '"{}" "{}" -R "{}" -o "{}" '.format(cmd_file, scene_file, output_flm, self.output_file)
        logger.debug("Last flm cmd {}".format(cmd))
        prev_path = os.getcwd()
        os.chdir(os.path.dirname(self.main_scene_file))
        exec_cmd(cmd)
        os.chdir(prev_path)

    #######################
    def _update_preview(self, new_chunk_file_path, chunk_num):
        self.numAdd += 1
        if new_chunk_file_path.endswith(".exr"):
            self.__update_preview_from_exr(new_chunk_file_path)
        else:
            self.__update_preview_from_pil_file(new_chunk_file_path)

    #######################
    def __update_preview_from_pil_file(self, new_chunk_file_path):
        img = Image.open(new_chunk_file_path)

        img_current = self._open_preview()
        img_current = ImageChops.blend(img_current, img, 1.0 / float(self.numAdd))
        img_current.save(self.preview_file_path, "BMP")

    #######################
    def __update_preview_from_exr(self, new_chunk_file):
        if self.preview_exr is None:
            self.preview_exr = load_img(new_chunk_file)
        else:
            self.preview_exr = blend(self.preview_exr, load_img(new_chunk_file), 1.0 / float(self.numAdd))

        img_current = self._open_preview()
        img = self.preview_exr.to_pil()
        img.save(self.preview_file_path, "BMP")

    #######################
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

    #######################
    def _get_lux_console_rel_path(self):
        luxconsole_rel = os.path.relpath(os.path.dirname(self.luxconsole), os.path.dirname(self.main_scene_file))
        luxconsole_rel = os.path.join(luxconsole_rel, os.path.basename(self.luxconsole))
        return luxconsole_rel
