from __future__ import division
import os
import logging
import math
from collections import OrderedDict
from PIL import Image, ImageChops

from golem.task.taskstate import SubtaskStatus

from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import Options
from apps.rendering.resources.imgrepr import load_as_pil
from apps.rendering.resources.renderingtaskcollector import RenderingTaskCollector
from apps.rendering.task.renderingtask import RenderingTask, RenderingTaskBuilder
from apps.rendering.task.verificator import FrameRenderingVerificator

logger = logging.getLogger("apps.rendering")

DEFAULT_PADDING = 4


class FrameRendererOptions(Options):
    def __init__(self):
        super(FrameRendererOptions, self).__init__()
        self.use_frames = False
        self.frames = range(1, 11)


class FrameRenderingTask(RenderingTask):

    VERIFICATOR_CLASS = FrameRenderingVerificator

    ################
    # Task methods #
    ################

    def __init__(self, **kwargs):
        super(FrameRenderingTask, self).__init__(**kwargs)

        task_definition = kwargs['task_definition']
        self.use_frames = task_definition.options.use_frames
        self.frames = task_definition.options.frames

        self.frames_given = {}
        for frame in self.frames:
            frame_key = unicode(frame)
            self.frames_given[frame_key] = {}

        if self.use_frames:
            self.preview_file_path = [None] * len(self.frames)
            self.preview_task_file_path = [None] * len(self.frames)

        self.verificator.use_frames = self.use_frames
        self.verificator.frames = self.frames

    @CoreTask.handle_key_error
    def computation_failed(self, subtask_id):
        CoreTask.computation_failed(self, subtask_id)
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

    def accept_results(self, subtask_id, result_files):
        super(FrameRenderingTask, self).accept_results(subtask_id, result_files)
        self.counting_nodes[self.subtasks_given[subtask_id]['node_id']].accept()
        num_start = self.subtasks_given[subtask_id]['start_task']
        parts = self.subtasks_given[subtask_id]['parts']
        num_end = self.subtasks_given[subtask_id]['end_task']
        frames = self.subtasks_given[subtask_id]['frames']

        for result_file in result_files:
            if not self.use_frames:
                self._collect_image_part(num_start, result_file)
            elif self.total_tasks <= len(self.frames):
                frames = self._collect_frames(num_start, result_file, frames)
            else:
                self._collect_frame_part(num_start, result_file, parts)

        self.num_tasks_received += num_end - num_start + 1

        if self.num_tasks_received == self.total_tasks and not self.use_frames:
            self._put_image_together()

    #########################
    # Specific task methods #
    #########################

    def _update_frame_preview(self, new_chunk_file_path, frame_num, part=1, final=False):
        num = self.frames.index(frame_num)
        img = load_as_pil(new_chunk_file_path)

        if not final:
            img = self._paste_new_chunk(img, self._get_preview_file_path(num), part,
                                        int(self.total_tasks / len(self.frames)))

        img_x, img_y = img.size
        img = img.resize((int(round(self.scale_factor * img_x)),
                          int(round(self.scale_factor * img_y))),
                         resample=Image.BILINEAR)
        img.save(self._get_preview_file_path(num), "BMP")
        img.save(self._get_preview_task_file_path(num), "BMP")

        img.close()

    def _paste_new_chunk(self, img_chunk, preview_file_path, chunk_num, all_chunks_num):
        try:
            img_offset = Image.new("RGB", (int(round(self.res_x * self.scale_factor)),
                                           int(round(self.res_y * self.scale_factor))))
            offset = math.floor((chunk_num - 1) * self.res_y * self.scale_factor / all_chunks_num)
            offset = int(offset)
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
            if SubtaskStatus.is_computed(sub['status']):
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
            return

        lower_x = 0
        upper_x = int(round(self.res_x * self.scale_factor))
        if self.__full_frames():
            upper_y = 0
            lower_y = int(round(self.res_y * self.scale_factor))
        else:
            parts = int(self.total_tasks / len(self.frames))
            part_height = self.res_y / parts * self.scale_factor
            upper_y = int(math.ceil(part_height) * ((subtask['start_task'] - 1) % parts))
            lower_y = int(math.floor(part_height) * ((subtask['start_task'] - 1) % parts + 1))

        for i in range(lower_x, upper_x):
            for j in range(upper_y, lower_y):
                img_task.putpixel((i, j), color)

    def _choose_frames(self, frames, start_task, total_tasks):
        if total_tasks <= len(frames):
            subtasks_frames = int(math.ceil(len(frames) / total_tasks))
            start_frame = (start_task - 1) * subtasks_frames
            end_frame = min(start_task * subtasks_frames, len(frames))
            return frames[start_frame:end_frame], 1
        else:
            parts = int(total_tasks / len(frames))
            return [frames[int((start_task - 1) / parts)]], parts

    def _put_image_together(self):
        output_file_name = self.output_file
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

        frame_num = self.frames[int((num_start - 1) / parts)]
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
        preview_task_file_path = self._get_preview_task_file_path(idx)
        img_task = self._open_frame_preview(preview_task_file_path)
        self._mark_task_area(sub, img_task, color, idx)
        img_task.save(preview_task_file_path, "BMP")

    def _get_subtask_file_path(self, subtask_dir_list, name_dir, num):
        if subtask_dir_list[num] is None:
            subtask_dir_list[num] = "{}{}".format(os.path.join(self.tmp_dir, name_dir), num)
        return subtask_dir_list[num]

    def _get_preview_task_file_path(self, num):
        return self._get_subtask_file_path(self.preview_task_file_path, "current_task_preview",
                                           num)

    def _get_preview_file_path(self, num):
        return self._get_subtask_file_path(self.preview_file_path, "current_preview", num)

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


class FrameRenderingTaskBuilder(RenderingTaskBuilder):
    TASK_CLASS = FrameRenderingTask

    def _calculate_total(self, defaults):
        if self.task_definition.optimize_total:
            if self.task_definition.options.use_frames:
                return len(self.task_definition.options.frames)
            else:
                return defaults.default_subtasks

        if self.task_definition.options.use_frames:
            num_frames = len(self.task_definition.options.frames)
            if self.task_definition.total_subtasks > num_frames:
                est = math.floor(self.task_definition.total_subtasks /
                                 num_frames) * num_frames
                est = int(est)
                if est != self.task_definition.total_subtasks:
                    logger.warning("Too many subtasks for this task. %s "
                                   "subtasks will be used", est)
                return est

            est = num_frames / math.ceil(num_frames /
                                         self.task_definition.total_subtasks)
            est = int(math.ceil(est))
            if est != self.task_definition.total_subtasks:
                logger.warning("Too many subtasks for this task. %s "
                               "subtasks will be used.", est)

            return est

        total = self.task_definition.total_subtasks
        if defaults.min_subtasks <= total <= defaults.max_subtasks:
            return total
        else:
            return defaults.default_subtasks

    @classmethod
    def build_dictionary(cls, definition):
        parent = super(FrameRenderingTaskBuilder, cls)
        dictionary = parent.build_dictionary(definition)
        dictionary[u'options'][u'frames'] = definition.options.frames
        return dictionary

    @classmethod
    def build_definition(cls, task_type, dictionary):
        parent = super(FrameRenderingTaskBuilder, cls)
        definition = parent.build_definition(task_type, dictionary)
        definition.options.frames = dictionary['options']['frames']
        return definition


