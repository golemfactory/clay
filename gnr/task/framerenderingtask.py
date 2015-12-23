import os
import logging
import math
import shutil
from collections import OrderedDict
from PIL import Image, ImageChops
from gnr.task.gnrtask import check_subtask_id_wrapper
from gnr.task.renderingtask import RenderingTask, RenderingTaskBuilder
from gnr.task.renderingtaskcollector import exr_to_pil, RenderingTaskCollector
from gnr.renderingdirmanager import get_tmp_path
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger(__name__)


class FrameRenderingTaskBuilder(RenderingTaskBuilder):
    def _calculate_total(self, defaults, definition):
        if definition.optimize_total:
            if self.task_definition.renderer_options.use_frames:
                return len(self.task_definition.renderer_options.frames)
            else:
                return defaults.default_subtasks

        if self.task_definition.renderer_options.use_frames:
            num_frames = len(self.task_definition.renderer_options.frames)
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

    def __init__(self, node_name, task_id, owner_address, owner_port, owner_key_id, environment, ttl,
                 subtask_ttl, main_program_file, task_resources, main_scene_dir, main_scene_file,
                 total_tasks, res_x, res_y, outfilebasename, output_file, output_format, root_path,
                 estimated_memory, use_frames, frames):
        RenderingTask.__init__(self, node_name, task_id, owner_address, owner_port, owner_key_id, environment, ttl,
                               subtask_ttl, main_program_file, task_resources, main_scene_dir, main_scene_file,
                               total_tasks, res_x, res_y, outfilebasename, output_file, output_format, root_path,
                               estimated_memory)

        self.use_frames = use_frames
        self.frames = frames

        if use_frames:
            self.preview_file_path = [None] * len(frames)
            self.preview_task_file_path = [None] * len(frames)

    def restart(self):
        RenderingTask.restart(self)
        if self.use_frames:
            self.preview_file_path = [None] * len(self.frames)
            self.preview_task_file_path = [None] * len(self.frames)

    @check_subtask_id_wrapper
    def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):

        if not self.should_accept(subtask_id):
            return

        tmp_dir = dir_manager.get_task_temporary_dir(self.header.task_id, create=False)
        self.tmp_dir = tmp_dir

        if len(task_result) > 0:
            num_start = self.subtasks_given[subtask_id]['start_task']
            parts = self.subtasks_given[subtask_id]['parts']
            num_end = self.subtasks_given[subtask_id]['end_task']
            self.subtasks_given[subtask_id]['status'] = SubtaskStatus.finished
            frames_list = []

            if self.use_frames and self.total_tasks <= len(self.frames):
                frames_list = self.subtasks_given[subtask_id]['frames']
                if len(task_result) < len(frames_list):
                    self._mark_subtask_failed(subtask_id)
                    if not self.use_frames:
                        self._update_task_preview()
                    else:
                        self._update_frame_task_preview()
                    return

            tr_files = self.load_task_results(task_result, result_type, tmp_dir)

            if not self._verify_imgs(subtask_id, tr_files):
                self._mark_subtask_failed(subtask_id)
                if not self.use_frames:
                    self._update_task_preview()
                else:
                    self._update_frame_task_preview()
                return

            self.counting_nodes[self.subtasks_given[subtask_id]['node_id']] = 1

            for tr_file in tr_files:

                if not self.use_frames:
                    self._collect_image_part(num_start, tr_file)
                elif self.total_tasks <= len(self.frames):
                    frames_list = self._collect_frames(num_start, tr_file, frames_list, tmp_dir)
                else:
                    self._collect_frame_part(num_start, tr_file, parts, tmp_dir)

            self.num_tasks_received += num_end - num_start + 1

        if self.num_tasks_received == self.total_tasks:
            if self.use_frames:
                self._copy_frames()
            else:
                self._put_image_together(tmp_dir)

    #########################
    # Specific task methods #
    #########################

    def _update_frame_preview(self, new_chunk_file_path, frame_num, part=1, final=False):
        num = self.frames.index(frame_num)
        if new_chunk_file_path.endswith(".exr") or new_chunk_file_path.endswith(".EXR"):
            img = exr_to_pil(new_chunk_file_path)
        else:
            img = Image.open(new_chunk_file_path)

        tmp_dir = get_tmp_path(self.header.node_name, self.header.task_id, self.root_path)
        if self.preview_file_path[num] is None:
            self.preview_file_path[num] = "{}{}".format(os.path.join(tmp_dir, "current_preview"), num)
        if self.preview_task_file_path[num] is None:
            self.preview_task_file_path[num] = "{}{}".format(os.path.join(tmp_dir, "current_task_preview"), num)

        if not final:
            img = self._paste_new_chunk(img, self.preview_file_path[num], part, self.total_tasks / len(self.frames))

        if img:
            img.save(self.preview_file_path[num], "BMP")
            img.save(self.preview_task_file_path[num], "BMP")

    def _paste_new_chunk(self, img_chunk, preview_file_path, chunk_num, all_chunks_num):
        try:
            img_offset = Image.new("RGB", (self.res_x, self.res_y))
            offset = int(math.floor((chunk_num - 1) * float(self.res_y) / float(all_chunks_num)))
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

            if sub['status'] == SubtaskStatus.failure:
                for frame in sub['frames']:
                    self.__mark_sub_frame(sub, frame, failed_color)

    def _open_frame_preview(self, preview_file_path):

        if not os.path.exists(preview_file_path):
            img = Image.new("RGB", (self.res_x, self.res_y))
            img.save(preview_file_path, "BMP")

        return Image.open(preview_file_path)

    def _mark_task_area(self, subtask, img_task, color):
        if not self.use_frames:
            RenderingTask._mark_task_area(self, subtask, img_task, color)
        elif self.__full_frames():
            for i in range(0, self.res_x):
                for j in range(0, self.res_y):
                    img_task.putpixel((i, j), color)
        else:
            parts = self.total_tasks / len(self.frames)
            upper = int(math.floor(float(self.res_y) / float(parts)) * ((subtask['start_task'] - 1) % parts))
            lower = int(math.floor(float(self.res_y) / float(parts)) * ((subtask['start_task'] - 1) % parts + 1))
            for i in range(0, self.res_x):
                for j in range(upper, lower):
                    img_task.putpixel((i, j), color)

    @check_subtask_id_wrapper
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

    def _put_image_together(self, tmp_dir):
        output_file_name = u"{}".format(self.output_file, self.output_format)
        self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
        if not self._use_outer_task_collector():
            collector = RenderingTaskCollector(paste=True, width=self.res_x, height=self.res_y)
            for file in self.collected_file_names.values():
                collector.add_img_file(file)
            collector.finalize().save(output_file_name, self.output_format)
        else:
            self._put_collected_files_together(os.path.join(tmp_dir, output_file_name),
                                               self.collected_file_names.values(), "paste")

    def _put_frame_together(self, tmp_dir, frame_num, num_start):
        output_file_name = os.path.join(tmp_dir, self._get_output_name(frame_num, num_start))
        collected = self.frames_given[frame_num]
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

    def _collect_frames(self, num_start, tr_file, frames_list, tmp_dir):
        self.frames_given[frames_list[0]][0] = tr_file
        self._put_frame_together(tmp_dir, frames_list[0], num_start)
        return frames_list[1:]

    def _collect_frame_part(self, num_start, tr_file, parts, tmp_dir):

        frame_num = self.frames[(num_start - 1) / parts]
        part = self._count_part(num_start, parts)
        self.frames_given[frame_num][part] = tr_file

        self._update_frame_preview(tr_file, frame_num, part)

        if len(self.frames_given[frame_num]) == parts:
            self._put_frame_together(tmp_dir, frame_num, num_start)

    def _count_part(self, start_num, parts):
        return ((start_num - 1) % parts) + 1

    def __full_frames(self):
        return self.total_tasks <= len(self.frames)

    def __mark_sub_frame(self, sub, frame, color):
        tmp_dir = get_tmp_path(self.header.node_name, self.header.task_id, self.root_path)
        idx = self.frames.index(frame)
        preview_task_file_path = "{}{}".format(os.path.join(tmp_dir, "current_task_preview"), idx)
        preview_file_path = "{}{}".format(os.path.join(tmp_dir, "current_preview"), idx)
        img_task = self._open_frame_preview(preview_file_path)
        self._mark_task_area(sub, img_task, color)
        img_task.save(preview_task_file_path, "BMP")
        self.preview_task_file_path[idx] = preview_task_file_path



def get_task_boarder(start_task, end_task, total_tasks, res_x=300, res_y=200, use_frames=False, frames=100,
                     frame_num=1):
    if not use_frames:
        boarder = __get_boarder(start_task, end_task, total_tasks, res_x, res_y)
    elif total_tasks > frames:
        parts = total_tasks / frames
        boarder = __get_boarder((start_task - 1) % parts + 1, (end_task - 1) % parts + 1, parts, res_x, res_y)
    else:
        boarder = []

    return boarder


def get_task_num_from_pixels(p_x, p_y, total_tasks, res_x=300, res_y=200, use_frames=False, frames=100, frame_num=1):
    if not use_frames:
        num = __num_from_pixel(p_y, res_y, total_tasks)
    else:
        if total_tasks <= frames:
            subtask_frames = int(math.ceil(float(frames) / float(total_tasks)))
            num = int(math.ceil(float(frame_num) / subtask_frames))
        else:
            parts = total_tasks / frames
            num = (frame_num - 1) * parts + __num_from_pixel(p_y, res_y, parts)
    return num


def __get_boarder(start_task, end_task, parts, res_x, res_y):
    boarder = []
    upper = int(math.floor(float(res_y) / float(parts) * (start_task - 1)))
    lower = int(math.floor(float(res_y) / float(parts) * end_task))
    for i in range(upper, lower):
        boarder.append((0, i))
        boarder.append((res_x, i))
    for i in range(0, res_x):
        boarder.append((i, upper))
        boarder.append((i, lower))
    return boarder


def __num_from_pixel(p_y, res_y, tasks):
    return int(math.floor(p_y / math.floor(float(res_y) / float(tasks)))) + 1
