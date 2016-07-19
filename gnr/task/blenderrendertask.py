import logging
import random
import os
import math
from collections import OrderedDict

from PIL import Image, ImageChops

from golem.task.taskstate import SubtaskStatus

from gnr.renderingenvironment import BlenderEnvironment
from gnr.renderingdirmanager import get_test_task_path, find_task_script
from gnr.renderingtaskstate import RendererDefaults, RendererInfo

from gnr.task.gnrtask import GNROptions
from gnr.task.renderingtask import RenderingTask, AcceptClientVerdict

from gnr.task.framerenderingtask import FrameRenderingTask, FrameRenderingTaskBuilder, get_task_boarder, \
    get_task_num_from_pixels
from gnr.task.renderingtaskcollector import RenderingTaskCollector, exr_to_pil
from gnr.task.scenefileeditor import regenerate_blender_crop_file


logger = logging.getLogger("gnr.task")


class BlenderDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "EXR"
        self.main_program_file = find_task_script("docker_blendertask.py")
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 6


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
        
    def get_offset(self, subtask_number):
        if subtask_number == self.perfectly_placed_subtasks + 1:
            return self.perfect_match_area_y
        return self.expected_offsets[subtask_number]
        
    def update_preview(self, subtask_path, subtask_number):
        if subtask_number not in self.chunks:
            self.chunks[subtask_number] = subtask_path
        
        try:
            if subtask_path.upper().endswith(".EXR"):
                img = exr_to_pil(subtask_path)
            else:
                img = Image.open(subtask_path)
                
            offset = self.get_offset(subtask_number)
            if subtask_number == self.perfectly_placed_subtasks + 1:
                _, img_y = img.size
                self.perfect_match_area_y += img_y
                self.perfectly_placed_subtasks += 1

            if os.path.exists(self.preview_file_path):
                img_current = Image.open(self.preview_file_path)
                img_current.paste(img, (0, offset))
                img_current.save(self.preview_file_path, "BMP")
                img_current.close()
            else:
                img_offset = Image.new("RGB", (self.scene_res_x, self.scene_res_y))
                img_offset.paste(img, (0, offset))
                img_offset.save(self.preview_file_path, "BMP")
                img_offset.close()
            img.close()

        except Exception as err:
            import traceback
            # Print the stack traceback
            traceback.print_exc()
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
        self.compositing = False


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
                                         self.task_definition.renderer_options.compositing,
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
                 compositing,
                 max_price,
                 return_address="",
                 return_port=0,
                 key_id="",
                 docker_images=None):

        FrameRenderingTask.__init__(self, node_name, task_id, return_address, return_port, key_id,
                                    BlenderEnvironment.get_id(), full_task_timeout, subtask_timeout,
                                    main_program_file, task_resources, main_scene_dir, main_scene_file,
                                    total_tasks, res_x, res_y, outfilebasename, output_file, output_format,
                                    root_path, estimated_memory, use_frames, frames, max_price, docker_images)

        crop_task = find_task_script("blendercrop.py")
        try:
            with open(crop_task) as f:
                self.script_src = f.read()
        except IOError as err:
            logger.error("Wrong script file: {}".format(err))
            self.script_src = ""

        self.compositing = compositing
        self.frames_given = {}
        for frame in frames:
            self.frames_given[frame] = {}

        tmp_dir = self._get_tmp_dir()
        if not self.use_frames:
            self.preview_file_path = "{}".format(os.path.join(tmp_dir, "current_preview"))
        else:
            self.preview_file_path = []
            for i in range(len(self.frames)):
                self.preview_file_path.append("{}".format(os.path.join(tmp_dir, "current_preview{}".format(i))))
        
        if self.use_frames:
            parts = self.total_tasks / len(self.frames)
        else:
            parts = self.total_tasks
        expected_offsets = {}
        for i in range(1, parts + 1):
            _, expected_offset = self._get_min_max_y(i)
            expected_offset =  self.res_y - int(expected_offset * float(self.res_y))
            expected_offsets[i] = expected_offset
        
        if self.use_frames:
            self.preview_updaters = []
            for i in range(0, len(self.frames)):
                preview_path = self.preview_file_path[i]
                self.preview_updaters.append(PreviewUpdater(preview_path, self.res_x, self.res_y, expected_offsets))
        else:
            self.preview_updater = PreviewUpdater(self.preview_file_path, self.res_x, self.res_y, expected_offsets)

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):

        verdict = self._accept_client(node_id)
        if verdict != AcceptClientVerdict.ACCEPTED:

            should_wait = verdict == AcceptClientVerdict.SHOULD_WAIT
            if should_wait:
                logger.warning("Waiting for client's {} task results".format(node_name))
            else:
                logger.warning("Client {} banned from this task".format(node_name))

            return self.ExtraData(should_wait=should_wait)

        start_task, end_task = self._get_next_task()
        working_directory = self._get_working_directory()
        scene_file = self._get_scene_file_rel_path()

        if self.use_frames:
            frames, parts = self._choose_frames(self.frames, start_task, self.total_tasks)
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

        script_src = regenerate_blender_crop_file(self.script_src, self.res_x, self.res_y, 0.0, 1.0, min_y, max_y,
                                                  self.compositing)
        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
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

        ctd = self._new_compute_task_def(hash, extra_data, working_directory, perf_index)
        return self.ExtraData(ctd=ctd)

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

        script_src = regenerate_blender_crop_file(self.script_src, 8, 8, 0.0, 1.0, 0.0, 1.0, self.compositing)

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 1,
                      "end_task": 1,
                      "total_tasks": self.total_tasks,
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
        if self.use_frames:
            parts = self.total_tasks / len(self.frames)
        else:
            parts = self.total_tasks
        if self.res_y % parts == 0:
            min_y = (parts - start_task) * (1.0 / float(parts))
            max_y = (parts - start_task + 1) * (1.0 / float(parts))
        else:
            ceiling_height = int(math.ceil(float(self.res_y) / float(parts)))
            ceiling_subtasks = parts - (ceiling_height * parts - self.res_y)
            if start_task > ceiling_subtasks:
                min_y = float(parts - start_task) * float(ceiling_height - 1) / float(self.res_y)
                max_y = float(parts - start_task + 1) * float(ceiling_height - 1) / float(self.res_y)
            else:
                min_y = (parts - ceiling_subtasks) * (ceiling_height - 1)
                min_y += (ceiling_subtasks - start_task) * ceiling_height
                min_y = float(min_y) / float(self.res_y)

                max_y = (parts - ceiling_subtasks) * (ceiling_height - 1)
                max_y += (ceiling_subtasks - start_task + 1) * ceiling_height
                max_y = float(max_y) / float(self.res_y)
        return min_y, max_y

    def _get_part_size(self, subtask_id):
        start_task = self.subtasks_given[subtask_id]['start_task']
        if not self.use_frames:
            res_y = self._get_part_size_from_subtask_number(start_task)
        elif len(self.frames) >= self.total_tasks:
            res_y = self.res_y
        else:
            parts = self.total_tasks / len(self.frames)
            res_y = int(math.floor(float(self.res_y) / float(parts)))
        return self.res_x, res_y

    def _get_part_size_from_subtask_number(self, subtask_number):
        
        if self.res_y % self.total_tasks == 0:
            res_y = self.res_y / self.total_tasks
        else:
            # in this case task will be divided into not equal parts: floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(float(self.res_y) / float(self.total_tasks)))
            ceiling_subtasks = self.total_tasks - (ceiling_height * self.total_tasks - self.res_y)
            if subtask_number > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    @FrameRenderingTask.handle_key_error
    def _get_part_img_size(self, subtask_id, adv_test_file):
        x, y = self._get_part_size(subtask_id)
        return 0, 0, x, y

    @FrameRenderingTask.handle_key_error
    def _change_scope(self, subtask_id, start_box, tr_file):
        extra_data, _ = FrameRenderingTask._change_scope(self, subtask_id, start_box, tr_file)
        min_x = start_box[0] / float(self.res_x)
        max_x = (start_box[0] + self.verification_options.box_size[0] + 1) / float(self.res_x)
        start_y = start_box[1] + (extra_data['start_task'] - 1) * (self.res_y / float(extra_data['total_tasks']))
        max_y = float(self.res_y - start_y) / self.res_y
        min_y = max(float(self.res_y - start_y - self.verification_options.box_size[1] - 1) / self.res_y, 0.0)
        script_src = regenerate_blender_crop_file(self.script_src, self.res_x, self.res_y, min_x, max_x, min_y, max_y,
                                                  self.compositing)
        extra_data['script_src'] = script_src
        extra_data['output_format'] = self.output_format
        return extra_data, (0, 0)

    def __get_frame_num_from_output_file(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.split('_')[-2]
        return int(idx)

    def _update_preview(self, new_chunk_file_path, chunk_num):
        self.preview_updater.update_preview(new_chunk_file_path, chunk_num)

    def _update_frame_preview(self, new_chunk_file_path, frame_num, part=1, final=False):
        if final:
            if new_chunk_file_path.upper().endswith(".EXR"):
                img = exr_to_pil(new_chunk_file_path)
            else:   
                img = Image.open(new_chunk_file_path)
            img.save(self.preview_file_path[self.frames.index(frame_num)], "BMP")
            img.save(self.preview_task_file_path[self.frames.index(frame_num)], "BMP")
            img.close()
        else:
            self.preview_updaters[self.frames.index(frame_num)].update_preview(new_chunk_file_path, part)

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
                       
    def _mark_task_area(self, subtask, img_task, color, frame_index=0):
        if not self.use_frames:
            RenderingTask._mark_task_area(self, subtask, img_task, color)
        elif self.total_tasks <= len(self.frames):
            for i in range(0, self.res_x):
                for j in range(0, self.res_y):
                    img_task.putpixel((i, j), color)
        else:
            parts = self.total_tasks / len(self.frames)
            pu = self.preview_updaters[frame_index]
            part = (subtask['start_task'] - 1) % parts + 1
            lower = pu.get_offset(part)
            if part == parts:
                upper = self.res_y
            else:
                upper = pu.get_offset(part + 1)
            for i in range(0, self.res_x):
                for j in range(lower, upper):
                    img_task.putpixel((i, j), color)
                    
    def _put_frame_together(self, frame_num, num_start):
        directory = os.path.dirname(self.output_file)
        output_file_name = os.path.join(directory, self._get_output_name(frame_num, num_start))
        collected = self.frames_given[frame_num]
        collected = OrderedDict(sorted(collected.items()))
        if not self._use_outer_task_collector():
            collector = CustomCollector(paste=True, width=self.res_x, height=self.res_y)
            for file in collected.values():
                collector.add_img_file(file)
            collector.finalize().save(output_file_name, self.output_format)
        else:
            self._put_collected_files_together(output_file_name, collected.values(), "paste")
        self.collected_file_names[frame_num] = output_file_name
        self._update_frame_preview(output_file_name, frame_num, final=True)
        self._update_frame_task_preview()


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
    
