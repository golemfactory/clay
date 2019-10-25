import functools
import logging
import math
import os
import random
import time
from collections import OrderedDict
from copy import copy
from typing import Optional, Type

import apps.blender.resources.blenderloganalyser as log_analyser
from apps.blender.blenderenvironment import BlenderEnvironment, \
    BlenderNVGPUEnvironment
from apps.core.task.coretask import CoreTaskTypeInfo
from apps.rendering.resources.imgrepr import OpenCVImgRepr
from apps.rendering.resources.renderingtaskcollector import \
    RenderingTaskCollector
from apps.rendering.resources.utils import handle_opencv_image_error
from apps.rendering.task.framerenderingtask import FrameRenderingTask, \
    FrameRenderingTaskBuilder, FrameRendererOptions
from apps.rendering.task.renderingtask import PREVIEW_EXT, PREVIEW_X, \
    PREVIEW_Y
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from golem.core.common import short_node_id, to_unicode
from golem.core.fileshelper import has_ext
from golem.docker.task_thread import DockerTaskThread
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import TaskPurpose, TaskTypeInfo
from golem.task.taskstate import SubtaskStatus, TaskStatus
from golem.verifier.blender_verifier import BlenderVerifier

logger = logging.getLogger(__name__)


class PreviewUpdater(object):
    def __init__(self, preview_file_path, preview_res_x, preview_res_y,
                 expected_offsets):
        # pairs of (subtask_number, its_image_filepath)
        # careful: chunks' numbers start from 1
        self.chunks = {}
        self.preview_res_x = preview_res_x
        self.preview_res_y = preview_res_y
        self.preview_file_path = preview_file_path
        self.expected_offsets = expected_offsets

        # where the match ends - since the chunks have unexpectable sizes, we
        # don't know where to paste new chunk unless all of the above are in
        # their correct places
        self.perfect_match_area_y = 0
        self.perfectly_placed_subtasks = 0

    def get_offset(self, subtask_number):
        return self.expected_offsets.get(subtask_number, self.preview_res_y)

    def update_preview(self, subtask_path, subtask_number):
        if subtask_number not in self.chunks:
            self.chunks[subtask_number] = subtask_path

        with handle_opencv_image_error(logger) as handler_result:

            subtask_img = OpenCVImgRepr.from_image_file(subtask_path)

            offset = self.get_offset(subtask_number)
            if subtask_number == self.perfectly_placed_subtasks + 1:
                self.perfect_match_area_y += subtask_img.get_height()
                self.perfectly_placed_subtasks += 1

            chunk_height = self._get_height(subtask_number)

            subtask_img_resized = subtask_img.resize(self.preview_res_x,
                                                     chunk_height)

            def open_or_create_image():
                if not os.path.exists(self.preview_file_path) \
                        or len(self.chunks) == 1:
                    chunk_channels = subtask_img.get_channels()
                    return OpenCVImgRepr.empty(self.preview_res_x,
                                               self.preview_res_y,
                                               channels=chunk_channels)
                return OpenCVImgRepr.from_image_file(self.preview_file_path)

            preview_img = open_or_create_image()

            subtask_img_resized.try_adjust_type(OpenCVImgRepr.IMG_U8)

            preview_img.paste_image(subtask_img_resized, 0, offset)
            preview_img.save_with_extension(self.preview_file_path, PREVIEW_EXT)

        if not handler_result.success:
            return

        if subtask_number == self.perfectly_placed_subtasks and \
                (subtask_number + 1) in self.chunks:
            self.update_preview(self.chunks[subtask_number + 1],
                                subtask_number + 1)

    def restart(self):
        self.chunks = {}
        self.perfect_match_area_y = 0
        self.perfectly_placed_subtasks = 0
        if os.path.exists(self.preview_file_path):
            with handle_opencv_image_error(logger):
                OpenCVImgRepr.empty(self.preview_res_x, self.preview_res_y) \
                    .save_with_extension(self.preview_file_path, PREVIEW_EXT)

    def _get_height(self, subtask_number):
        next_offset = \
            self.expected_offsets.get(subtask_number + 1, self.preview_res_y)
        return next_offset - self.expected_offsets.get(subtask_number)


class RenderingTaskTypeInfo(CoreTaskTypeInfo):

    @classmethod
    def get_preview(cls, task, single=False):
        result = None
        if not task:
            pass
        elif task.use_frames:
            if single:
                return to_unicode(task.last_preview_path)
            else:
                previews = [to_unicode(p) for p in task.preview_task_file_path]
                result = {}
                for i, f in enumerate(task.frames):
                    try:
                        result[to_unicode(f)] = previews[i]
                    except IndexError:
                        result[to_unicode(f)] = None
        else:
            result = to_unicode(task.preview_task_file_path or
                                task.preview_file_path)
        return cls._preview_result(result, single=single)

    @classmethod
    def scale_factor(cls, res_x, res_y):
        preview_x = PREVIEW_X
        preview_y = PREVIEW_Y
        if res_x != 0 and res_y != 0:
            if res_x / res_y > preview_x / preview_y:
                scale_factor = preview_x / res_x
            else:
                scale_factor = preview_y / res_y
            scale_factor = min(1.0, scale_factor)
        else:
            scale_factor = 1.0
        return scale_factor

    @classmethod
    def get_task_border(cls, extra_data: dict, definition, subtasks_count,
                        as_path=False):
        """ Return list of pixels that should be marked as a border of
         a given extra_data
        :param RenderingTaskDefinition definition: task definition
        :param int subtasks_count: total number of subtasks used in this task
        :param int as_path: return pixels that form a border path
        :return list: list of pixels that belong to a subtask border
        """
        start_task = extra_data['start_task']
        frames = len(definition.options.frames)
        res_x, res_y = definition.resolution

        if as_path:
            method = cls.__get_border_path
        else:
            method = cls.__get_border

        if not definition.options.use_frames:
            return method(start_task, subtasks_count, res_x, res_y)
        elif subtasks_count <= frames:
            if not as_path:
                return []
            scale_factor = cls.scale_factor(res_x, res_y)
            x = int(math.floor(res_x * scale_factor))
            y = int(math.floor(res_y * scale_factor))
            return [(0, y), (x, y),
                    (x, 0), (0, 0)]

        parts = int(subtasks_count / frames)
        return method((start_task - 1) % parts + 1,
                      parts, res_x, res_y)

    @classmethod
    def __get_border(cls, start, parts, res_x, res_y):
        """
        Return list of pixels that should be marked as a border of subtasks
        with numbers between start and end.
        :param int start: number of first subtask
        :param int parts: number of parts for single frame
        :param int res_x: image resolution width
        :param int res_y: image resolution height
        :return list: list of pixels that belong to a subtask border
        """
        border = []
        if res_x == 0 or res_y == 0:
            return border
        offsets = generate_expected_offsets(parts, res_x, res_y)
        scale_factor = offsets[parts + 1] / res_y
        x = int(math.floor(res_x * scale_factor))

        upper = offsets[start]
        lower = offsets[start + 1]
        for i in range(upper, lower):
            border.append((0, i))
            border.append((x, i))
        for i in range(0, x):
            border.append((i, upper))
            border.append((i, lower))
        return border

    @classmethod
    def __get_border_path(cls, start, parts, res_x, res_y):
        """
        Return list of points that make a border of subtasks with numbers
        between start and end.
        :param int start: number of first subtask
        :param int parts: number of parts for single frame
        :param int res_x: image resolution width
        :param int res_y: image resolution height
        :return list: list of pixels that belong to a subtask border
        """
        if res_x == 0 or res_y == 0:
            return []

        offsets = generate_expected_offsets(parts, res_x, res_y)
        scale_factor = offsets[parts + 1] / res_y

        x = int(math.floor(res_x * scale_factor))
        upper = offsets[start]
        lower = max(0, offsets[start + 1] - 1)

        return [(0, upper), (x, upper),
                (x, lower), (0, lower)]


class BlenderTaskTypeInfo(RenderingTaskTypeInfo):
    """ Blender App description that can be used by interface to define
    parameters and task build
    """

    def __init__(self):
        super(BlenderTaskTypeInfo, self).__init__("Blender",
                                                  RenderingTaskDefinition,
                                                  BlenderRendererOptions,
                                                  BlenderRenderTaskBuilder)

        self.output_formats = ["PNG", "TGA", "EXR", "JPEG", "BMP"]
        self.output_file_ext = ["blend"]


class BlenderNVGPUTaskTypeInfo(RenderingTaskTypeInfo):

    def __init__(self):
        super().__init__("Blender_NVGPU",
                         RenderingTaskDefinition,
                         BlenderNVGPURendererOptions,
                         BlenderNVGPURenderTaskBuilder)

        self.output_formats = ["PNG", "TGA", "EXR", "JPEG", "BMP"]
        self.output_file_ext = ["blend"]

    def for_purpose(self, purpose: TaskPurpose) -> TaskTypeInfo:
        # Testing the task shouldn't require a compatible GPU + OS
        if purpose == TaskPurpose.TESTING:
            return BlenderTaskTypeInfo()
        return self


class BlenderRendererOptions(FrameRendererOptions):

    def __init__(self):
        super(BlenderRendererOptions, self).__init__()
        self.environment = BlenderEnvironment()
        self.compositing = False
        self.samples = 0


class BlenderNVGPURendererOptions(BlenderRendererOptions):

    def __init__(self):
        super().__init__()
        self.environment = BlenderNVGPUEnvironment()


class BlenderRenderTask(FrameRenderingTask):
    ENVIRONMENT_CLASS: Type[BlenderEnvironment] = BlenderEnvironment
    VERIFIER_CLASS = functools.partial(BlenderVerifier,
                                       docker_task_cls=DockerTaskThread)

    BLENDER_MIN_BOX = [8, 8]
    BLENDER_MIN_SAMPLE = 5

    ################
    # Task methods #
    ################
    def __init__(self, task_definition, **kwargs):
        self.preview_updater = None
        self.preview_updaters = None

        super().__init__(task_definition=task_definition, **kwargs)

        # https://github.com/golemfactory/golem/issues/2388
        self.compositing = False
        self.samples = task_definition.options.samples

    def initialize(self, dir_manager):
        super(BlenderRenderTask, self).initialize(dir_manager)

        if self.use_frames:
            parts = int(self.get_total_tasks() / len(self.frames))
        else:
            parts = self.get_total_tasks()
        expected_offsets = generate_expected_offsets(parts, self.res_x,
                                                     self.res_y)
        preview_y = expected_offsets[parts + 1]
        if self.res_y != 0 and preview_y != 0:
            self.scale_factor = preview_y / self.res_y
        preview_x = int(round(self.res_x * self.scale_factor))

        if self.use_frames:
            self.preview_file_path = []
            self.preview_updaters = []
            for i in range(0, len(self.frames)):
                preview_name = "current_task_preview{}.{}".format(i,
                                                                  PREVIEW_EXT)
                preview_path = os.path.join(self.tmp_dir, preview_name)
                self.preview_file_path.append(preview_path)
                self.preview_updaters.append(PreviewUpdater(preview_path,
                                                            preview_x,
                                                            preview_y,
                                                            expected_offsets))
        else:
            preview_name = "current_preview.{}".format(PREVIEW_EXT)
            self.preview_file_path = "{}".format(os.path.join(self.tmp_dir,
                                                              preview_name))
            self.preview_updater = PreviewUpdater(self.preview_file_path,
                                                  preview_x,
                                                  preview_y,
                                                  expected_offsets)

    # pylint: disable-msg=too-many-locals
    def query_extra_data(self, perf_index: float,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) \
            -> FrameRenderingTask.ExtraData:

        start_task = self._get_next_task()
        scene_file = self._get_scene_file_rel_path()

        if self.use_frames:
            frames, parts = self._choose_frames(self.frames, start_task,
                                                self.get_total_tasks())
        else:
            frames = self.frames or [1]
            parts = 1

        min_y, max_y = self.get_subtask_y_border(start_task)

        crops = [
            {"outfilebasename": "{}_{}".format(
                self.outfilebasename, start_task),
             "borders_x": [0.0, 1.0],
             "borders_y": [min_y, max_y]}
        ]
        extra_data = {"scene_file": scene_file,
                      "resolution": [self.res_x, self.res_y],
                      "use_compositing": self.compositing,
                      "samples": self.samples,
                      "frames": frames,
                      "output_format": self.output_format,
                      "path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "total_tasks": self.get_total_tasks(),
                      "crops": crops,
                      "entrypoint":
                          "python3 /golem/entrypoints/render_entrypoint.py",
                      }

        subtask_id = self.create_subtask_id()
        logger.debug(
            'Created new subtask for task. '
            'task_id=%s, subtask_id=%s, node_id=%s',
            self.header.task_id,
            subtask_id,
            short_node_id(node_id or '')
        )
        self.subtasks_given[subtask_id] = copy(extra_data)
        self.subtasks_given[subtask_id]['subtask_id'] = subtask_id
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.starting
        self.subtasks_given[subtask_id]['node_id'] = node_id
        self.subtasks_given[subtask_id]['parts'] = parts
        self.subtasks_given[subtask_id]['res_x'] = self.res_x
        self.subtasks_given[subtask_id]['res_y'] = self.res_y
        self.subtasks_given[subtask_id]['samples'] = self.samples
        self.subtasks_given[subtask_id]['use_frames'] = self.use_frames
        self.subtasks_given[subtask_id]['all_frames'] = self.frames
        self.subtasks_given[subtask_id]['crop_window'] = (0.0, 1.0, min_y,
                                                          max_y)
        self.subtasks_given[subtask_id]['subtask_timeout'] = \
            self.header.subtask_timeout
        self.subtasks_given[subtask_id]['tmp_dir'] = self.tmp_dir
        # FIXME issue #1955

        part = self._count_part(start_task, parts)

        for frame in frames:
            frame_key = to_unicode(frame)
            state = self.frames_state[frame_key]

            state.status = TaskStatus.computing
            state.started = state.started or time.time()

            self.frames_subtasks[frame_key][part - 1] = subtask_id

        if not self.use_frames:
            self._update_task_preview()
        else:
            self._update_frame_task_preview()

        ctd = self._new_compute_task_def(subtask_id, extra_data,
                                         perf_index=perf_index)
        self.subtasks_given[subtask_id]['ctd'] = ctd
        return self.ExtraData(ctd=ctd)

    def get_parts_in_frame(self, total_tasks):
        if self.use_frames:
            if total_tasks <= len(self.frames):
                return 1
            return max(1, int(total_tasks / len(self.frames)))
        return total_tasks

    def get_subtask_y_border(self, start_task):
        parts_in_frame = self.get_parts_in_frame(self.get_total_tasks())
        if not self.use_frames:
            return get_min_max_y(start_task, parts_in_frame, self.res_y)
        elif parts_in_frame > 1:
            part = self._count_part(start_task, parts_in_frame)
            return get_min_max_y(part, parts_in_frame, self.res_y)

        return 0.0, 1.0

    def restart(self):
        super(BlenderRenderTask, self).restart()
        if self.use_frames:
            for preview in self.preview_updaters:
                preview.restart()
                self._update_frame_task_preview()
        else:
            self.preview_updater.restart()
            self._update_task_preview()

    ###################
    # CoreTask methods#
    ###################

    def query_extra_data_for_test_task(self):

        scene_file = self._get_scene_file_rel_path()

        crops = [
            {"outfilebasename": "testresult_1",
             "borders_x": [0.0, 1.0],
             "borders_y": [0.0, 1.0]}
        ]

        extra_data = {"scene_file": scene_file,
                      "resolution": BlenderRenderTask.BLENDER_MIN_BOX,
                      "use_compositing": False,
                      "samples": BlenderRenderTask.BLENDER_MIN_SAMPLE,
                      "frames": [1],
                      "output_format": "PNG",
                      "path_root": self.main_scene_dir,
                      "start_task": 1,
                      "total_tasks": 1,
                      "crops": crops,
                      "entrypoint":
                          "python3 /golem/entrypoints/render_entrypoint.py",
                      }

        hash = "{}".format(random.getrandbits(128))

        dm = DirManager(self.root_path)
        self.test_task_res_path = dm.get_task_test_dir(self.header.task_id)

        logger.debug(self.test_task_res_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        return self._new_compute_task_def(hash, extra_data, 0)

    def after_test(self, results, tmp_dir):
        return_data = dict()
        if not results or not results.get("data"):
            return return_data

        for filename in results["data"]:
            if not has_ext(filename, ".log"):
                continue

            with open(filename, "r") as f:
                log_content = f.read()

            log_analyser.make_log_analyses(log_content, return_data)

        return return_data

    def _update_preview(self, new_chunk_file_path, num_start):
        self.preview_updater.update_preview(new_chunk_file_path, num_start)

    def _update_frame_preview(self, new_chunk_file_path, frame_num, part=1,
                              final=False):
        num = self.frames.index(frame_num)
        if final:
            with handle_opencv_image_error(logger):
                img = OpenCVImgRepr.from_image_file(new_chunk_file_path)
                img.resize(int(round(self.res_x * self.scale_factor)),
                           int(round(self.res_y * self.scale_factor)))

                preview_task_file_path = self._get_preview_task_file_path(num)
                self.last_preview_path = preview_task_file_path

                img.try_adjust_type(OpenCVImgRepr.IMG_U8)

                img.save_with_extension(preview_task_file_path, PREVIEW_EXT)
                img.save_with_extension(self._get_preview_file_path(num),
                                        PREVIEW_EXT)
        else:
            self.preview_updaters[num].update_preview(new_chunk_file_path, part)
            self._update_frame_task_preview()

    def _put_image_together(self):
        output_file_name = "{}".format(self.output_file, self.output_format)
        logger.debug('_put_image_together() out: %r', output_file_name)
        self.collected_file_names = OrderedDict(
            sorted(self.collected_file_names.items()))
        collector = CustomCollector(width=self.res_x,
                                    height=self.res_y)
        for file in self.collected_file_names.values():
            collector.add_img_file(file)
        with handle_opencv_image_error(logger):
            image = collector.finalize()
            image.save_with_extension(output_file_name, self.output_format)

    @staticmethod
    def mark_part_on_preview(part, img_task, color, preview_updater):
        lower = preview_updater.get_offset(part)
        upper = preview_updater.get_offset(part + 1)
        res_x = preview_updater.preview_res_x
        for i in range(0, res_x):
            for j in range(lower, upper):
                img_task.set_pixel((i, j), color)

    def _mark_task_area(self, subtask, img_task, color, frame_index=0):
        if not self.use_frames:
            self.mark_part_on_preview(subtask['start_task'], img_task, color,
                                      self.preview_updater)
        elif self.get_total_tasks() <= len(self.frames):
            for i in range(0, int(math.floor(self.res_x * self.scale_factor))):
                for j in range(0,
                               int(math.floor(self.res_y * self.scale_factor))):
                    img_task.set_pixel((i, j), color)
        else:
            parts = int(self.get_total_tasks() / len(self.frames))
            pu = self.preview_updaters[frame_index]
            part = (subtask['start_task'] - 1) % parts + 1
            self.mark_part_on_preview(part, img_task, color, pu)

    def _put_frame_together(self, frame_num, num_start):
        directory = os.path.dirname(self.output_file)
        output_file_name = os.path.join(directory,
                                        self._get_output_name(frame_num))
        frame_key = str(frame_num)
        collected = self.frames_given[frame_key]
        collected = OrderedDict(sorted(collected.items()))
        collector = CustomCollector(width=self.res_x,
                                    height=self.res_y)
        for file in collected.values():
            collector.add_img_file(file)
        with handle_opencv_image_error(logger):
            image = collector.finalize()
            image.save_with_extension(output_file_name, self.output_format)
        self.collected_file_names[frame_num] = output_file_name
        self._update_frame_preview(output_file_name, frame_num, final=True)
        self._update_frame_task_preview()


class BlenderNVGPURenderTask(BlenderRenderTask):
    ENVIRONMENT_CLASS: Type[BlenderEnvironment] = BlenderNVGPUEnvironment


class BlenderRenderTaskBuilder(FrameRenderingTaskBuilder):
    """ Build new Blender tasks using RenderingTaskDefintions and
     BlenderRendererOptions as taskdefinition renderer options """
    TASK_CLASS: Type[BlenderRenderTask] = BlenderRenderTask

    @classmethod
    def build_dictionary(cls, definition):
        dictionary = super().build_dictionary(definition)
        dictionary['options']['compositing'] = definition.options.compositing
        dictionary['options']['samples'] = definition.options.samples
        return dictionary

    @classmethod
    def build_full_definition(cls, task_type, dictionary):
        requested_format = dictionary['options']['format']
        if requested_format not in task_type.output_formats:
            default_format = task_type.output_formats[0]
            logger.warning(
                "Unsupported output format: `%s`, "
                "replacing with default: `%s`",
                requested_format, default_format
            )
            dictionary['options']['format'] = default_format

        options = dictionary['options']

        definition = super().build_full_definition(task_type, dictionary)
        definition.options.compositing = options.get('compositing', False)
        definition.options.samples = options.get('samples', 0)

        return definition


class BlenderNVGPURenderTaskBuilder(BlenderRenderTaskBuilder):
    TASK_CLASS: Type[BlenderRenderTask] = BlenderNVGPURenderTask


class CustomCollector(RenderingTaskCollector):
    def __init__(self, width=1, height=1):
        RenderingTaskCollector.__init__(self, width, height)
        self.current_offset = 0

    def _paste_image(self, final_img, new_part, num):
        img_offset = OpenCVImgRepr.empty(self.width, self.height)
        img_offset.paste_image(new_part, 0, self.current_offset)
        new_img_res_y = new_part.get_height()
        self.current_offset += new_img_res_y
        img_offset.add(final_img)
        return img_offset


def generate_expected_offsets(parts, res_x, res_y):
    logger.debug('generate_expected_offsets(%r, %r, %r)', parts, res_x, res_y)
    # returns expected offsets for preview; the highest value is preview's
    # height
    scale_factor = BlenderTaskTypeInfo.scale_factor(res_x, res_y)
    expected_offsets = {}
    previous_end = 0
    for i in range(1, parts + 1):
        low, high = get_min_max_y(i, parts, res_y)
        low *= scale_factor * res_y
        high *= scale_factor * res_y
        height = int(math.floor(high - low))
        expected_offsets[i] = previous_end
        previous_end += height

    expected_offsets[parts + 1] = previous_end
    return expected_offsets


def get_min_max_y(part, parts_in_frame, res_y):
    if res_y % parts_in_frame == 0:
        min_y = (parts_in_frame - part) * (1.0 / parts_in_frame)
        max_y = (parts_in_frame - part + 1) * (1.0 / parts_in_frame)
    else:
        ceiling_height = int(math.ceil(res_y / parts_in_frame))
        ceiling_subtasks = parts_in_frame - \
            (ceiling_height * parts_in_frame - res_y)
        if part > ceiling_subtasks:
            min_y = (parts_in_frame - part) * (ceiling_height - 1) / res_y
            max_y = (parts_in_frame - part + 1) * (ceiling_height - 1) / res_y
        else:
            min_y = (parts_in_frame - ceiling_subtasks) * (ceiling_height - 1)
            min_y += (ceiling_subtasks - part) * ceiling_height
            min_y = min_y / res_y

            max_y = (parts_in_frame - ceiling_subtasks) * (ceiling_height - 1)
            max_y += (ceiling_subtasks - part + 1) * ceiling_height
            max_y = max_y / res_y
    return min_y, max_y
