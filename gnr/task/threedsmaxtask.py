import logging
import random
import os
import math
from PIL import Image, ImageChops
from golem.task.taskstate import SubtaskStatus
from gnr.task.gnrtask import GNROptions, check_subtask_id_wrapper
from gnr.task.renderingtaskcollector import exr_to_pil
from gnr.task.framerenderingtask import FrameRenderingTask, FrameRenderingTaskBuilder, get_task_boarder, \
    get_task_num_from_pixels
from gnr.renderingdirmanager import get_test_task_path, get_tmp_path
from gnr.renderingtaskstate import RendererDefaults, RendererInfo
from gnr.renderingenvironment import ThreeDSMaxEnvironment
from gnr.ui.threedsmaxdialog import ThreeDSMaxDialog
from gnr.customizers.threedsmaxdialogcustomizer import ThreeDSMaxDialogCustomizer

logger = logging.getLogger(__name__)


class ThreeDSMaxDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "EXR"
        self.main_program_file = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                                               '../tasks/3dsmaxtask.py')))
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 6


def build_3ds_max_renderer_info(dialog, customizer):
    defaults = ThreeDSMaxDefaults()

    renderer = RendererInfo("3ds Max Renderer", defaults, ThreeDSMaxTaskBuilder, dialog, customizer,
                            ThreeDSMaxRendererOptions)
    renderer.output_formats = ["BMP", "EXR", "GIF", "IM", "JPEG", "PCD", "PCX", "PNG", "PPM", "PSD", "TIFF", "XBM",
                               "XPM"]
    renderer.scene_file_ext = ["max", "zip"]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_boarder = get_task_boarder

    return renderer


class ThreeDSMaxRendererOptions(GNROptions):
    def __init__(self):
        self.environment = ThreeDSMaxEnvironment()
        self.preset = self.environment.get_default_preset()
        self.cmd = self.environment.get_3ds_max_cmd_path()
        self.use_frames = False
        self.frames = range(1, 11)

    def add_to_resources(self, resources):
        if os.path.isfile(self.preset):
            resources.add(os.path.normpath(self.preset))
        return resources

    def remove_from_resources(self, resources):
        if os.path.normpath(self.preset) in resources:
            resources.remove(os.path.normpath(self.preset))
        return resources


class ThreeDSMaxTaskBuilder(FrameRenderingTaskBuilder):
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)

        three_ds_max_task = ThreeDSMaxTask(self.node_name,
                                           self.task_definition.task_id,
                                           main_scene_dir,
                                           self.task_definition.main_scene_file,
                                           self.task_definition.main_program_file,
                                           self._calculate_total(ThreeDSMaxDefaults(), self.task_definition),
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
                                           self.task_definition.renderer_options.preset,
                                           self.task_definition.renderer_options.cmd,
                                           self.task_definition.renderer_options.use_frames,
                                           self.task_definition.renderer_options.frames
                                           )

        return self._set_verification_options(three_ds_max_task)


class ThreeDSMaxTask(FrameRenderingTask):

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
                 preset_file,
                 cmd_file,
                 use_frames,
                 frames,
                 return_address="",
                 return_port=0,
                 ):

        FrameRenderingTask.__init__(self, node_name, task_id, return_address, return_port,
                                    ThreeDSMaxEnvironment.get_id(), full_task_timeout, subtask_timeout,
                                    main_program_file, task_resources, main_scene_dir, main_scene_file,
                                    total_tasks, res_x, res_y, outfilebasename, output_file, output_format,
                                    root_path, estimated_memory, use_frames, frames)

        self.preset_file = preset_file
        self.cmd = cmd_file
        self.frames_given = {}

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):

        if not self._accept_client(node_id):
            logger.warning(" Client {} banned from this task ".format(node_name))
            return None

        start_task, end_task = self._get_next_task()

        working_directory = self._get_working_directory()
        preset_file = self.__get_preset_file_rel_path()
        scene_file = self._get_scene_file_rel_path()
        cmd_file = os.path.basename(self.cmd)

        if self.use_frames:
            frames, parts = self._choose_frames(self.frames, start_task, self.total_tasks)
        else:
            frames = []
            parts = 1

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "width": self.res_x,
                      "height": self.res_y,
                      "preset_file": preset_file,
                      "cmd_file": cmd_file,
                      "num_cores": num_cores,
                      "use_frames": self.use_frames,
                      "frames": frames,
                      "parts": parts,
                      "overlap": 0
                      }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[hash] = extra_data
        self.subtasks_given[hash]['status'] = SubtaskStatus.starting
        self.subtasks_given[hash]['perf'] = perf_index
        self.subtasks_given[hash]['node_id'] = node_id

        for frame in frames:
            self.frames_given[frame] = {}

        if not self.use_frames:
            self._update_task_preview()
        else:
            self._update_frame_task_preview()

        return self._new_compute_task_def(hash, extra_data, working_directory, perf_index)

    @check_subtask_id_wrapper
    def get_price_mod(self, subtask_id):
        perf = (self.subtasks_given[subtask_id]['end_task'] - self.subtasks_given[subtask_id]['start_task']) + 1
        perf *= float(self.subtasks_given[subtask_id]['perf']) / 1000
        perf *= 50
        return perf

    @check_subtask_id_wrapper
    def restart_subtask(self, subtask_id):
        FrameRenderingTask.restart_subtask(self, subtask_id)
        if not self.use_frames:
            self._update_task_preview()
        else:
            self._update_frame_task_preview()

    ###################
    # GNRTask methods #
    ###################

    def query_extra_data_for_test_task(self):

        working_directory = self._get_working_directory()
        preset_file = self.__get_preset_file_rel_path()
        scene_file = self._get_scene_file_rel_path()
        cmd_file = os.path.basename(self.cmd)

        if self.use_frames:
            frames = [self.frames[0]]
        else:
            frames = []

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 1,
                      "end_task": 1,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "width": 1,
                      "height": self.total_tasks,
                      "preset_file": preset_file,
                      "cmd_file": cmd_file,
                      "num_cores": 0,
                      "use_frames": self.use_frames,
                      "frames": frames,
                      "parts": 1,
                      "overlap": 0
                      }

        hash = "{}".format(random.getrandbits(128))

        self.test_task_res_path = get_test_task_path(self.root_path)
        logger.debug(self.test_task_res_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        return self._new_compute_task_def(hash, extra_data, working_directory, 0)

    def _update_preview(self, new_chunk_file_path, chunk_num):

        try:
            if new_chunk_file_path.endswith(".exr"):
                img = exr_to_pil(new_chunk_file_path)
            else:
                img = Image.open(new_chunk_file_path)
            img_offset = Image.new("RGB", (self.res_x, self.res_y))
            offset = int(math.floor((chunk_num - 1) * float(self.res_y) / float(self.total_tasks)))
            img_offset.paste(img, (0, offset))
        except Exception as err:
            logger.error("Can't generate preview {}".format(err))
            return

        tmp_dir = get_tmp_path(self.header.node_name, self.header.task_id, self.root_path)

        self.preview_file_path = "{}".format(os.path.join(tmp_dir, "current_preview"))

        if os.path.exists(self.preview_file_path):
            img_current = Image.open(self.preview_file_path)
            img_current = ImageChops.add(img_current, img_offset)
            img_current.save(self.preview_file_path, "BMP")
        else:
            img_offset.save(self.preview_file_path, "BMP")

    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        msg = []
        msg.append("scene file: {} ".format(l["scene_file"]))
        msg.append("preset: {} ".format(l["preset_file"]))
        msg.append("total tasks: {}".format(l["total_tasks"]))
        msg.append("start task: {}".format(l["start_task"]))
        msg.append("end task: {}".format(l["end_task"]))
        msg.append("outfile basename: {}".format(l["outfilebasename"]))
        msg.append("size: {}x{}".format(l["width"], l["height"]))
        if l["use_frames"]:
            msg.append("frames: {}".format(l["frames"]))
        return "\n".join(msg)

    def _get_output_name(self, frame_num, num_start):
        num = str(frame_num)
        return "{}{}.{}".format(self.outfilebasename, num.zfill(4), self.output_format)

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
        if not self.use_frames:
            start_y = start_box[1] + (extra_data['start_task'] - 1) * self.res_y / extra_data['total_tasks']
        elif self.total_tasks <= len(self.frames):
            start_y = start_box[1]
            extra_data['frames'] = [self.__get_frame_num_from_output_file(tr_file)]
            extra_data['parts'] = extra_data['total_tasks']
        else:
            part = ((extra_data['start_task'] - 1) % extra_data['parts']) + 1
            start_y = start_box[1] + (part - 1) * self.res_y / extra_data['parts']
        extra_data['total_tasks'] = self.res_y / self.verification_options.box_size[1]
        extra_data['parts'] = extra_data['total_tasks']
        extra_data['start_task'] = start_y / self.verification_options.box_size[1] + 1
        extra_data['end_task'] = (start_y + self.verification_options.box_size[1]) / self.verification_options.box_size[
            1] + 1
        extra_data['overlap'] = extra_data['end_task'] - extra_data['start_task']
        extra_data['overlap'] *= self.verification_options.box_size[1]
        if extra_data['start_task'] != 1:
            new_start_y = extra_data['overlap']
        else:
            new_start_y = 0
        new_start_y += start_y % self.verification_options.box_size[1]
        return extra_data, (start_box[0], new_start_y)

    def __get_preset_file_rel_path(self):
        preset_file = os.path.relpath(os.path.dirname(self.preset_file), os.path.dirname(self.main_program_file))
        preset_file = os.path.join(preset_file, os.path.basename(self.preset_file))
        return preset_file

    def __get_frame_num_from_output_file(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.find(self.outfilebasename)
        return int(file_name[idx + len(self.outfilebasename):])
