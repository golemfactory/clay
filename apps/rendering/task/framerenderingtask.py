import logging
import math
import os
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    Type,
    cast,
)
from bisect import insort
from collections import OrderedDict, defaultdict

from copy import deepcopy

from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import Options
from apps.rendering.resources.imgrepr import OpenCVImgRepr
from apps.rendering.resources.renderingtaskcollector import \
    RenderingTaskCollector
from apps.rendering.resources.utils import handle_opencv_image_error
from apps.rendering.task.renderingtask import (
    RenderingTask,
    RenderingTaskBuilder,
    PREVIEW_EXT,
    MIN_PIXELS_PER_SUBTASK,
)
from golem.verifier.rendering_verifier import FrameRenderingVerifier
from golem.core.common import update_dict, to_unicode
from golem.task.taskbase import TaskResult
from golem.task.taskstate import SubtaskStatus, TaskStatus

if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from .renderingtaskstate import RenderingTaskDefinition


logger = logging.getLogger("apps.rendering")

DEFAULT_PADDING = 4


def _round_int(value: int, base: int) -> int:
    """
    The built-in round function is rounding to base 10. This allows rounding to
    other bases.

    It's the same as `round(value / base) * base`, but without using floats,
    which are slow.

    Examples:
    _round_int(0, 6) == 0
    _round_int(2, 6) == 0
    _round_int(3, 6) == 6
    _round_int(8, 6) == 6
    _round_int(9, 6) == 12

    For base=1 it returns value.
    """
    return ((value + base//2) // base) * base


def _calculate_subtasks_count(
        subtasks_count: int,
        use_frames: bool,
        frames: list,
        resolution: List[int]) -> int:
    if subtasks_count < 1:
        logger.warning("Cannot set total subtasks to %s. Changing to 1",
                       subtasks_count)
        return 1

    max_subtasks_per_frame = resolution[1] // MIN_PIXELS_PER_SUBTASK
    num_frames = len(frames) if use_frames else 1
    max_subtasks_count = max_subtasks_per_frame * num_frames

    if subtasks_count <= num_frames:
        new_subtasks_count = subtasks_count
    else:  # subtasks_count > num_frames:
        # round to num_frames, to make sure every frame is divided into
        # whole number of subtasks.
        new_subtasks_count = _round_int(subtasks_count, num_frames)

    new_subtasks_count = min(new_subtasks_count, max_subtasks_count)
    if new_subtasks_count != subtasks_count:
        logger.warning(
            "Cannot set total subtask count to %s. Changing to %s.",
            subtasks_count,
            new_subtasks_count
        )

    return new_subtasks_count


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
        return self.status.name, self.started


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

        parts = max(1, int(self.get_total_tasks() / len(self.frames)))

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
    def computation_failed(self, subtask_id: str, ban_node: bool = True):
        CoreTask.computation_failed(self, subtask_id, ban_node)
        if self.use_frames:
            self._update_frame_task_preview()
            self._update_subtask_frame_status(subtask_id)
        else:
            self._update_task_preview()

    @CoreTask.handle_key_error
    def computation_finished(
            self, subtask_id: str, task_result: TaskResult,
            verification_finished: Callable[[], None]) -> None:
        super(FrameRenderingTask, self).computation_finished(
            subtask_id,
            task_result,
            verification_finished)

    def verification_finished(self, subtask_id, verdict, result):
        super().verification_finished(subtask_id,
                                      verdict, result)
        if self.use_frames:
            self._update_subtask_frame_status(subtask_id)

    def restart_subtask(
            self,
            subtask_id,
            new_state: Optional[SubtaskStatus] = None,
    ):
        super(FrameRenderingTask, self).restart_subtask(
            subtask_id,
            new_state=new_state,
        )
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

    def get_subtasks(self, part) -> Dict[str, dict]:
        if self.task_definition.options.use_frames:
            subtask_ids = self.frames_subtasks.get(to_unicode(part), [])
            subtask_ids = filter(None, subtask_ids)
        else:
            subtask_ids = self.subtasks_given.keys()

        subtasks = {}

        for subtask_id in subtask_ids:
            subtasks[subtask_id] =\
                self.subtasks_given[subtask_id]

        return subtasks

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        num_start = self.subtasks_given[subtask_id]['start_task']
        parts = self.subtasks_given[subtask_id]['parts']
        frames = self.subtasks_given[subtask_id]['frames']

        for result_file in result_files:
            if not self.use_frames:
                self._collect_image_part(num_start, result_file)
            elif self.get_total_tasks() <= len(self.frames):
                frames = self._collect_frames(num_start, result_file, frames)
            else:
                self._collect_frame_part(num_start, result_file, parts)

        self.num_tasks_received += 1

        if self.num_tasks_received == \
                self.get_total_tasks() and not self.use_frames:
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

    def subtask_status_updated(self, subtask_id: str) -> None:
        self._update_subtask_frame_status(subtask_id)

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

    def _update_frame_preview(self, new_chunk_file_path, frame_num, part=1,
                              final=False):
        num = self.frames.index(frame_num)
        preview_task_file_path = self._get_preview_task_file_path(num)

        with handle_opencv_image_error(logger):
            logger.debug('new_chunk_file_path = {}'.format(new_chunk_file_path))
            img = OpenCVImgRepr.from_image_file(new_chunk_file_path)

            def resize_and_save(img):
                img.resize(int(round(self.scale_factor * img.get_width())),
                           int(round(self.scale_factor * img.get_height())))

                img.save_with_extension(self._get_preview_file_path(num),
                                        PREVIEW_EXT)

            if not final:
                img_pasted = self._paste_new_chunk(
                    img, self._get_preview_file_path(num), part,
                    int(self.get_total_tasks() / len(self.frames))
                )
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
        frame_key = str(frame)
        state = self.frames_state[frame_key]
        subtask_ids = self.frames_subtasks[frame_key]

        parts = max(1, self.get_total_tasks() // len(self.frames))
        counters = defaultdict(lambda: 0, dict())

        # Count the number of occurrences of each subtask state
        for subtask_id in filter(bool, subtask_ids):
            subtask = self.subtasks_given[subtask_id]
            counters[subtask['status']] += 1

        computing = len([x for x in counters.keys() if x.is_active()])

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

    def _paste_new_chunk(self, img_chunk, preview_file_path, chunk_num,
                         all_chunks_num):

        try:
            img_offset = OpenCVImgRepr.empty(int(round(self.res_x *
                                                       self.scale_factor)),
                                             int(round(self.res_y
                                                       * self.scale_factor)))
            offset = int(math.floor((chunk_num - 1) * self.res_y
                                    * self.scale_factor / all_chunks_num))
            img_offset.paste_image(img_chunk, 0, offset)

        except Exception as e:
            logger.error("Can't generate preview {}".format(e))
            img_offset = None

        with handle_opencv_image_error(logger):
            existing_frame_preview = OpenCVImgRepr.from_image_file(
                preview_file_path)
            if img_offset:
                existing_frame_preview.add(img_offset)
            return existing_frame_preview
        logger.error("Can't add new chunk to preview")
        return img_offset

    def _update_frame_task_preview(self):
        sent_color = (0, 255, 0)
        failed_color = (255, 0, 0)

        for sub in list(self.subtasks_given.values()):
            if sub['status'].is_active():
                for frame in sub['frames']:
                    self.__mark_sub_frame(sub, frame, sent_color)

            if sub['status'] in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                for frame in sub['frames']:
                    self.__mark_sub_frame(sub, frame, failed_color)

    def _open_frame_preview(self, preview_file_path):

        if not os.path.exists(preview_file_path):
            img = OpenCVImgRepr.empty(
                int(round(self.res_x * self.scale_factor)),
                int(round(self.res_y * self.scale_factor)))
            img.save_with_extension(preview_file_path, PREVIEW_EXT)

        return OpenCVImgRepr.from_image_file(preview_file_path)

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
            parts = max(1, int(self.get_total_tasks() / len(self.frames)))
            part_height = self.res_y / parts * self.scale_factor
            upper_y = int(math.ceil(part_height) * ((subtask['start_task'] - 1) % parts))
            lower_y = int(math.floor(part_height) * ((subtask['start_task'] - 1) % parts + 1))

        for i in range(lower_x, upper_x):
            for j in range(upper_y, lower_y):
                img_task.set_pixel((i, j), color)

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
        collector = RenderingTaskCollector(width=self.res_x,
                                           height=self.res_y)
        for file in self.collected_file_names.values():
            collector.add_img_file(file)
        with handle_opencv_image_error(logger):
            image = collector.finalize()
            image.save_with_extension(output_file_name, self.output_format)

    def _put_frame_together(self, frame_num, num_start):
        directory = os.path.dirname(self.output_file)
        output_file_name = os.path.join(directory, self._get_output_name(frame_num))
        frame_key = str(frame_num)
        collected = self.frames_given[frame_key]
        collected = OrderedDict(sorted(collected.items()))
        collector = RenderingTaskCollector(width=self.res_x,
                                           height=self.res_y)
        for file in collected.values():
            collector.add_img_file(file)
        with handle_opencv_image_error(logger):
            image = collector.finalize()
            image.save_with_extension(output_file_name, self.output_format)

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
        return self.get_total_tasks() <= len(self.frames)

    def __mark_sub_frame(self, sub, frame, color):
        idx = self.frames.index(frame)
        preview_task_file_path = self._get_preview_task_file_path(idx)
        with handle_opencv_image_error(logger):
            img_task = self._open_frame_preview(preview_task_file_path)
            self._mark_task_area(sub, img_task, color, idx)
            img_task.save_with_extension(preview_task_file_path, PREVIEW_EXT)

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
    TASK_CLASS: Type[FrameRenderingTask]

    def __init__(self, owner, task_definition, dir_manager):
        frames = task_definition.options.frames

        if isinstance(frames, str):
            task_definition = deepcopy(task_definition)
            task_definition.options.frames = self.string_to_frames(frames)

        super(FrameRenderingTaskBuilder, self).__init__(owner,
                                                        task_definition,
                                                        dir_manager)

    @classmethod
    def build_dictionary(cls, definition):
        parent = super(FrameRenderingTaskBuilder, cls)
        dictionary = parent.build_dictionary(definition)
        dictionary['options']['frames'] = definition.options.frames_string
        return dictionary

    @classmethod
    def build_minimal_definition(cls, task_type, dictionary) \
            -> 'RenderingTaskDefinition':
        parent = cast(Type[RenderingTaskBuilder],
                      super(FrameRenderingTaskBuilder, cls))
        options = dictionary.get('options') or dict()

        frames_string = to_unicode(options.get('frames', 1))
        frames = cls.string_to_frames(frames_string)
        use_frames = options.get('use_frames', len(frames) > 1)

        definition = parent.build_minimal_definition(task_type, dictionary)
        definition.options.frames_string = frames_string
        definition.options.frames = frames
        definition.options.use_frames = use_frames
        definition.subtasks_count = int(dictionary['subtasks_count'])

        return definition

    @classmethod
    def build_full_definition(cls, task_type, dictionary) \
            -> 'RenderingTaskDefinition':
        parent = cast(Type[RenderingTaskBuilder],
                      super(FrameRenderingTaskBuilder, cls))

        definition = parent.build_full_definition(task_type, dictionary)
        definition.subtasks_count = _calculate_subtasks_count(
            subtasks_count=int(dictionary['subtasks_count']),
            use_frames=definition.options.use_frames,
            frames=definition.options.frames,
            resolution=definition.resolution,
        )
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


