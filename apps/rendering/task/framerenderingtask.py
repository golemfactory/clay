import os
import logging
import math
import shutil
from collections import OrderedDict
from PIL import Image, ImageChops

from golem.task.taskstate import SubtaskStatus

from apps.core.task.gnrtask import GNRTask
from apps.rendering.resources.renderingtaskcollector import exr_to_pil, RenderingTaskCollector
from apps.rendering.task.renderingtask import RenderingTask, RenderingTaskBuilder

logger = logging.getLogger("apps.rendering")

DEFAULT_PADDING = 4


class FrameRenderingTaskBuilder(RenderingTaskBuilder):
    def _calculate_total(self, defaults, definition):
        if definition.optimize_total:
            if self.task_definition.options.use_frames:
                return len(self.task_definition.options.frames)
            else:
                return defaults.default_subtasks

        if self.task_definition.options.use_frames:
            num_frames = len(self.task_definition.options.frames)
            if definition.total_subtasks > num_frames:
                est = int(math.floor(float(definition.total_subtasks) / float(num_frames))) * num_frames
                if est != definition.total_subtasks:
                    logger.warning("Too many subtasks for this task. {} subtasks will be used".format(est))
                return est

            est = int(
                math.ceil(float(num_frames) / float(math.ceil(float(num_frames) / float(definition.total_subtasks)))))
            if est != definition.total_subtasks:
                logger.warning("Too many subtasks for this task. {} subtasks will be used.".format(est))

            return est

        if defaults.min_subtasks <= definition.total_subtasks <= defaults.max_subtasks:
            return definition.total_subtasks
        else:
            return defaults.default_subtasks


class FrameRenderingTask(RenderingTask):

    ################
    # Task methods #
    ################

    def __init__(self, node_name, task_id, owner_address, owner_port, owner_key_id, environment, timeout,
                 subtask_timeout, main_program_file, task_resources, main_scene_dir, main_scene_file,
                 total_tasks, res_x, res_y, outfilebasename, output_file, output_format, root_path,
                 estimated_memory, use_frames, frames, max_price, docker_images=None):
        RenderingTask.__init__(self, node_name, task_id, owner_address, owner_port, owner_key_id, environment, timeout,
                               subtask_timeout, main_program_file, task_resources, main_scene_dir, main_scene_file,
                               total_tasks, res_x, res_y, outfilebasename, output_file, output_format, root_path,
                               estimated_memory, max_price, docker_images)

        self.use_frames = use_frames
        self.frames = frames

        self.frames_given = {}
        for frame in frames:
            frame_key = unicode(frame)
            self.frames_given[frame_key] = {}

        if use_frames:
            self.preview_file_path = [None] * len(frames)
            self.preview_task_file_path = [None] * len(frames)

    @RenderingTask.handle_key_error
    def computation_finished(self, subtask_id, task_results, result_type=0):
        if not self.should_accept(subtask_id):
            return

        self.interpret_task_results(subtask_id, task_results, result_type)
        tr_files = self.results[subtask_id]

        if len(tr_files) > 0:
            num_start = self.subtasks_given[subtask_id]['start_task']
            parts = self.subtasks_given[subtask_id]['parts']
            num_end = self.subtasks_given[subtask_id]['end_task']
            self.subtasks_given[subtask_id]['status'] = SubtaskStatus.finished
            frames_list = []

            if self.use_frames and self.total_tasks <= len(self.frames):
                frames_list = self.subtasks_given[subtask_id]['frames']
                if len(tr_files) < len(frames_list):
                    self._mark_subtask_failed(subtask_id)
                    if not self.use_frames:
                        self._update_task_preview()
                    else:
                        self._update_frame_task_preview()
                    return

            if not self._verify_imgs(subtask_id, tr_files):
                self._mark_subtask_failed(subtask_id)
                if not self.use_frames:
                    self._update_task_preview()
                else:
                    self._update_frame_task_preview()
                return

            self.counting_nodes[self.subtasks_given[subtask_id]['node_id']].accept()

            for tr_file in tr_files:

                if not self.use_frames:
                    self._collect_image_part(num_start, tr_file)
                elif self.total_tasks <= len(self.frames):
                    frames_list = self._collect_frames(num_start, tr_file, frames_list)
                else:
                    self._collect_frame_part(num_start, tr_file, parts)

            self.num_tasks_received += num_end - num_start + 1

        if self.num_tasks_received == self.total_tasks and not self.use_frames:
            self._put_image_together()

    @GNRTask.handle_key_error
    def computation_failed(self, subtask_id):
        GNRTask.computation_failed(self, subtask_id)
        if self.use_frames:
            self._update_frame_task_preview()
        else:
            self._update_task_preview()

    def get_output_names(self):
        if self.use_frames:
            dir_ = os.path.dirname(self.output_file)
            return [os.path.normpath(os.path.join(dir_, self._get_output_name(frame))) for frame in self.frames]
        else:
            return super(FrameRenderingTask, self).get_output_names()

    #########################
    # Specific task methods #
    #########################

    def _update_frame_preview(self, new_chunk_file_path, frame_num, part=1, final=False):
        num = self.frames.index(frame_num)
        if new_chunk_file_path.upper().endswith(".EXR"):
            img = exr_to_pil(new_chunk_file_path)
        else:
            img = Image.open(new_chunk_file_path)

        if self.preview_file_path[num] is None:
            self.preview_file_path[num] = "{}{}".format(os.path.join(self.tmp_dir, "current_preview"), num)
        if self.preview_task_file_path[num] is None:
            self.preview_task_file_path[num] = "{}{}".format(os.path.join(self.tmp_dir, "current_task_preview"), num)

        if not final:
            img = self._paste_new_chunk(img, self.preview_file_path[num], part, self.total_tasks / len(self.frames))

        if img:
            img_x, img_y = img.size
            img = Image.resize((int(round(self.scale_factor * img_x)), int(round(self.scale_factor * img_y))),
                               resample=Image.BILINEAR)
            img.save(self.preview_file_path[num], "BMP")
            img.save(self.preview_task_file_path[num], "BMP")
            
        img.close()

    def _paste_new_chunk(self, img_chunk, preview_file_path, chunk_num, all_chunks_num):
        try:
            img_offset = Image.new("RGB", (int(round(self.res_x * self.scale_factor)), int(round(self.res_y * self.scale_factor))))
            offset = int(math.floor((chunk_num - 1) * float(self.res_y) * self.scale_factor / float(all_chunks_num)))
            img_offset.paste(img_chunk, (0, offset))
        except Exception as err:
            logger.error("Can't generate preview {}".format(err))
            img_offset = None

        if not os.path.exists(preview_file_path):
            return img_offset

        try:
            img = Image.open(preview_file_path)
            if img_offset:
                img = ImageChops.add(img, img_offset)
            return img
        except Exception as err:
            logger.error("Can't add new chunk to preview{}".format(err))
            return img_offset

    def _update_frame_task_preview(self):
        sent_color = (0, 255, 0)
        failed_color = (255, 0, 0)

        for sub in self.subtasks_given.values():
            if sub['status'] == SubtaskStatus.starting:
                for frame in sub['frames']:
                    self.__mark_sub_frame(sub, frame, sent_color)

            if sub['status'] in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                for frame in sub['frames']:
                    self.__mark_sub_frame(sub, frame, failed_color)

    def _open_frame_preview(self, preview_file_path):

        if not os.path.exists(preview_file_path):
            img = Image.new("RGB", (int(round(self.res_x * self.scale_factor)), 
                                    int(round(self.res_y * self.scale_factor))))
            img.save(preview_file_path, "BMP")

        return Image.open(preview_file_path)

    def _mark_task_area(self, subtask, img_task, color, frame_index=0):
        if not self.use_frames:
            RenderingTask._mark_task_area(self, subtask, img_task, color)
        elif self.__full_frames():
            for i in range(0, int(round(self.res_x * self.scale_factor))):
                for j in range(0, int(round(self.res_y))):
                    img_task.putpixel((i, j), color)
        else:
            parts = self.total_tasks / len(self.frames)
            upper = int(math.ceil(self.res_y / parts * self.scale_factor) * ((subtask['start_task'] - 1) % parts))
            lower = int(math.floor(self.res_y / parts * self.scale_factor) * ((subtask['start_task'] - 1) % parts + 1))
            for i in range(0, self.res_x):
                for j in range(upper, lower):
                    img_task.putpixel((i, j), color)

    @RenderingTask.handle_key_error
    def _get_part_img_size(self, subtask_id, adv_test_file):
        if not self.use_frames or self.__full_frames():
            return RenderingTask._get_part_img_size(self, subtask_id, adv_test_file)
        else:
            start_task = self.subtasks_given[subtask_id]['start_task']
            parts = self.subtasks_given[subtask_id]['parts']
            num_task = self._count_part(start_task, parts)
            img_height = int(math.floor(float(self.res_y) / float(parts)))
            return 1, (num_task - 1) * img_height + 1, self.res_x - 1, num_task * img_height - 1

    def _choose_frames(self, frames, start_task, total_tasks):
        if total_tasks <= len(frames):
            subtasks_frames = int(math.ceil(float(len(frames)) / float(total_tasks)))
            start_frame = (start_task - 1) * subtasks_frames
            end_frame = min(start_task * subtasks_frames, len(frames))
            return frames[start_frame:end_frame], 1
        else:
            parts = total_tasks / len(frames)
            return [frames[(start_task - 1) / parts]], parts

    def _put_image_together(self):
        output_file_name = u"{}".format(self.output_file, self.output_format)
        self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
        if not self._use_outer_task_collector():
            collector = RenderingTaskCollector(paste=True, width=self.res_x, height=self.res_y)
            for file in self.collected_file_names.values():
                collector.add_img_file(file)
            collector.finalize().save(output_file_name, self.output_format)
        else:
            self._put_collected_files_together(os.path.join(self.tmp_dir, output_file_name),
                                               self.collected_file_names.values(), "paste")

    def _put_frame_together(self, frame_num, num_start):
        directory = os.path.dirname(self.output_file)
        output_file_name = os.path.join(directory, self._get_output_name(frame_num))
        frame_key = unicode(frame_num)
        collected = self.frames_given[frame_key]
        collected = OrderedDict(sorted(collected.items()))
        if not self._use_outer_task_collector():
            collector = RenderingTaskCollector(paste=True, width=self.res_x, height=self.res_y)
            for file in collected.values():
                collector.add_img_file(file)
            collector.finalize().save(output_file_name, self.output_format)
        else:
            self._put_collected_files_together(output_file_name, collected.values(), "paste")
        self.collected_file_names[frame_num] = output_file_name
        self._update_frame_preview(output_file_name, frame_num, final=True)
        self._update_frame_task_preview()

    def _copy_frames(self):
        output_dir = os.path.dirname(self.output_file)
        for file in self.collected_file_names.values():
            shutil.copy(file, os.path.join(output_dir, os.path.basename(file)))

    def _collect_image_part(self, num_start, tr_file):
        self.collected_file_names[num_start] = tr_file
        self._update_preview(tr_file, num_start)
        self._update_task_preview()

    def _collect_frames(self, num_start, tr_file, frames_list):
        frame_key = unicode(frames_list[0])
        self.frames_given[frame_key][0] = tr_file
        self._put_frame_together(frames_list[0], num_start)
        return frames_list[1:]

    def _collect_frame_part(self, num_start, tr_file, parts):

        frame_num = self.frames[(num_start - 1) / parts]
        frame_key = unicode(frame_num)
        part = self._count_part(num_start, parts)
        self.frames_given[frame_key][part] = tr_file

        self._update_frame_preview(tr_file, frame_num, part)

        if len(self.frames_given[frame_key]) == parts:
            self._put_frame_together(frame_num, num_start)

    def _count_part(self, start_num, parts):
        return ((start_num - 1) % parts) + 1

    def __full_frames(self):
        return self.total_tasks <= len(self.frames)

    def __mark_sub_frame(self, sub, frame, color):
        idx = self.frames.index(frame)
        preview_task_file_path = "{}{}".format(os.path.join(self.tmp_dir, "current_task_preview"), idx)
        preview_file_path = "{}{}".format(os.path.join(self.tmp_dir, "current_preview"), idx)
        img_task = self._open_frame_preview(preview_task_file_path)
        self._mark_task_area(sub, img_task, color, idx)
        img_task.save(preview_task_file_path, "BMP")
        self.preview_task_file_path[idx] = preview_task_file_path

    def _get_output_name(self, frame_num):
        return get_frame_name(self.outfilebasename, self.output_format, frame_num)

    def _update_preview_task_file_path(self, preview_task_file_path):
        if not self.use_frames:
            RenderingTask._update_preview_task_file_path(self, preview_task_file_path)


def get_frame_name(output_name, ext, frame_num):
    idr = output_name.rfind("#")
    idl = idr
    while idl > 0 and output_name[idl] == "#":
        idl -= 1
    if idr > 0:
        return u"{}.{}".format(output_name[:idl+1] + str(frame_num).zfill(idr-idl) + output_name[idr+1:], ext)
    else:
        return u"{}{}.{}".format(output_name, str(frame_num).zfill(DEFAULT_PADDING), ext)


def get_task_border(start_task, end_task, total_tasks, res_x=300, res_y=200, use_frames=False, frames=100,
                    frame_num=1):
    if not use_frames:
        border = __get_border(start_task, end_task, total_tasks, res_x, res_y)
    elif total_tasks > frames:
        parts = total_tasks / frames
        border = __get_border((start_task - 1) % parts + 1, (end_task - 1) % parts + 1, parts, res_x, res_y)
    else:
        border = []

    return border


def get_task_num_from_pixels(p_x, p_y, definition, total_subtasks, output_num=1):
    res_y = definition.resolution[1]
    if not definition.options.use_frames:
        num = __num_from_pixel(p_y, res_y, total_subtasks)
    else:
        frames = len(definition.options.frames)
        if total_subtasks <= frames:
            subtask_frames = int(math.ceil(float(frames) / float(total_subtasks)))
            num = int(math.ceil(float(output_num) / subtask_frames))
        else:
            parts = total_subtasks / frames
            num = (output_num - 1) * parts + __num_from_pixel(p_y, res_y, parts)
    return num


def __get_border(start_task, end_task, parts, res_x, res_y):
    preview_x = 300
    preview_y = 200
    if res_x != 0 and res_y != 0:
        if float(res_x) / float(res_y) > float(preview_x) / float(preview_y):
            scale_factor = float(preview_x) / float(res_x)
        else:
            scale_factor = float(preview_y) / float(res_y)
        scale_factor = min(1.0, scale_factor)
    else:
        scale_factor = 1.0
    border = []
    upper = int(math.floor(float(res_y) * scale_factor / float(parts) * (start_task - 1)))
    lower = int(math.floor(float(res_y) * scale_factor / float(parts) * end_task))
    for i in range(upper, lower):
        border.append((0, i))
        border.append((res_x - 1, i))
    for i in range(0, res_x):
        border.append((i, upper))
        border.append((i, lower))
    return border


def __num_from_pixel(p_y, res_y, tasks):
    num = int(math.ceil(float(tasks) * float(p_y) / float(res_y)))
    num = max(num, 1)
    num = min(num, tasks)
    return num
