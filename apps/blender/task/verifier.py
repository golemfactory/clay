import logging
import math
import os
import posixpath
import json
from collections import Callable
from threading import Lock
from shutil import copy

from apps.rendering.task.verifier import FrameRenderingVerifier
from apps.blender.resources.imgcompare import check_size
from golem.docker.job import DockerJob
from golem.docker.image import DockerImage
from golem.resource.dirmanager import find_task_script
from golem.core.common import get_golem_path
from apps.blender.task.blendercropper import BlenderCropper
from golem.verification.verifier import SubtaskVerificationState

logger = logging.getLogger("apps.blender")


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
        self.cropper = BlenderCropper()
        self.metrics = dict()
        self.subtask_info = None
        self.crops_size = ()

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
        self.subtask_info = subtask_info

        try:
            def success():
                self.success = success_
                self.failure = failure
                if not self._check_computer():
                    logger.error(self.message)
                    failure()
                    self.crops_size = self.cropper.render_crops(
                        self.computer,
                        self.resources,
                        self._crop_rendered,
                        self._crop_render_failure,
                        subtask_info)

            super()._verify_imgs(
                subtask_info,
                results,
                reference_data,
                resources, success, failure)
        except Exception as e:
            logger.error("Crop generation failed %r", e)
            failure()

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
        resource_dir = os.path.join(work_dir, "resources")

        if not os.path.exists(resource_dir):
                os.mkdir(resource_dir)
        if not os.path.exists(logs_dir):
            os.mkdir(logs_dir)
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

        copy(self.current_results_file, resource_dir)

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
                       resource_dir, work_dir, output_dir,
                       host_config=None) as job:
            job.start()
            was_failure = job.wait()
            self.metrics[verification_context.crop_id] = json.loads(
                os.path.join(
                    output_dir,
                    "result.txt"))
            stdout_file = os.path.join(logs_dir, "stdout.log")
            stderr_file = os.path.join(logs_dir, "stderr.log")
            job.dump_logs(stdout_file, stderr_file)

        with self.lock:
            if was_failure == -1:
                self.wasFailure = True
                self.failure()
            else:
                self.verified_crops_counter += 1
                if self.verified_crops_counter == 3:
                    self.make_verdict()

    # One failure is enough to stop verification process, although this might
    #  change in future
    def _crop_render_failure(self, error):
        logger.warning("Crop for verification render failure %r", error)
        with self.lock:
            self.wasFailure = True
            self.failure()

    def make_verdict(self):
        avg_corr = 0
        avg_ssim = 0
        for key, metric in self.metrics:
            avg_corr += metric['imgCorr']
            avg_ssim += metric['SSIM_normal']
        avg_corr /= 3
        avg_ssim /= 3

        # These are empirically measured values by CP and GG
        w_corr = 0.7
        w_ssim = 0.8

        w_corr_min = 0.6
        w_ssim_min = 0.6

        if avg_ssim > w_ssim and avg_corr > w_corr:
            self.success()
        elif avg_ssim < w_ssim and avg_corr < w_corr:
            self.failure()
        elif avg_ssim > w_ssim_min and avg_corr > w_corr_min:
            self.verified_crops_counter = 0
            self.cropper.render_crops(self.computer, self.resources,
                                      self._crop_rendered,
                                      self._crop_render_failure,
                                      self.subtask_info,
                                      (self.crops_size[0] + 0.01,
                                       self.crops_size[1] + 0.01))
        else:
            self.failure()


