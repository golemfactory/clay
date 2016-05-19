import logging
import random
import os
import math
from collections import OrderedDict

from PIL import Image, ImageChops

from golem.task.taskstate import SubtaskStatus

from gnr.renderingenvironment import BlenderEnvironment
from gnr.renderingdirmanager import get_test_task_path, get_tmp_path, find_task_script
from gnr.renderingtaskstate import RendererDefaults, RendererInfo
from gnr.task.gnrtask import GNROptions, check_subtask_id_wrapper
from gnr.task.framerenderingtask import FrameRenderingTask, FrameRenderingTaskBuilder, get_task_boarder, \
    get_task_num_from_pixels
from gnr.task.renderingtaskcollector import RenderingTaskCollector, exr_to_pil
from gnr.task.scenefileeditor import regenerate_blender_crop_file
from gnr.task.imgrepr import load_img


logger = logging.getLogger(__name__)


class BlenderDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "EXR"
        self.main_program_file = find_task_script("docker_blendertask.py")
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 6
        self.support_redundancy = True


class PreviewUpdater(object):
    def __init__(self, preview_file_path, scene_res_x, scene_res_y, expected_offsets):
        # pairs of (subtask_number, its_image_filepath)
        # careful: chunks' numbers start from 1
        self.chunks = {}
        self.scene_res_x = scene_res_x
        self.scene_res_y = scene_res_y
        self.preview_file_path = preview_file_path
        self.expected_offsets = expected_offsets
        
        # where the match ends - since the chunks have unexpectable sizes, we 
        # don't know where to paste new chunk unless all of the above are in 
        # their correct places
        self.perfect_match_area_y = 0
        self.perfectly_placed_subtasks = 0
        
    def update_preview(self, subtask_path, subtask_number):
        if subtask_number not in self.chunks:
            self.chunks[subtask_number] = subtask_path
        else:
            return
        
        try:
            if subtask_path.upper().endswith(".EXR"):
                img = exr_to_pil(subtask_path)
            else:
                img = Image.open(subtask_path)
            if subtask_number == self.perfectly_placed_subtasks + 1:
                offset = self.perfect_match_area_y
                _, img_y = img.size
                self.perfect_match_area_y += img_y
                self.perfectly_placed_subtasks += 1
            else:
                offset = self.expected_offsets[subtask_number]
            
            if os.path.exists(self.preview_file_path):
                img_current = Image.open(self.preview_file_path)
                img_current.paste(img, (0, offset))
                img_current.save(self.preview_file_path, "BMP")            
            else:
                img_offset = Image.new("RGB", (self.scene_res_x, self.scene_res_y))
                img_offset.paste(img, (0, offset))
                img_offset.save(self.preview_file_path, "BMP")
        except Exception as err:
            logger.error("Can't generate preview {}".format(err))
            return
        
        if subtask_number == self.perfectly_placed_subtasks and (subtask_number + 1) in self.chunks:
            self.update_preview(self.chunks[subtask_number + 1], subtask_number + 1)


def build_blender_renderer_info(dialog, customizer):
    defaults = BlenderDefaults()

    renderer = RendererInfo("Blender", defaults, BlenderRenderTaskBuilder, dialog,
                            customizer, BlenderRendererOptions)
    renderer.output_formats = ["PNG", "TGA", "EXR", "JPEG", "BMP"]
    renderer.scene_file_ext = ["blend"]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_boarder = get_task_boarder

    return renderer


class BlenderRendererOptions(GNROptions):
    def __init__(self):
        self.environment = BlenderEnvironment()
        self.use_frames = False
        self.frames = range(1, 11)


class BlenderRenderTaskBuilder(FrameRenderingTaskBuilder):
    """ Build new Blender tasks using RenderingTaskDefintions and BlenderRendererOptions as taskdefinition
    renderer options
    """
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)
        if self.task_definition.docker_images is None:
            self.task_definition.docker_images = BlenderEnvironment().docker_images

        blender_task = BlenderRenderTask(self.node_name,
                                         self.task_definition.task_id,
                                         main_scene_dir,
                                         self.task_definition.main_scene_file,
                                         self.task_definition.main_program_file,
                                         self._calculate_total(BlenderDefaults(), self.task_definition),
                                         self.task_definition.redundancy,
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
                                         self.task_definition.max_price,
                                         docker_images=self.task_definition.docker_images)
        return self._set_verification_options(blender_task)

    def _set_verification_options(self, new_task):
        new_task = FrameRenderingTaskBuilder._set_verification_options(self, new_task)
        if new_task.advanceVerification:
            box_x = max(new_task.verification_options.box_size[0], 8)
            box_y = max(new_task.verification_options.box_size[1], 8)
            new_task.box_size = (box_x, box_y)
        return new_task


DEFAULT_BLENDER_DOCKER_IMAGE = "golem/blender:latest"


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
                 num_subtasks,
                 redundancy,
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
                 max_price,
                 return_address="",
                 return_port=0,
                 key_id="",
                 docker_images=None):

        FrameRenderingTask.__init__(self, node_name, task_id, return_address, return_port, key_id,
                                    BlenderEnvironment.get_id(), full_task_timeout, subtask_timeout,
                                    main_program_file, task_resources, main_scene_dir, main_scene_file,
                                    num_subtasks, redundancy, res_x, res_y, outfilebasename, output_file,
                                    output_format, root_path, estimated_memory, use_frames, frames, max_price,
                                    docker_images)

        crop_task = find_task_script("blendercrop.py")
        try:
            with open(crop_task) as f:
                self.script_src = f.read()
        except IOError as err:
            logger.error("Wrong script file: {}".format(err))
            self.script_src = ""

        self.frames_given = {}
        for frame in frames:
            self.frames_given[frame] = {}
        
        tmp_dir = get_tmp_path(self.header.node_name, self.header.task_id, self.root_path)
        if not self.use_frames:
            self.preview_file_path = "{}".format(os.path.join(tmp_dir, "current_preview"))
        else:
            self.preview_file_path = []
            for i in range(len(self.frames)):
                self.preview_file_path.append("{}".format(os.path.join(tmp_dir, "current_preview{}".format(i))))
        expected_offsets = {}
        
        for i in range(1, self.total_tasks):
            _, expected_offset = self._get_min_max_y(i)
            expected_offset = self.res_y - int(expected_offset * float(self.res_y))
            expected_offsets[i] = expected_offset
        
        self.preview_updater = PreviewUpdater(self.preview_file_path, self.res_x, self.res_y, expected_offsets)

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):

        if not self._accept_client(node_id):
            logger.warning("Client {} banned from this task ".format(node_name))
            return None

        start_task, end_task = self._get_next_task()

        working_directory = self._get_working_directory()
        scene_file = self._get_scene_file_rel_path()

        if self.use_frames:
            frames, parts = self._choose_frames(start_task)
        else:
            frames = [1]
            parts = 1

        if not self.use_frames:
            min_y, max_y = self._get_min_max_y(start_task)
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
                      "start_part": self.get_part_num(start_task),
                      "end_part": self.get_part_num(end_task),
                      "num_subtasks": self.num_subtasks,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "script_src": script_src,
                      "frames": frames,
                      "output_format": self.output_format
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
            frames = [1]

        script_src = regenerate_blender_crop_file(self.script_src, 8, 8, 0.0, 1.0, 0.0, 1.0)

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 1,
                      "end_task": 1,
                      "start_part": 1,
                      "end_part": 1,
                      "total_tasks": self.total_tasks,
                      "num_subtasks": self.num_subtasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "script_src": script_src,
                      "frames": frames,
                      "output_format": self.output_format
                      }

        hash = "{}".format(random.getrandbits(128))

        self.test_task_res_path = get_test_task_path(self.root_path)
        logger.debug(self.test_task_res_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        return self._new_compute_task_def(hash, extra_data, working_directory, 0)

    def _get_min_max_y(self, start_task):
        part_num = self.get_part_num(start_task)
        if self.res_y % self.num_subtasks == 0:
            min_y = (self.num_subtasks - part_num) * (1.0 / float(self.num_subtasks))
            max_y = (self.num_subtasks - part_num + 1) * (1.0 / float(self.num_subtasks))
        else:
            ceiling_height = int(math.ceil(float(self.res_y) / float(self.num_subtasks)))
            ceiling_subtasks = self.num_subtasks - (ceiling_height * self.num_subtasks - self.res_y)
            if part_num > ceiling_subtasks:
                min_y = float(self.num_subtasks - part_num) * float(ceiling_height - 1) / float(self.res_y)
                max_y = float(self.num_subtasks - part_num + 1) * float(ceiling_height - 1) / float(self.res_y)
            else:
                min_y = float((self.num_subtasks - ceiling_subtasks) * (ceiling_height - 1) + (ceiling_subtasks - part_num) * (ceiling_height)) / float(self.res_y)
                max_y = float((self.num_subtasks - ceiling_subtasks) * (ceiling_height - 1) + (ceiling_subtasks - part_num + 1) * (ceiling_height)) / float(self.res_y)
        return min_y, max_y

    def _get_part_size(self, subtask_id):
        start_task = self.subtasks_given[subtask_id]['start_task']
        part_num = self.get_part_num(start_task)
        if not self.use_frames:
            res_y = self._get_part_size_from_subtask_number(part_num)
        elif len(self.frames) >= self.num_subtasks:
            res_y = self.res_y
        else:
            parts = self.num_subtasks / len(self.frames)
            res_y = int(math.floor(float(self.res_y) / float(parts)))
        return self.res_x, res_y

    def _get_part_size_from_subtask_number(self, subtask_number):
        
        if self.res_y % self.num_subtasks == 0:
            res_y = self.res_y / self.num_subtasks
        else:
            # in this case task will be divided into not equal parts: floor or ceil of (res_y/num_subtasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(float(self.res_y) / float(self.num_subtasks)))
            ceiling_subtasks = self.num_subtasks - (ceiling_height * self.num_subtasks - self.res_y)
            if subtask_number > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    @check_subtask_id_wrapper
    def _get_part_img_size(self, subtask_id, adv_test_file):
        x, y = self._get_part_size(subtask_id)
        return 0, 0, x, y

    @check_subtask_id_wrapper
    def _change_scope(self, subtask_id, start_box, tr_file):
        extra_data, _ = FrameRenderingTask._change_scope(self, subtask_id, start_box, tr_file)
        min_x = start_box[0] / float(self.res_x)
        max_x = (start_box[0] + self.verification_options.box_size[0] + 1) / float(self.res_x)
        part_num = self.get_part_num(extra_data['start_task'])
        start_y = start_box[1] + (part_num - 1) * (self.res_y / float(extra_data['num_subtasks']))
        max_y = float(self.res_y - start_y) / self.res_y
        min_y = max(float(self.res_y - start_y - self.verification_options.box_size[1] - 1) / self.res_y, 0.0)
        script_src = regenerate_blender_crop_file(self.script_src, self.res_x, self.res_y, min_x, max_x, min_y, max_y)
        extra_data['script_src'] = script_src
        extra_data['output_format'] = self.output_format
        return extra_data, (0, 0)

    def __get_frame_num_from_output_file(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.find(self.outfilebasename)
        return int(file_name[idx + len(self.outfilebasename):])

    def _update_preview(self, new_chunk_file_path, chunk_num):
        self.preview_updater.update_preview(new_chunk_file_path, chunk_num)

    def _get_output_name(self, frame_num, num_start):
        num = str(frame_num)
        return "{}{}.{}".format(self.outfilebasename, num.zfill(4), self.output_format)
    
    def _put_image_together(self, tmp_dir):
        output_file_name = u"{}".format(self.output_file, self.output_format)
        self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
        if not self._use_outer_task_collector():
            collector = CustomCollector(paste=True, width=self.res_x, height=self.res_y)
            for file in self.collected_file_names.values():
                collector.add_img_file(file)
            collector.finalize().save(output_file_name, self.output_format)
        else:
            self._put_collected_files_together(os.path.join(tmp_dir, output_file_name),
                                               self.collected_file_names.values(), "paste")


class CustomCollector(RenderingTaskCollector):
    def __init__(self, paste=False, width=1, height=1):
        RenderingTaskCollector.__init__(self, paste, width, height)
        self.current_offset = 0
    
    def _paste_image(self, final_img, new_part, num):
        res_y = self.height
        img_offset = Image.new("RGB", (self.width, self.height))
        offset = self.current_offset
        _, new_img_res_y = new_part.size
        self.current_offset += new_img_res_y
        img_offset.paste(new_part, (0, offset))
        return ImageChops.add(final_img, img_offset)
    
