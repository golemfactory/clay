import logging
import random
import os
import math
from collections import OrderedDict
from PIL import Image, ImageChops
from golem.task.taskstate import SubtaskStatus
from gnr.renderingdirmanager import get_test_task_path, get_tmp_path
from gnr.renderingenvironment import BlenderEnvironment
from gnr.renderingtaskstate import RendererDefaults, RendererInfo
from gnr.task.gnrtask import GNROptions, check_subtask_id_wrapper
from gnr.task.framerenderingtask import FrameRenderingTask, FrameRenderingTaskBuilder, get_task_boarder, \
    get_task_num_from_pixels
from gnr.task.renderingtaskcollector import RenderingTaskCollector, exr_to_pil
from gnr.task.scenefileeditor import regenerate_blender_crop_file


logger = logging.getLogger(__name__)


class BlenderDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "EXR"
        self.main_program_file = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                                               '../tasks/blendertask.py')))
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 6


def build_blender_renderer_info(dialog, customizer):
    defaults = BlenderDefaults()

    renderer = RendererInfo("Blender", defaults, BlenderRenderTaskBuilder, dialog,
                            customizer, BlenderRendererOptions)
    renderer.output_formats = ["PNG", "TGA", "EXR"]
    renderer.scene_file_ext = ["blend"]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_boarder = get_task_boarder

    return renderer


class BlenderRendererOptions(GNROptions):
    def __init__(self):
        self.environment = BlenderEnvironment()
        self.engine_values = ["BLENDER_RENDER", "BLENDER_GAME", "CYCLES"]
        self.engine = "BLENDER_RENDER"
        self.use_frames = False
        self.frames = range(1, 11)


class BlenderRenderTaskBuilder(FrameRenderingTaskBuilder):
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)

        vray_task = BlenderRenderTask(self.node_name,
                                      self.task_definition.task_id,
                                      main_scene_dir,
                                      self.task_definition.main_scene_file,
                                      self.task_definition.main_program_file,
                                      self._calculate_total(BlenderDefaults(), self.task_definition),
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
                                      self.task_definition.renderer_options.use_frames,
                                      self.task_definition.renderer_options.frames,
                                      self.task_definition.renderer_options.engine
                                      )
        return self._set_verification_options(vray_task)

    def _set_verification_options(self, new_task):
        new_task = FrameRenderingTaskBuilder._set_verification_options(self, new_task)
        if new_task.advanceVerification:
            box_x = max(new_task.verification_options.box_size[0], 8)
            box_y = max(new_task.verification_options.box_size[1], 8)
            new_task.box_size = (box_x, box_y)
        return new_task


class BlenderRenderTask(FrameRenderingTask):

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
                 use_frames,
                 frames,
                 engine,
                 return_address="",
                 return_port=0,
                 key_id=""):

        FrameRenderingTask.__init__(self, node_name, task_id, return_address, return_port, key_id,
                                    BlenderEnvironment.get_id(), full_task_timeout, subtask_timeout,
                                    main_program_file, task_resources, main_scene_dir, main_scene_file,
                                    total_tasks, res_x, res_y, outfilebasename, output_file, output_format,
                                    root_path, estimated_memory, use_frames, frames)

        crop_task = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/tasks/blendercrop.py'))
        try:
            with open(crop_task) as f:
                self.script_src = f.read()
        except Exception, err:
            logger.error("Wrong script file: {}".format(str(err)))
            self.script_src = ""

        self.engine = engine

        self.frames_given = {}
        for frame in frames:
            self.frames_given[frame] = {}

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):

        if not self._accept_client(node_id):
            logger.warning("Client {} banned from this task ".format(node_name))
            return None

        start_task, end_task = self._get_next_task()

        working_directory = self._get_working_directory()
        scene_file = self._get_scene_file_rel_path()

        if self.use_frames:
            frames, parts = self._choose_frames(self.frames, start_task, self.total_tasks)
        else:
            frames = [1]
            parts = 1

        if not self.use_frames:
            min_y = (self.total_tasks - start_task) * (1.0 / float(self.total_tasks))
            max_y = (self.total_tasks - start_task + 1) * (1.0 / float(self.total_tasks))
        elif parts > 1:
            min_y = (parts - self._count_part(start_task, parts)) * (1.0 / float(parts))
            max_y = (parts - self._count_part(start_task, parts) + 1) * (1.0 / float(parts))
        else:
            min_y = 0.0
            max_y = 1.0

        script_src = regenerate_blender_crop_file(self.script_src, self.res_x, self.res_y, 0.0, 1.0, min_y, max_y)
        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "script_src": script_src,
                      "engine": self.engine,
                      "frames": frames,
                      }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[hash] = extra_data
        self.subtasks_given[hash]['status'] = SubtaskStatus.starting
        self.subtasks_given[hash]['perf'] = perf_index
        self.subtasks_given[hash]['node_id'] = node_id
        self.subtasks_given[hash]['parts'] = parts

        if not self.use_frames:
            self._update_task_preview()
        else:
            self._update_frame_task_preview()

        return self._new_compute_task_def(hash, extra_data, working_directory, perf_index)

    ###################
    # GNRTask methods #
    ###################

    def query_extra_data_for_test_task(self):

        working_directory = self._get_working_directory()
        scene_file = self._get_scene_file_rel_path()

        if self.use_frames:
            frames = [self.frames[0]]
        else:
            frames = []

        if self.use_frames:
            frames = [self.frames[0]]
        else:
            frames = [1]

        script_src = regenerate_blender_crop_file(self.script_src, 8, 8, 0.0, 1.0, 0.0, 1.0)

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 1,
                      "end_task": 1,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "script_src": script_src,
                      "engine": self.engine,
                      "frames": frames
                      }

        hash = "{}".format(random.getrandbits(128))

        self.test_task_res_path = get_test_task_path(self.root_path)
        logger.debug(self.test_task_res_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        return self._new_compute_task_def(hash, extra_data, working_directory, 0)

    def _get_part_size(self):
        if not self.use_frames:
            res_y = int(math.floor(float(self.res_y) / float(self.total_tasks)))
        elif len(self.frames) >= self.total_tasks:
            res_y = self.res_y
        else:
            parts = self.total_tasks / len(self.frames)
            res_y = int(math.floor(float(self.res_y) / float(parts)))
        return self.res_x, res_y

    @check_subtask_id_wrapper
    def _get_part_img_size(self, subtask_id, adv_test_file):
        x, y = self._get_part_size()
        return 0, 0, x, y

    @check_subtask_id_wrapper
    def _change_scope(self, subtask_id, start_box, tr_file):
        extra_data, _ = FrameRenderingTask._change_scope(self, subtask_id, start_box, tr_file)
        min_x = start_box[0] / float(self.res_x)
        max_x = (start_box[0] + self.verification_options.box_size[0] + 1) / float(self.res_x)
        start_y = start_box[1] + (extra_data['start_task'] - 1) * (self.res_y / float(extra_data['total_tasks']))
        max_y = float(self.res_y - start_y) / self.res_y
        min_y = max(float(self.res_y - start_y - self.verification_options.box_size[1] - 1) / self.res_y, 0.0)
        script_src = regenerate_blender_crop_file(self.script_src, self.res_x, self.res_y, min_x, max_x, min_y, max_y)
        extra_data['script_src'] = script_src
        return extra_data, (0, 0)

    def __get_frame_num_from_output_file(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.find(self.outfilebasename)
        return int(file_name[idx + len(self.outfilebasename):])

    def _update_preview(self, new_chunk_file_path, chunk_num):

        if new_chunk_file_path.endswith(".exr"):
            img = exr_to_pil(new_chunk_file_path)
        else:
            img = Image.open(new_chunk_file_path)

        img_offset = Image.new("RGB", (self.res_x, self.res_y))
        try:
            offset = int(math.floor((chunk_num - 1) * float(self.res_y) / float(self.total_tasks)))
            img_offset.paste(img, (0, offset))
        except Exception, err:
            logger.error("Can't generate preview {}".format(str(err)))

        tmp_dir = get_tmp_path(self.header.node_name, self.header.task_id, self.root_path)

        self.preview_file_path = "{}".format(os.path.join(tmp_dir, "current_preview"))

        if os.path.exists(self.preview_file_path):
            img_current = Image.open(self.preview_file_path)
            img_current = ImageChops.add(img_current, img_offset)
            img_current.save(self.preview_file_path, "BMP")
        else:
            img_offset.save(self.preview_file_path, "BMP")

    def _get_output_name(self, frame_num, num_start):
        num = str(frame_num)
        return "{}{}.{}".format(self.outfilebasename, num.zfill(4), self.output_format)
