import logging
import os
import random
import shutil

from PIL import Image, ImageChops
from collections import OrderedDict

from golem.task.taskstate import SubtaskStatus

from gnr.renderingtaskstate import RendererDefaults, RendererInfo
from gnr.task.gnrtask import GNROptions, check_subtask_id_wrapper
from gnr.task.framerenderingtask import FrameRenderingTask, FrameRenderingTaskBuilder, get_task_boarder, \
    get_task_num_from_pixels
from gnr.renderingdirmanager import get_test_task_path, find_task_script
from gnr.task.renderingtaskcollector import RenderingTaskCollector
from gnr.renderingenvironment import VRayEnvironment




logger = logging.getLogger(__name__)


class VrayDefaults(RendererDefaults):
    def __init__(self):
        RendererDefaults.__init__(self)
        self.output_format = "EXR"
        self.main_program_file = find_task_script('vraytask.py')
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 6


def build_vray_renderer_info(dialog, customizer):
    defaults = VrayDefaults()

    renderer = RendererInfo("VRay Standalone", defaults, VRayTaskBuilder, dialog, customizer, VRayRendererOptions)
    renderer.output_formats = ["BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF"]
    renderer.scene_file_ext = ["vrscene"]
    renderer.get_task_num_from_pixels = get_task_num_from_pixels
    renderer.get_task_boarder = get_task_boarder

    return renderer


class VRayRendererOptions(GNROptions):
    def __init__(self):
        self.environment = VRayEnvironment()
        self.rt_engine = 0
        self.rt_engine_values = {0: 'No engine', 1: 'CPU', 3: 'OpenGL', 5: 'CUDA'}
        self.use_frames = False
        self.frames = range(1, 11)


class VRayTaskBuilder(FrameRenderingTaskBuilder):
    def build(self):
        main_scene_dir = os.path.dirname(self.task_definition.main_scene_file)

        vray_task = VRayTask(self.node_name,
                             self.task_definition.task_id,
                             main_scene_dir,
                             self.task_definition.main_scene_file,
                             self.task_definition.main_program_file,
                             self._calculate_total(VrayDefaults(), self.task_definition),
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
                             self.task_definition.renderer_options.rt_engine,
                             self.task_definition.renderer_options.use_frames,
                             self.task_definition.renderer_options.frames
                             )
        return self._set_verification_options(vray_task)


class VRayTask(FrameRenderingTask):

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
                 rt_engine,
                 use_frames,
                 frames,
                 return_address="",
                 return_port=0,
                 key_id=""):

        FrameRenderingTask.__init__(self, node_name, task_id, return_address, return_port, key_id,
                                    VRayEnvironment.get_id(), full_task_timeout, subtask_timeout,
                                    main_program_file, task_resources, main_scene_dir, main_scene_file,
                                    num_subtasks, res_x, res_y, outfilebasename, output_file, output_format,
                                    root_path, estimated_memory, use_frames, frames)

        self.rt_engine = rt_engine
        self.collected_alpha_files = {}

        self.framesParts = {}
        self.framesAlphaParts = {}

    def query_extra_data(self, perf_index, num_cores=0, node_id=None, node_name=None):

        if not self._accept_client(node_id):
            logger.warning(" Client {} banned from this task ".format(node_id))
            return None

        start_task, end_task = self._get_next_task()

        working_directory = self._get_working_directory()
        scene_file = self._get_scene_file_rel_path()

        if self.use_frames:
            frames, parts = self._choose_frames(start_task)
        else:
            frames = []
            parts = 1

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
                      "start_part": self.get_part_num(start_task),
                      "end_part": self.get_part_num(end_task),
                      "h_task": self.total_tasks,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "width": self.res_x,
                      "height": self.res_y,
                      "rt_engine": self.rt_engine,
                      "num_threads": num_cores,
                      "use_frames": self.use_frames,
                      "frames": frames,
                      "parts": parts
                      }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[hash] = extra_data
        self.subtasks_given[hash]['status'] = SubtaskStatus.starting
        self.subtasks_given[hash]['perf'] = perf_index
        self.subtasks_given[hash]['node_id'] = node_id

        for frame in frames:
            if self.use_frames and frame not in self.framesParts:
                self.framesParts[frame] = {}
                self.framesAlphaParts[frame] = {}

        if not self.use_frames:
            self._update_task_preview()
        else:
            self._update_frame_task_preview()

        return self._new_compute_task_def(hash, extra_data, working_directory, perf_index)

    @check_subtask_id_wrapper
    def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):

        if not self.should_accept(subtask_id):
            return

        tmp_dir = dir_manager.get_task_temporary_dir(self.header.task_id, create=False)
        self.tmp_dir = tmp_dir

        self.interpret_task_results(subtask_id, task_result, result_type, tmp_dir)
        tr_files = self.results[subtask_id]

        if len(tr_files) > 0:
            num_start = self.subtasks_given[subtask_id]['start_task']
            parts = self.subtasks_given[subtask_id]['parts']
            num_end = self.subtasks_given[subtask_id]['end_task']
            self.subtasks_given[subtask_id]['status'] = SubtaskStatus.finished

            if self.use_frames and self.total_tasks <= len(self.frames):
                if len(task_result) < len(self.subtasks_given[subtask_id]['frames']):
                    self._mark_subtask_failed(subtask_id)
                    return

            if not self._verify_imgs(subtask_id, tr_files):
                self._mark_subtask_failed(subtask_id)
                if not self.use_frames:
                    self._update_task_preview()
                else:
                    self._update_frame_task_preview()
                return

            self.counting_nodes[self.subtasks_given[subtask_id]['node_id']] = 1

            if not self.use_frames:
                for tr_file in tr_files:
                    self.__collect_image_part(num_start, tr_file)
            elif self.total_tasks < len(self.frames):
                for tr_file in tr_files:
                    self.__collect_frame_file(tr_file)
                self.__collect_frames(self.subtasks_given[subtask_id]['frames'], tmp_dir)
            else:
                for tr_file in tr_files:
                    self.__collect_frame_part(num_start, tr_file, parts, tmp_dir)

            self.num_tasks_received += num_end - num_start + 1
        else:
            self._mark_subtask_failed(subtask_id)
            if not self.use_frames:
                self._update_task_preview()
            else:
                self._update_frame_task_preview()

        if self.num_tasks_received == self.total_tasks:
            if self.use_frames:
                self.__copy_frames()
            else:
                output_file_name = u"{}".format(self.output_file, self.output_format)
                self.__put_image_together(output_file_name)

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

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 0,
                      "end_task": 1,
                      "start_part": 0,
                      "end_part": 1,
                      "h_task": self.total_tasks,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "scene_file": scene_file,
                      "width": 1,
                      "height": 1,
                      "rt_engine": self.rt_engine,
                      "num_threads": 0,
                      "use_frames": self.use_frames,
                      "frames": frames,
                      "parts": 1
                      }

        hash = "{}".format(random.getrandbits(128))

        self.test_task_res_path = get_test_task_path(self.root_path)
        logger.debug(self.test_task_res_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        return self._new_compute_task_def(hash, extra_data, working_directory, 0)

    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        msg = []
        msg.append(" scene file: {} ".format(l["scene_file"]))
        msg.append("total tasks: {}".format(l["total_tasks"]))
        msg.append("start task: {}".format(l["start_task"]))
        msg.append("end task: {}".format(l["end_task"]))
        msg.append("outfile basename: {}".format(l["outfilebasename"]))
        msg.append("size: {}x{}".format(l["width"], l["height"]))
        msg.append("rt_engine: {}".format(l["rt_engine"]))
        if l["use_frames"]:
            msg.append("frames: {}".format(l["frames"]))
        return "\n".join(msg)

    def _paste_new_chunk(self, img_chunk, preview_file_path, chunk_num, all_chunks_num):
        if os.path.exists(preview_file_path):
            img = Image.open(preview_file_path)
            img = ImageChops.add(img, img_chunk)
            return img
        else:
            return img_chunk

    @check_subtask_id_wrapper
    def _change_scope(self, subtask_id, start_box, tr_file):
        extra_data, _ = FrameRenderingTask._change_scope(self, subtask_id, start_box, tr_file)
        extra_data['is_alpha'] = self.__is_alpha_file(tr_file)
        extra_data['generateStartBox'] = True
        if start_box[0] == 0:
            new_start_box_x = 0
            new_box_x = self.verification_options.box_size[0] + 1
        else:
            new_start_box_x = start_box[0] - 1
            new_box_x = self.verification_options.box_size[0] + 2
        if start_box[1] == 0:
            new_start_box_y = 0
            new_box_y = self.verification_options.box_size[1] + 1
        else:
            new_start_box_y = start_box[1] - 1
            new_box_y = self.verification_options.box_size[1] + 2
        extra_data['start_box'] = (new_start_box_x, new_start_box_y)
        extra_data['box'] = (new_box_x, new_box_y)
        if self.use_frames:
            extra_data['frames'] = [self.__get_frame_num_from_output_file(tr_file)]
            extra_data['parts'] = extra_data['total_tasks']

        return extra_data, start_box

    def _run_task(self, src_code, scope):
        exec src_code in scope
        tr_files = self.load_task_results(scope['output']['data'], scope['output']['result_type'], self.tmp_dir)
        if scope['is_alpha']:
            for tr_file in tr_files:
                if self.__is_alpha_file(tr_file):
                    return tr_file
        else:
            for tr_file in tr_files:
                if not self.__is_alpha_file(tr_file):
                    return tr_file
        if len(tr_files) > 0:
            return tr_files[0]
        else:
            return None

    def __get_frame_num_from_output_file(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.find(self.outfilebasename)
        if self.__is_alpha_file(file_name):
            idx_alpha = file_name.find("Alpha")
            if self.use_frames and self.total_tasks == len(self.frames):
                return int(file_name[idx + len(self.outfilebasename) + 1: idx_alpha - 1])
            elif self.use_frames and self.total_tasks < len(self.frames):
                return int(file_name[idx_alpha + len("Alpha") + 1:])
            else:
                return int(file_name.split(".")[-3])

        else:
            if self.use_frames and self.total_tasks > len(self.frames):
                suf = file_name[idx + len(self.outfilebasename) + 1:]
                idx_dot = suf.find(".")
                return int(suf[idx_dot + 1:])
            else:
                return int(file_name[idx + len(self.outfilebasename) + 1:])

    def __use_alpha(self):
        unsupported_formats = ['BMP', 'PCX', 'PDF']
        if self.output_format in unsupported_formats:
            return False
        return True

    def __is_alpha_file(self, file_name):
        return file_name.find('Alpha') != -1

    def __put_image_together(self, output_file_name):
        collector = RenderingTaskCollector()

        if not self._use_outer_task_collector():
            for file in self.collected_file_names.values():
                collector.add_img_file(file)
            for file in self.collected_alpha_files.values():
                collector.acceptAlphaFile(file)
            collector.finalize().save(output_file_name, self.output_format)
        #            if not self.use_frames:
        #                self.preview_file_path = output_file_name
        else:
            self.collected_file_names = OrderedDict(sorted(self.collected_file_names.items()))
            self.collected_alpha_files = OrderedDict(sorted(self.collected_alpha_files.items()))
            files = self.collected_file_names.values() + self.collected_alpha_files.values()
            self._put_collected_files_together(output_file_name, files, "add")

    def __collect_image_part(self, num_start, tr_file):
        if self.__is_alpha_file(tr_file):
            self.collected_alpha_files[num_start] = tr_file
        else:
            self.collected_file_names[num_start] = tr_file
            self._update_preview(tr_file)
            self._update_task_preview()

    def __collect_frames(self, frames, tmp_dir):
        for frame in frames:
            self.__put_frame_together(tmp_dir, frame, frame)

    def __collect_frame_file(self, tr_file):
        frame_num = self.__get_frame_number_from_name(tr_file)
        if frame_num is None:
            return
        if self.__is_alpha_file(tr_file):
            self.framesAlphaParts[frame_num][1] = tr_file
        else:
            self.framesParts[frame_num][1] = tr_file

    def __collect_frame_part(self, num_start, tr_file, parts, tmp_dir):
        frame_num = self.frames[(num_start - 1) / parts]
        part = ((num_start - 1) % parts) + 1

        if self.__is_alpha_file(tr_file):
            self.framesAlphaParts[frame_num][part] = tr_file
        else:
            self.framesParts[frame_num][part] = tr_file

        self._update_frame_preview(tr_file, frame_num, part)

        if len(self.framesParts[frame_num]) == parts:
            self.__put_frame_together(tmp_dir, frame_num, num_start)

    def __copy_frames(self):
        output_dir = os.path.dirname(self.output_file)
        for file in self.collected_file_names.values():
            shutil.copy(file, os.path.join(output_dir, os.path.basename(file)))

    def __put_frame_together(self, tmp_dir, frame_num, num_start):
        output_file_name = os.path.join(tmp_dir, self.__get_output_name(frame_num))
        if self._use_outer_task_collector():
            collected = self.framesParts[frame_num]
            collected = OrderedDict(sorted(collected.items()))
            collected_alphas = self.framesAlphaParts[frame_num]
            collected_alphas = OrderedDict(sorted(collected_alphas.items()))
            files = collected.values() + collected_alphas.values()
            self._put_collected_files_together(output_file_name, files, "add")
        else:
            collector = RenderingTaskCollector()
            for part in self.framesParts[frame_num].values():
                collector.add_img_file(part)
            for part in self.framesAlphaParts[frame_num].values():
                collector.add_alpha_file(part)
            collector.finalize().save(output_file_name, self.output_format)
        self.collected_file_names[num_start] = output_file_name
        self._update_frame_preview(output_file_name, frame_num, final=True)

    def __get_frame_number_from_name(self, frame_name):
        try:
            frame_name, ext = os.path.splitext(frame_name)
            num = int(frame_name.split(".")[-1].lstrip("0"))
            return num
        except (ValueError, TypeError, IndexError) as err:
            logger.warning("Wrong result name: {}; {} ", frame_name, str(err))
            return None

    def __get_output_name(self, frame_num):
        num = str(frame_num)
        return "{}{}.{}".format(self.outfilebasename, num.zfill(4), self.output_format)

