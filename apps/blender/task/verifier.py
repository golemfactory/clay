from copy import deepcopy
import logging
import math
import os
import posixpath
from collections import Callable
from threading import Lock
from functools import partial

from apps.rendering.task.verifier import FrameRenderingVerifier
from apps.blender.resources.cropgenerator import generate_crops
from apps.blender.resources.imgcompare import check_size
from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.docker.job import DockerJob
from golem.docker.image import DockerImage
from golem.resource.dirmanager import find_task_script
from golem.core.common import get_golem_path
from golem.core.common import timeout_to_deadline

logger = logging.getLogger("apps.blender")

NUM_CROPS = 3


# pylint: disable=R0903
class VerificationContext:
    def __init__(self, crops_position, crop_id, crops_path):
        self.crop_id = crop_id
        self.crop_path = os.path.join(crops_path, str(crop_id))
        self.crop_position_x = crops_position[crop_id][0]
        self.crop_position_y = crops_position[crop_id][1]


# pylint: disable=R0902
class BlenderVerifier(FrameRenderingVerifier):

    DOCKER_NAME = "golemfactory/image_metrics"
    DOCKER_TAG = '1.1'

    def __init__(self, callback: Callable):
        super().__init__(callback)
        self.lock = Lock()
        self.verified_crops_counter = 0
        self.success = None
        self.failure = None
        self.crops_path = None
        self.current_results_file = None
        self.program_file = find_task_script(os.path.join(
            get_golem_path(), 'apps', 'rendering'), 'runner.py')
        self.wasFailure = False

    def _get_part_img_size(self, subtask_info):
        x, y = self._get_part_size(subtask_info)
        return 0, 0, x, y

    def _get_part_size(self, subtask_info):
        total_tasks = subtask_info['total_tasks']
        if not subtask_info['use_frames']:
            res_y = self._get_part_size_from_subtask_number(subtask_info)
        elif len(subtask_info['all_frames']) >= total_tasks:
            res_y = subtask_info['res_y']
        else:
            parts = int(total_tasks / len(subtask_info['all_frames']))
            res_y = int(math.floor(subtask_info['res_y'] / parts))
        return subtask_info['res_x'], res_y

    def _get_part_size_from_subtask_number(self, subtask_info):

        if subtask_info['res_y'] % subtask_info['total_tasks'] == 0:
            res_y = int(subtask_info['res_y'] / subtask_info['total_tasks'])
        else:
            # in this case task will be divided into not equal parts:
            # floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(subtask_info['res_y'] /
                                           subtask_info['total_tasks']))
            additional_height = ceiling_height * subtask_info['total_tasks']
            additional_pixels = additional_height - subtask_info['res_y']
            ceiling_subtasks = subtask_info['total_tasks'] - additional_pixels

            if subtask_info['start_task'] > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    def _check_size(self, file_, res_x, res_y):
        return check_size(file_, res_x, res_y)

    # pylint: disable-msg=too-many-arguments
    def _verify_imgs(self, subtask_info, results, reference_data, resources,
                     success_=None, failure=None):
        self.crops_path = os.path.join(subtask_info['tmp_dir'],
                                       subtask_info['subtask_id'])
        self.current_results_file = results[0]

        try:
            def success():
                self.success = success_
                self.failure = failure
                self._render_crops(subtask_info)

            super()._verify_imgs(
                subtask_info,
                results,
                reference_data,
                resources, success, failure)
        except Exception as e:
            logger.error("Crop generation failed %r", e)
            failure()

    def _render_crops(self, subtask_info,
                      num_crops=NUM_CROPS, crop_size=None):
        # pylint: disable=unused-argument
        if not self._check_computer():
            return False

        crops_info = generate_crops((subtask_info['res_x'],
                                     subtask_info['res_y']),
                                    subtask_info['crop_window'], num_crops,
                                    crop_size)
        for num in range(num_crops):
            verify_ctx = VerificationContext(crops_info[1], num,
                                             self.crops_path)
            self._render_one_crop(crops_info[0][num], subtask_info, verify_ctx)
        return True

    def _render_one_crop(self, crop, subtask_info, verify_ctx):
        minx, maxx, miny, maxy = crop

        script_src = generate_blender_crop_file(
            resolution=(subtask_info['res_x'], subtask_info['res_y']),
            borders_x=(minx, maxx),
            borders_y=(miny, maxy),
            use_compositing=False
        )
        ctd = self._generate_ctd(subtask_info, script_src)
        # FIXME issue #1955
        self.computer.start_computation(
            root_path=verify_ctx.crop_path,
            success_callback=partial(self._crop_rendered,
                                     verification_context=verify_ctx),
            error_callback=self._crop_render_failure,
            compute_task_def=ctd,
            resources=self.resources,
            additional_resources=[]
        )

    @staticmethod
    def _generate_ctd(subtask_info, script_src):
        ctd = deepcopy(subtask_info['ctd'])

        ctd['extra_data']['outfilebasename'] = \
            "ref_" + subtask_info['outfilebasename']
        ctd['extra_data']['script_src'] = script_src
        ctd['deadline'] = timeout_to_deadline(subtask_info['subtask_timeout'])
        return ctd

    #  The verification function will generate three random crops, from results
    #  only after all three will be generated, we can start verification process
    # pylint: disable=R0914
    def _crop_rendered(self, results, time_spend, verification_context):
        logger.info("Crop for verification rendered. Time spent: %r, "
                    "results: %r", time_spend, results)

        filtered_results = list(filter(lambda x:
                                       not os.path.basename(x).endswith(
                                           ".log"), results['data']))

        with self.lock:
            if self.wasFailure:
                return

        work_dir = verification_context.crop_path
        di = DockerImage(BlenderVerifier.DOCKER_NAME,
                         tag=BlenderVerifier.DOCKER_TAG)

        output_dir = os.path.join(work_dir, "output")
        logs_dir = os.path.join(work_dir, "logs")

        if not os.path.exists(logs_dir):
            os.mkdir(logs_dir)
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

        resource_path = os.path.dirname(self.current_results_file)

        params = dict()

        params['cropped_img_path'] = posixpath.join(
            "/golem/work/tmp/output",
            os.path.basename(filtered_results[0]))
        params['rendered_scene_path'] = posixpath.join(
            "/golem/resources",
            os.path.basename(self.current_results_file))

        params['xres'] = verification_context.crop_position_x
        params['yres'] = verification_context.crop_position_y

        # pylint: disable=W0703
        try:
            with open(self.program_file, "r") as src_file:
                src_code = src_file.read()
        except Exception as err:
            logger.warning("Wrong main program file: %r", err)
            src_code = ""

        with DockerJob(di, src_code, params,
                       resource_path, work_dir, output_dir,
                       host_config=None) as job:
            job.start()
            was_failure = job.wait()
            stdout_file = os.path.join(logs_dir, "stdout.log")
            stderr_file = os.path.join(logs_dir, "stderr.log")
            job.dump_logs(stdout_file, stderr_file)

        with self.lock:
            if was_failure == -1:
                self.wasFailure = True
                self.failure()
            else:
                self.verified_crops_counter += 1
                if self.verified_crops_counter == NUM_CROPS:
                    self.success()

    # One failure is enough to stop verification process, although this might
    #  change in future
    def _crop_render_failure(self, error):
        logger.warning("Crop for verification render failure %r", error)
        with self.lock:
            self.wasFailure = True
            self.failure()
