import logging
import math
import os
from bisect import insort
from collections import OrderedDict, defaultdict

from PIL import Image, ImageChops
from copy import deepcopy

from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import Options
from apps.rendering.resources.imgrepr import load_as_pil
from apps.rendering.resources.renderingtaskcollector import \
    RenderingTaskCollector
from apps.rendering.resources.utils import handle_image_error, handle_none
from apps.rendering.task.renderingtask import (RenderingTask,
                                               RenderingTaskBuilder,
                                               PREVIEW_EXT)
from apps.rendering.task.verifier import FrameRenderingVerifier
from golem.core.common import update_dict, to_unicode
from golem.task.taskbase import ResultType
from golem.task.taskstate import SubtaskStatus, TaskStatus, SubtaskState

logger = logging.getLogger("apps.rendering")

DEFAULT_PADDING = 4


class FrameRendererOptions(Options):
    def __init__(self):
        super(FrameRendererOptions, self).__init__()
        self.use_frames = True
        self.frames = list(range(1, 11))
        self.frames_string = "1-10"


class FrameState(object):
    __slots__ = ['status', 'started']

    def __init__(self):
        self.status = TaskStatus.notStarted
        self.started = None

    def serialize(self):
        return to_unicode(self.status), self.started


class FrameRenderingTask(RenderingTask):

    VERIFIER_CLASS = FrameRenderingVerifier

    ################
    # Task methods #
    ################

    def __init__(self, **kwargs):
        super(FrameRenderingTask, self).__init__(**kwargs)

        task_definition = kwargs['task_definition']
        self.use_frames = task_definition.options.use_frames
        self.frames = task_definition.options.frames

        parts = max(1, int(self.total_tasks / len(self.frames)))

        self.frames_given = {}
        self.frames_state = {}
        self.frames_subtasks = {}

        for frame in self.frames:
            frame_key = str(frame)
            self.frames_given[frame_key] = {}
            self.frames_state[frame_key] = FrameState()
            self.frames_subtasks[frame_key] = [None] * parts

        if self.use_frames:
            self.preview_file_path = [None] * len(self.frames)
            self.preview_task_file_path = [None] * len(self.frames)
        self.last_preview_path = None

    @CoreTask.handle_key_error
    def computation_failed(self, subtask_id):
        CoreTask.computation_failed(self, subtask_id)
        if self.use_frames:
            self._update_frame_task_preview()
            self._update_subtask_frame_status(subtask_id)
        else:
            self._update_task_preview()

    @CoreTask.handle_key_error
    def computation_finished(self, subtask_id, task_result,
                             result_type=ResultType.DATA,
                             verification_finished_=None):
        super(FrameRenderingTask, self).computation_finished(
            subtask_id,
            task_result,
            result_type,
            verification_finished_)

    def verification_finished(self, subtask_id, verdict, result):
        super(FrameRenderingTask, self).verification_finished(subtask_id,
                                                              verdict, result)
        if self.use_frames:
            self._update_subtask_frame_status(subtask_id)

    def restart_subtask(self, subtask_id):
        super(FrameRenderingTask, self).restart_subtask(subtask_id)
        self._update_subtask_frame_status(subtask_id)

    def get_output_names(self):
        if self.use_frames:
            dir_ = os.path.dirname(self.output_file)
            return [os.path.normpath(os.path.join(dir_, self._get_output_name(frame))) for frame in self.frames]
        else:
            return super(FrameRenderingTask, self).get_output_names()

    def get_output_states(self):
        if self.use_frames:
            result = []
            for k, v in self.frames_state.items():
                insort(result, (k, v.serialize()))
            return result
        return []

    def get_subtasks(self, frame):
        if self.task_definition.options.use_frames:
            subtask_ids = self.frames_subtasks.get(to_unicode(frame), [])
        else:
            subtask_ids = self.subtasks_given.keys()

        subtasks = dict()

        # Convert to SubtaskState in order to match parent's return type
        for subtask_id in subtask_ids:
            state = SubtaskState()
            state.extra_data = self.subtasks_given[subtask_id]
            subtasks[subtask_id] = state

        return subtasks

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
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

    def get_frames_to_subtasks(self):
        frames = OrderedDict((frame_num, []) for frame_num in self.frames)

        for subtask_id, subtask in self.subtasks_given.items():
            if subtask and subtask['frames']:
                for frame in subtask['frames']:
                    frames[frame].append(subtask_id)
        return frames

    def to_dictionary(self):
        dictionary = super(FrameRenderingTask, self).to_dictionary()
        frame_count = len(self.frames) if self.use_frames else 1

        return update_dict(dictionary, {'options': {
            'frame_count': frame_count
        }})

    #########################
    # Specific task methods #
    #########################

    @CoreTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        if not isinstance(self.preview_file_path, (list, tuple)):
            return super()._remove_from_preview(subtask_id)
        empty_color = (0, 0, 0)
        sub = self.subtasks_given[subtask_id]
        for frame in sub['frames']:
            # __mark_sub_frame() also saves preview_file_path(num)
            self.__mark_sub_frame(sub, frame, empty_color)

    def _update_frame_preview(self, new_chunk_file_path, frame_num, part=1, final=False):
        num = self.frames.index(frame_num)
        preview_task_file_path = self._get_preview_task_file_path(num)

        with handle_image_error(logger), \
                handle_none(load_as_pil(new_chunk_file_path),
                            raise_if_none=IOError("load_as_pil failed")) as img:

            def resize_and_save(img):
                img_x, img_y = img.size
                with img.resize((int(round(self.scale_factor * img_x)),
                                 int(round(self.scale_factor * img_y))),
                                resample=Image.BILINEAR) as img_resized:
                    img_resized.save(self._get_preview_file_path(num),
                                     PREVIEW_EXT)
                    img_resized.save(preview_task_file_path, PREVIEW_EXT)

            if not final:
                with self._paste_new_chunk(
                    img, self._get_preview_file_path(num), part,
                    int(self.total_tasks / len(self.frames))
                ) as img_pasted:
                    resize_and_save(img_pasted)
            else:
                resize_and_save(img)

        self.last_preview_path = preview_task_file_path

    @CoreTask.handle_key_error
    def _update_subtask_frame_status(self, subtask_id):
        frames = self.subtasks_given[subtask_id]['frames']
        for frame in frames:
            self._update_frame_status(frame)

    def _update_frame_status(self, frame):
        frame_key = to_unicode(frame)
        state = self.frames_state[frame_key]
        subtask_ids = self.frames_subtasks[frame_key]

        parts = max(1, int(self.total_tasks / len(self.frames)))
        counters = defaultdict(lambda: 0, dict())

        # Count the number of occurrences of each subtask state
        for subtask_id in filter(bool, subtask_ids):
            subtask = self.subtasks_given[subtask_id]
            counters[subtask['status']] += 1

        # Count statuses different from 'finished' and 'failure'
        computing = len([x for x in counters.keys()
                         if x not in [SubtaskStatus.finished,
                                      SubtaskStatus.failure]])

        # Finished if at least n subtasks >= parts were finished
        if counters[SubtaskStatus.finished] >= parts:
            state.status = TaskStatus.finished
        # Computing if at least one subtask did not fail
        elif computing > 0:
            state.status = TaskStatus.computing
        # Failure if the only known subtask status is 'failure'
        elif counters[SubtaskStatus.failure] > 0:
            state.status = TaskStatus.aborted
        # Otherwise, do not change frame's status.

    def _paste_new_chunk(self, img_chunk, preview_file_path, chunk_num, all_chunks_num):
        try:
            img_offset = Image.new("RGB", (int(round(self.res_x * self.scale_factor)),
                                           int(round(self.res_y * self.scale_factor))))
            offset = math.floor((chunk_num - 1) * self.res_y * self.scale_factor / all_chunks_num)
            offset = int(offset)
            img_offset.paste(img_chunk, (0, offset))
        except Exception as err:
            logger.error("Can't generate preview {}".format(err))
            img_offset.close()
            img_offset = None

        if not os.path.exists(preview_file_path):
            return img_offset

        try:
            if img_offset:
                with Image.open(preview_file_path) as img:
                    result = ImageChops.add(img, img_offset)
                    img_offset.close()
                    return result 
            else:
                return Image.open(preview_file_path)
        except Exception as err:
            logger.error("Can't add new chunk to preview{}".format(err))
            return img_offset

    def _update_frame_task_preview(self):
        sent_color = (0, 255, 0)
        failed_color = (255, 0, 0)

        for sub in list(self.subtasks_given.values()):
            if SubtaskStatus.is_active(sub['status']):
                for frame in sub['frames']:
                    self.__mark_sub_frame(sub, frame, sent_color)

            if sub['status'] in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                for frame in sub['frames']:
                    self.__mark_sub_frame(sub, frame, failed_color)

    def _open_frame_preview(self, preview_file_path):

        if not os.path.exists(preview_file_path):
            with handle_image_error(logger), \
                    Image.new("RGB",
                              (int(round(self.res_x * self.scale_factor)),
                               int(round(self.res_y * self.scale_factor)))) \
                    as img:
                img.save(preview_file_path, PREVIEW_EXT)

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
            parts = max(1, int(self.total_tasks / len(self.frames)))
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
            parts = max(1, int(total_tasks / len(frames)))
            return [frames[int((start_task - 1) / parts)]], parts

    def _put_image_together(self):
        output_file_name = self.output_file
        self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
        if not self._use_outer_task_collector():
            collector = RenderingTaskCollector(paste=True, width=self.res_x, height=self.res_y)
            for file in self.collected_file_names.values():
                collector.add_img_file(file)
            with handle_image_error(logger), \
                    collector.finalize() as image:
                image.save(output_file_name, self.output_format)
        else:
            self._put_collected_files_together(os.path.join(self.tmp_dir, output_file_name),
                                               list(self.collected_file_names.values()), "paste")

    def _put_frame_together(self, frame_num, num_start):
        directory = os.path.dirname(self.output_file)
        output_file_name = os.path.join(directory, self._get_output_name(frame_num))
        frame_key = str(frame_num)
        collected = self.frames_given[frame_key]
        collected = OrderedDict(sorted(collected.items()))
        if not self._use_outer_task_collector():
            collector = RenderingTaskCollector(paste=True, width=self.res_x, height=self.res_y)
            for file in collected.values():
                collector.add_img_file(file)
            with handle_image_error(logger), \
                    collector.finalize() as image:
                image.save(output_file_name, self.output_format)
        else:
            self._put_collected_files_together(output_file_name, list(collected.values()), "paste")

        self.collected_file_names[frame_num] = output_file_name
        self._update_frame_preview(output_file_name, frame_num, final=True)
        self._update_frame_task_preview()

    def _collect_image_part(self, num_start, tr_file):
        self.collected_file_names[num_start] = tr_file
        self._update_preview(tr_file, num_start)
        self._update_task_preview()

    def _collect_frames(self, num_start, tr_file, frames_list):
        frame_key = str(frames_list[0])
        self.frames_given[frame_key][0] = tr_file
        self._put_frame_together(frames_list[0], num_start)
        return frames_list[1:]

    def _collect_frame_part(self, num_start, tr_file, parts):

        frame_num = self.frames[int((num_start - 1) / parts)]
        frame_key = str(frame_num)
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
        with self._open_frame_preview(preview_task_file_path) as img_task:
            self._mark_task_area(sub, img_task, color, idx)
            img_task.save(preview_task_file_path, PREVIEW_EXT)

    def _get_subtask_file_path(self, subtask_dir_list, name_dir, num):
        if subtask_dir_list[num] is None:
            subtask_dir_list[num] = "{}{}.{}".format(os.path.join(self.tmp_dir,
                                                                  name_dir),
                                                     num, PREVIEW_EXT)
        return subtask_dir_list[num]

    def _get_preview_task_file_path(self, num):
        return self._get_subtask_file_path(self.preview_task_file_path,
                                           "current_task_preview", num)

    def _get_preview_file_path(self, num):
        return self._get_subtask_file_path(self.preview_file_path,
                                           "current_preview", num)

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
        return "{}.{}".format(output_name[:idl+1] + str(frame_num).zfill(idr-idl) + output_name[idr+1:], ext)
    else:
        return "{}{}.{}".format(output_name, str(frame_num).zfill(DEFAULT_PADDING), ext)


class FrameRenderingTaskBuilder(RenderingTaskBuilder):
    TASK_CLASS = FrameRenderingTask

    def __init__(self, node_name, task_definition, root_path, dir_manager):
        frames = task_definition.options.frames

        if isinstance(frames, str):
            task_definition = deepcopy(task_definition)
            task_definition.options.frames = self.string_to_frames(frames)

        super(FrameRenderingTaskBuilder, self).__init__(node_name,
                                                        task_definition,
                                                        root_path, dir_manager)

    def _calculate_total(self, defaults):
        if self.task_definition.optimize_total or \
           not self.task_definition.total_subtasks:
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
        dictionary['options']['frames'] = definition.options.frames_string
        return dictionary

    @classmethod
    def build_minimal_definition(cls, task_type, dictionary):
        parent = super(FrameRenderingTaskBuilder, cls)
        options = dictionary.get('options') or dict()

        frames_string = to_unicode(options.get('frames', 1))
        frames = cls.string_to_frames(frames_string)
        use_frames = options.get('use_frames', len(frames) > 1)

        definition = parent.build_minimal_definition(task_type, dictionary)
        definition.options.frames_string = frames_string
        definition.options.frames = frames
        definition.options.use_frames = use_frames

        return definition

    @staticmethod
    def frames_to_string(frames):
        s = ""
        last_frame = None
        interval = False
        try:
            for frame in sorted(frames):
                frame = int(frame)
                if frame < 0:
                    raise ValueError("Frame number must be "
                                     "greater or equal to 0")

                if last_frame is None:
                    s += str(frame)
                elif frame - last_frame == 1:
                    if not interval:
                        s += '-'
                        interval = True
                elif interval:
                    s += str(last_frame) + ";" + str(frame)
                    interval = False
                else:
                    s += ';' + str(frame)

                last_frame = frame

        except (ValueError, AttributeError, TypeError) as err:
            logger.error("Wrong frame format: {}".format(err))
            return ""

        if interval:
            s += str(last_frame)

        return s

    @staticmethod
    def string_to_frames(s):
        try:
            frames = []
            after_split = s.split(";")
            for i in after_split:
                inter = i.split("-")
                if len(inter) == 1:
                    # single frame (e.g. 5)
                    frames.append(int(inter[0]))
                elif len(inter) == 2:
                    inter2 = inter[1].split(",")
                    # frame range (e.g. 1-10)
                    if len(inter2) == 1:
                        start_frame = int(inter[0])
                        end_frame = int(inter[1]) + 1
                        frames += list(range(start_frame, end_frame))
                    # every nth frame (e.g. 10-100,5)
                    elif len(inter2) == 2:
                        start_frame = int(inter[0])
                        end_frame = int(inter2[0]) + 1
                        step = int(inter2[1])
                        frames += list(range(start_frame, end_frame, step))
                    else:
                        raise ValueError("Wrong frame step")
                else:
                    raise ValueError("Wrong frame range")
            return sorted(frames)
        except ValueError as err:
            logger.warning("Wrong frame format: {}".format(err))
            return []
        except (AttributeError, TypeError) as err:
            logger.error("Problem with change string to frame: {}".format(err))
            return []


