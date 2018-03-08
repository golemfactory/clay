import glob
import logging
import math
import os
from pathlib import Path
import random
import shutil
from collections import OrderedDict
from copy import copy

from PIL import Image, ImageChops, ImageOps

import apps.lux.resources.scenefilereader as sfr
from apps.core.task import coretask
from apps.core.task.coretask import CoreTaskTypeInfo
from apps.lux.luxenvironment import LuxRenderEnvironment
from apps.lux.resources.scenefileeditor import regenerate_lux_file
from apps.lux.resources.scenefilereader import make_scene_analysis
from apps.lux.task.verifier import LuxRenderVerifier
from apps.rendering.resources.imgrepr import load_img, blend, load_as_PILImgRepr
from apps.rendering.resources.utils import handle_image_error
from apps.rendering.task import renderingtask
from apps.rendering.task import renderingtaskstate
from apps.rendering.task.renderingtask import PREVIEW_EXT, PREVIEW_Y, PREVIEW_X
from golem.core.common import timeout_to_deadline, get_golem_path, to_unicode
from golem.core.fileshelper import common_dir, find_file_with_ext, has_ext
from golem.resource import dirmanager
from golem.resource.dirmanager import DirManager
from golem.task.localcomputer import LocalComputer
from apps.core.task.coretaskstate import Options
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.lux")

MERGE_TIMEOUT = 7200

APP_DIR = os.path.join(get_golem_path(), 'apps', 'lux')


class LuxRenderDefaults(renderingtaskstate.RendererDefaults):
    def __init__(self):
        super(LuxRenderDefaults, self).__init__()
        self.output_format = "EXR"
        self.main_program_file = LuxRenderEnvironment().main_program_file
        self.min_subtasks = 1
        self.max_subtasks = 100
        self.default_subtasks = 5


class LuxRenderTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super(LuxRenderTaskTypeInfo, self).__init__(
            "LuxRender",
            renderingtaskstate.RenderingTaskDefinition,
            LuxRenderDefaults(),
            LuxRenderOptions,
            LuxRenderTaskBuilder
        )
        self.output_formats = ["EXR", "PNG", "TGA"]
        self.output_file_ext = ["lxs"]

    @classmethod
    def get_task_border(cls, subtask, definition, total_subtasks,
                        output_num=1, as_path=False):
        """ Return list of pixels that should be marked as a border of
         a given subtask
        :param SubtaskState subtask: subtask state description
        :param RenderingTaskDefinition definition: task definition
        :param int total_subtasks: total number of subtasks used in this task
        :param int output_num: number of final output files
        :param int as_path: return pixels that form a border path
        :return list: list of pixels that belong to a subtask border
        """
        preview_x = PREVIEW_X
        preview_y = PREVIEW_Y
        res_x, res_y = definition.resolution
        if res_x == 0 or res_y == 0:
            return []

        if res_x / res_y > preview_x / preview_y:
            scale_factor = preview_x / res_x
        else:
            scale_factor = preview_y / res_y
        scale_factor = min(1.0, scale_factor)

        x = int(round(res_x * scale_factor))
        y = int(round(res_y * scale_factor))

        if as_path:
            border = [(0, 0), (x - 1, 0), (x - 1, y - 1), (0, y - 1)]
        else:
            border = [(0, i) for i in range(y)]
            border += [(x - 1, i) for i in range(y)]
            border += [(i, 0) for i in range(x)]
            border += [(i, y - 1) for i in range(x)]

        return border

    @classmethod
    def get_task_num_from_pixels(cls, x, y, definition, total_subtasks,
                                 output_num=1):
        """
        Compute number of subtask that represents pixel (x, y) on preview
        :param int x: x coordinate
        :param int y: y coordiante
        :param TaskDefintion definition: task definition
        :param int total_subtasks: total number of subtasks used in this task
        :param int output_num: number of final output files
        :return int: subtask's number
        """

        return 1

    @classmethod
    def get_preview(cls, task, single=False):
        result = to_unicode(task.preview_file_path) if task else None
        return cls._preview_result(result, single=single)


class LuxRenderOptions(Options):
    def __init__(self):
        super(LuxRenderOptions, self).__init__()
        self.environment = LuxRenderEnvironment()
        self.halttime = 50
        self.haltspp = 10


class LuxTask(renderingtask.RenderingTask):
    ENVIRONMENT_CLASS = LuxRenderEnvironment
    VERIFIER_CLASS = LuxRenderVerifier

    ################
    # Task methods #
    ################

    def __init__(self, halttime, haltspp, **kwargs):
        super().__init__(**kwargs)

        self.dirManager = DirManager(self.root_path)
        self.tmp_dir = \
            self.dirManager.get_task_temporary_dir(self.header.task_id)

        self.halttime = halttime
        self.haltspp = int(math.ceil(haltspp / self.total_tasks))
        self.verification_error = False
        self.merge_timeout = MERGE_TIMEOUT

        # Is it necessary to load scene_file contents here?
        try:
            with open(self.main_scene_file) as f:
                self.scene_file_src = f.read()

        except IOError as err:
            logger.error("Wrong scene file: {}".format(err))
            self.scene_file_src = ""

        self.random_crop_window_for_verification = \
            sfr.get_random_crop_window_for_verification(self.scene_file_src)

        self.output_file, _ = os.path.splitext(self.output_file)
        self.output_format = self.output_format.lower()
        self.num_add = 0

        self.preview_exr = None
        self.reference_runs = 2

    def __getstate__(self):
        state = super(LuxTask, self).__getstate__()
        state['preview_exr'] = None
        return state

    def initialize(self, dir_manager):
        super(LuxTask, self).initialize(dir_manager)
        # FIXME With full verification

    def _write_interval_wrapper(self, halttime):
        if halttime > 0:
            write_interval = int(self.halttime / 2)
        else:
            write_interval = 60

        return write_interval

    @coretask.accepting
    def query_extra_data(self,
                         perf_index,
                         num_cores=0,
                         node_id=None,
                         node_name=None
                         ):
        start_task, end_task = self._get_next_task()
        if start_task is None or end_task is None:
            logger.error("Task already computed")
            return self.ExtraData()

        write_interval = self._write_interval_wrapper(self.halttime)

        scene_src = regenerate_lux_file(
            self.scene_file_src,
            self.res_x,
            self.res_y,
            self.halttime,
            self.haltspp,
            write_interval,
            [0, 1, 0, 1],
            self.output_format
        )
        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": start_task,
                      "end_task": end_task,
                      "total_tasks": self.total_tasks,
                      "outfilebasename": self.outfilebasename,
                      "output_format": self.output_format,
                      "scene_file_src": scene_src,
                      "scene_dir": scene_dir,
                      }

        hash = "{}".format(random.getrandbits(128))
        self.subtasks_given[hash] = copy(extra_data)
        self.subtasks_given[hash]['status'] = SubtaskStatus.starting
        self.subtasks_given[hash]['perf'] = perf_index
        self.subtasks_given[hash]['node_id'] = node_id
        self.subtasks_given[hash]['res_x'] = self.res_x
        self.subtasks_given[hash]['res_y'] = self.res_y
        self.subtasks_given[hash]['verification_crop_window'] = \
            self.random_crop_window_for_verification
        self.subtasks_given[hash]['subtask_id'] = hash
        self.subtasks_given[hash]['root_path'] = self.root_path
        self.subtasks_given[hash]['tmp_dir'] = self.tmp_dir
        self.subtasks_given[hash]['merge_ctd'] = self.__get_merge_ctd([])

        ctd = self._new_compute_task_def(hash, extra_data, None, perf_index)
        return self.ExtraData(ctd=ctd)

    # GG propably same as query_extra_data_for_merge
    def query_extra_data_for_flm_merging_test(self):
        scene_src = regenerate_lux_file(
            scene_file_src=self.scene_file_src,
            xres=self.res_x,
            yres=self.res_y,
            halttime=4,
            haltspp=1,
            writeinterval=0.5,
            crop=[0, 1, 0, 1],
            output_format=self.output_format)

        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        extra_data = {
            "path_root": self.main_scene_dir,
            "start_task": 1,
            "end_task": 1,
            "total_tasks": 1,
            "outfilebasename": "reference_merging_task",
            "output_format": self.output_format,
            "scene_file_src": scene_src,
            "scene_dir": scene_dir,
        }

        ctd = self._new_compute_task_def(
            "ReferenceMergingTask",
            extra_data,
            scene_dir,
            0)
        return ctd

    def query_extra_data_for_reference_task(self, counter):
        write_interval = \
            self._write_interval_wrapper(self.halttime)

        scene_src = regenerate_lux_file(
            scene_file_src=self.scene_file_src,
            xres=self.res_x,
            yres=self.res_y,
            halttime=self.halttime,
            haltspp=self.haltspp,
            writeinterval=write_interval,
            crop=self.random_crop_window_for_verification,
            output_format=self.output_format)

        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        extra_data = {
            "path_root": self.main_scene_dir,
            "start_task": 1,
            "end_task": 1,
            "total_tasks": 1,
            "outfilebasename": "".join(["reference_task", str(counter)]),
            "output_format": self.output_format,
            "scene_file_src": scene_src,
            "scene_dir": scene_dir,
        }

        ctd = self._new_compute_task_def(
            "".join(["ReferenceTask", str(counter)]),
            extra_data,
            scene_dir,
            0)

        return ctd

    # FIXME check if just get_test_flm is not enough
    def get_reference_data(self):
        get_test_flm = self.get_test_flm_for_verifier()
        return [get_test_flm] + self.get_reference_imgs()

    def get_reference_imgs(self):
        ref_imgs = []
        dm = self.dirManager

        for i in range(0, self.reference_runs):
            dir = os.path.join(
                dm.get_ref_data_dir(self.header.task_id, counter=i),
                dm.tmp,
                dm.output)

            f = glob.glob(os.path.join(dir, '*.' + self.output_format))

            ref_img_pil = load_as_PILImgRepr(f.pop())
            ref_imgs.append(ref_img_pil)

        return ref_imgs

    def get_test_flm_for_verifier(self):
        dm = self.dirManager
        dir = os.path.join(
            dm.get_ref_data_dir(
                self.header.task_id,
                counter='flmMergingTest'),
            dm.tmp,
            dm.output
        )

        test_flm = glob.glob(os.path.join(dir, '*.flm'))
        return test_flm.pop()

    ###################
    # CoreTask methods #
    ###################
    def query_extra_data_for_test_task(self):
        self.test_task_res_path = \
            self.dirManager.get_task_test_dir(
                self.header.task_id)

        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)

        scene_src = regenerate_lux_file(
            scene_file_src=self.scene_file_src,
            xres=10,
            yres=10,
            halttime=1,
            haltspp=0,
            writeinterval=0.5,
            crop=[0, 1, 0, 1],
            output_format="png")

        scene_dir = os.path.dirname(self._get_scene_file_rel_path())

        extra_data = {
            "path_root": self.main_scene_dir,
            "start_task": 1,
            "end_task": 1,
            "total_tasks": 1,
            "outfilebasename": "testtask",
            "output_format": "png",
            "scene_file_src": scene_src,
            "scene_dir": scene_dir,
        }

        hash = "{}".format(random.getrandbits(128))

        return self._new_compute_task_def(hash, extra_data, None, 0)

    def after_test(self, results, tmp_dir):
        FLM_NOT_FOUND_MSG = "Flm file was not found, check scene."
        return_data = dict()
        flm = find_file_with_ext(tmp_dir, [".flm"])
        if flm is None:
            return_data['warnings'] = FLM_NOT_FOUND_MSG
            logger.warning(return_data["warnings"])
        make_scene_analysis(self.scene_file_src, return_data)
        return return_data

    def query_extra_data_for_merge(self):

        scene_src = regenerate_lux_file(
            self.scene_file_src,
            self.res_x,
            self.res_y,
            10,
            0,
            5,
            [0, 1, 0, 1],
            self.output_format
        )

        scene_dir = os.path.dirname(self._get_scene_file_rel_path())
        extra_data = {"path_root": self.main_scene_dir,
                      "start_task": 0,
                      "end_task": 0,
                      "total_tasks": 0,
                      "outfilebasename": self.outfilebasename,
                      "output_format": self.output_format,
                      "scene_file_src": scene_src,
                      "scene_dir": scene_dir}

        return self._new_compute_task_def(
            "FINALTASK",
            extra_data,
            scene_dir,
            0
        )

    def query_extra_data_for_final_flm(self):
        files = [
            os.path.basename(x) for x in self.collected_file_names.values()
        ]
        return self.__get_merge_ctd(files)

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        num_start = self.subtasks_given[subtask_id]['start_task']
        for tr_file in result_files:
            if has_ext(tr_file, ".flm"):
                self.collected_file_names[num_start] = tr_file
                self.counting_nodes[
                    self.subtasks_given[subtask_id]['node_id']
                ].accept()
                self.num_tasks_received += 1
            elif not has_ext(tr_file, '.log'):
                self.subtasks_given[subtask_id]['preview_file'] = tr_file
                self._update_preview(tr_file, num_start)

        if self.num_tasks_received == self.total_tasks:
            self.__generate_final_flm()

    def __get_merge_ctd(self, files):
        script_file = dirmanager.find_task_script(
            APP_DIR,
            "docker_luxmerge.py"
        )

        if script_file is None:
            logger.error("Cannot find merger script")
            return

        with open(script_file) as f:
            src_code = f.read()

        extra_data = {'output_flm': Path(self.output_file).as_posix(),
                      'flm_files': files}
        ctd = self._new_compute_task_def(hash=self.header.task_id,
                                         extra_data=extra_data,
                                         perf_index=0)

        # different than ordinary subtask code and timeout
        ctd['src_code'] = src_code
        ctd['deadline'] = timeout_to_deadline(self.merge_timeout)
        return ctd

    def short_extra_data_repr(self, extra_data):
        if "output_flm" in extra_data:
            return "output flm: {output_flm}, " \
                   "flm files: {flm_files}, ".format(**extra_data)
        return "start_task: {start_task}, " \
               "outfilebasename: {outfilebasename}, " \
               "scene_file_src: {scene_file_src}".format(**extra_data)

    def _update_preview(self, new_chunk_file_path, num_start):
        self.num_add += 1
        if has_ext(new_chunk_file_path, ".exr"):
            self._update_preview_from_exr(new_chunk_file_path)
        else:
            self.__update_preview_from_pil_file(new_chunk_file_path)

    def _update_task_preview(self):
        pass

    @renderingtask.RenderingTask.handle_key_error
    def _remove_from_preview(self, subtask_id):
        preview_files = []
        for sub_id, task in list(self.subtasks_given.items()):
            if sub_id != subtask_id \
                    and task['status'] == 'Finished' \
                    and 'preview_file' in task:
                preview_files.append(task['preview_file'])

        self.preview_file_path = None
        self.num_add = 0

        for f in preview_files:
            self._update_preview(f, None)
        if len(preview_files) == 0:
            with handle_image_error(logger), \
                    self._open_preview():
                pass  # just create the image

    @handle_image_error(logger)
    def __update_preview_from_pil_file(self, new_chunk_file_path):
        with Image.open(new_chunk_file_path) as img, \
                img.resize((int(round(self.scale_factor * self.res_x)),
                            int(round(self.scale_factor * self.res_y))),
                           resample=Image.BILINEAR) as scaled, \
                self._open_preview() as img_current, \
                ImageChops.blend(img_current,
                                 scaled, 1.0 / self.num_add) as img_blended:
            img_blended.save(self.preview_file_path, PREVIEW_EXT)

    def _update_preview_from_exr(self, new_chunk_file):
        if self.preview_exr is None:
            self.preview_exr = load_img(new_chunk_file)
        else:
            new_preview_exr = load_img(new_chunk_file)
            if new_preview_exr is not None:
                self.preview_exr = blend(
                    self.preview_exr,
                    new_preview_exr,
                    1.0 / self.num_add
                )

        if self.preview_exr is None:
            return

        # self._open_preview() is just to properly initalize some variables
        with handle_image_error(logger), \
                self._open_preview(), \
                self.preview_exr.to_pil() as img, \
                ImageOps.fit(
                    img,
                    (
                        int(round(self.scale_factor * self.res_x)),
                        int(round(self.scale_factor * self.res_y))
                    ),
                    method=Image.BILINEAR
                ) as scaled:
            scaled.save(self.preview_file_path, PREVIEW_EXT)

    def create_reference_data_for_task_validation(self):
        for i in range(0, self.reference_runs):
            path = \
                self.dirManager.get_ref_data_dir(self.header.task_id, counter=i)

            computer = LocalComputer(
                root_path=path,
                success_callback=self.__final_img_ready,
                error_callback=self.__final_img_error,
                compute_task_def=self.query_extra_data_for_reference_task(
                    counter=i),
                resources=self.task_resources
            )
            computer.run()
            computer.tt.join()

        path = self.dirManager.get_ref_data_dir(
            self.header.task_id,
            counter='flmMergingTest'
        )

        computer = LocalComputer(
            root_path=path,
            success_callback=self.__final_img_ready,
            error_callback=self.__final_img_error,
            get_compute_task_def=self.query_extra_data_for_flm_merging_test,
            resources=self.task_resources
        )
        computer.run()
        computer.tt.join()

    def __generate_final_file(self, flm):
        computer = LocalComputer(
            root_path=self.root_path,
            success_callback=self.__final_img_ready,
            error_callback=self.__final_img_error,
            get_compute_task_def=self.query_extra_data_for_merge,
            resources=self.task_resources,
            additional_resources=[flm]
        )
        computer.run()
        computer.tt.join()

    def __final_img_ready(self, results, time_spent):
        commonprefix = common_dir(results['data'])
        img = find_file_with_ext(commonprefix, ["." + self.output_format])
        if img is None:
            # TODO Maybe we should try again?
            logger.error("No final file generated...")
        else:
            try:
                shutil.copy(img, self.output_file + "." + self.output_format)
            except (IOError, OSError) as err:
                logger.warning("Couldn't rename and copy img file. %s", err)

        self.notify_update_task()

    def __final_img_error(self, error):
        logger.error("Cannot generate final image: {}".format(error))
        # TODO What should we do in this situation?

    def __generate_final_flm(self):
        self.collected_file_names = OrderedDict(
            sorted(self.collected_file_names.items())
        )
        computer = LocalComputer(
            root_path=self.root_path,
            success_callback=self.__final_flm_ready,
            error_callback=self.__final_flm_failure,
            get_compute_task_def=self.query_extra_data_for_final_flm,
            resources=[],
            additional_resources=list(self.collected_file_names.values())
        )
        computer.run()
        computer.tt.join()

    def __final_flm_ready(self, results, time_spent):
        commonprefix = common_dir(results['data'])
        flm = find_file_with_ext(commonprefix, [".flm"])
        if flm is None:
            self.__final_flm_failure("No flm file created")
            return
        shutil.copy(flm, os.path.dirname(self.output_file))
        new_flm = os.path.join(
            os.path.dirname(self.output_file),
            os.path.basename(flm)
        )
        self.__generate_final_file(new_flm)

    def __final_flm_failure(self, error):
        logger.error("Cannot generate final flm: {}".format(error))
        # TODO What should we do in this sitution?

    # TODO Implement with proper verifier
    def __generate_final_flm_advanced_verification(self):
        # the file containing result of task test
        test_result_flm = self.__get_test_flm()

        new_flm = self.output_file + ".flm"
        shutil.copy(test_result_flm, new_flm)
        logger.debug("Copying " + test_result_flm + " to " + new_flm)
        self.__generate_final_file(new_flm)

    def __get_test_flm(self):
        return os.path.join(self.tmp_dir, "test_result.flm")


class LuxRenderTaskBuilder(renderingtask.RenderingTaskBuilder):
    TASK_CLASS = LuxTask
    DEFAULTS = LuxRenderDefaults

    def get_task_kwargs(self, **kwargs):
        kwargs = super().get_task_kwargs(**kwargs)
        kwargs['halttime'] = self.task_definition.options.halttime
        kwargs['haltspp'] = self.task_definition.options.haltspp
        return kwargs

    @classmethod
    def build_dictionary(cls, definition):
        dictionary = super().build_dictionary(definition)
        dictionary['options']['haltspp'] = definition.options.haltspp
        return dictionary

    @classmethod
    def build_full_definition(cls, task_type, dictionary):
        options = dictionary['options']
        definition = super().build_full_definition(task_type, dictionary)
        definition.options.haltspp = options.get('haltspp',
                                                 definition.options.haltspp)
        return definition
