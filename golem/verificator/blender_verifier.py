import logging
from typing import Type

import math
import os
import posixpath
import json
import numpy
from threading import Lock
from shutil import copy

from golem.core.common import get_golem_path
from golem.verificator.verifier import SubtaskVerificationState

from .rendering_verifier import FrameRenderingVerifier
from twisted.internet.defer import Deferred, gatherResults

logger = logging.getLogger("apps.blender")


# FIXME #2086
# pylint: disable=R0902
class BlenderVerifier(FrameRenderingVerifier):
    DOCKER_NAME = "golemfactory/image_metrics"
    DOCKER_TAG = '1.8'

    def __init__(self, verification_data, cropper_cls: Type,
                 docker_task_cls: Type) -> None:
        super().__init__(verification_data)
        self.lock = Lock()
        self.verified_crops_counter = 0
        self.finished = Deferred()
        self.current_results_files = None
        self.program_file = os.path.join(get_golem_path(),
                                         'docker',
                                         'blender',
                                         'images',
                                         'scripts',
                                         'runner.py')
        self.already_called = False
        self.cropper = cropper_cls()
        self.docker_task_cls = docker_task_cls
        self.metrics = dict()
        self.crops_size = ()
        self.additional_test = False
        self.default_crops_number = 3
        self.timeout = 0
        self.docker_task = None

    def _get_part_img_size(self, subtask_info):
        x, y = self._get_part_size(subtask_info)
        return 0, 0, x, y

    def _get_part_size(self, subtask_info):
        if subtask_info['use_frames'] and len(subtask_info['all_frames']) \
          >= subtask_info['total_tasks']:
            res_y = subtask_info['resolution'][1]
        else:
            res_y = int(round(numpy.float32(
                numpy.float32(subtask_info['crops'][0]['borders_y'][0])
                * numpy.float32(subtask_info['resolution'][1]))))
        return subtask_info['resolution'][0], res_y

    @staticmethod
    def _get_part_size_from_subtask_number(subtask_info):

        if subtask_info['resolution'][1] % subtask_info['total_tasks'] == 0:
            res_y = int(subtask_info['resolution'][1] / subtask_info['total_tasks'])
        else:
            # in this case task will be divided into not equal parts:
            # floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(subtask_info['resolution'][1] /
                                           subtask_info['total_tasks']))
            additional_height = ceiling_height * subtask_info['total_tasks']
            additional_pixels = additional_height - subtask_info['resolution'][1]
            ceiling_subtasks = subtask_info['total_tasks'] - additional_pixels

            if subtask_info['start_task'] > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    # pylint: disable-msg=too-many-arguments
    def _verify_with_reference(self, verification_data):
        self.current_results_files = verification_data["results"]
        self.subtask_info = verification_data["subtask_info"]
        self.verification_data = verification_data

        try:
            self.start_rendering()
        # pylint: disable=W0703
        except Exception as e:
            logger.error("Crop generation failed %r", e)
            self.finished.errback(e)

        return self.finished

    def stop(self):
        for d in self.finished_crops:
            d.cancel()
        self.can_make_verdict.cancel()
        if self.docker_task:
            self.docker_task.end_comp()

    def start_rendering(self, timeout=0):
        self.timeout = timeout

        def success(result):
            logger.debug("Success Callback")
            self.state = SubtaskVerificationState.VERIFIED
            return self.verification_completed()

        def failure(exc):
            logger.warning("Failure callback %r", exc)
            self.state = SubtaskVerificationState.WRONG_ANSWER
            return exc

        self.finished_crops = self.cropper.render_crops(
            self.resources,
            self.verification_data["subtask_info"],
            self.default_crops_number)
        self.finished.addCallback(success)
        self.finished.addErrback(failure)
        for d in self.finished_crops:
            d.addCallback(self._crop_rendered)
            d.addErrback(self._crop_render_failure)
        self.can_make_verdict = gatherResults(self.finished_crops)
        self.can_make_verdict.addCallback(self.make_verdict)
        self.can_make_verdict.addErrback(failure)

    # The verification function will generate three random crops, from results
    # only after all three will be generated, we can start verification process
    # pylint: disable=R0914
    def _crop_rendered(self, result):
        results, time_spend, verification_context, crop_number = result

        logger.info("Crop no [%r] rendered for verification. Time spent: %r.",
                    crop_number, time_spend)

        with open(self.program_file, "r") as src_file:
            src_code = src_file.read()

        work_dir = verification_context.get_crop_path(
            str(crop_number))
        if not work_dir:
            raise Exception("Crop %s not found", crop_number)

        dir_mapping = self.docker_task_cls.specify_dir_mapping(
            resources=os.path.join(work_dir, "resources"),
            temporary=os.path.dirname(work_dir),
            work=work_dir,
            output=os.path.join(work_dir, "output"),
            logs=os.path.join(work_dir, "logs"),
        )

        extra_data = self.create_extra_data(
            results, verification_context,
            crop_number, dir_mapping)

        self.docker_task = self.docker_task_cls(
            subtask_id=self.subtask_info['subtask_id'],
            docker_images=[(self.DOCKER_NAME, self.DOCKER_TAG)],
            src_code=src_code,
            extra_data=extra_data,
            dir_mapping=dir_mapping,
            timeout=self.timeout)

        def error(e):
            # is handled elsewhere
            e.trap(Exception)

        self.docker_task.run()
        self.docker_task._deferred.addErrback(error)
        was_failure = self.docker_task.error

        self.metrics[crop_number] = dict()
        for root, _, files in os.walk(str(dir_mapping.output)):
            for i, file in enumerate(files):
                with open(dir_mapping.output / file) as json_data:
                    self.metrics[crop_number][i] = json.load(json_data)

    # One failure is enough to stop verification process, although this might
    #  change in future
    def _crop_render_failure(self, error):
        logger.warning("Crop render for verification failure %r", error)
        self.call_if_not_called(False)

    def create_extra_data(self, results, verification_context, crop_number,
                          dir_mapping):
        filtered_results = list(filter(
            lambda x: not os.path.basename(x).endswith(".log"), results['data']
        ))

        dir_mapping.mkdirs()
        verification_pairs = dict()

        for result in self.current_results_files:
            copy(result, dir_mapping.resources)
            for ref_result in filtered_results:
                if os.path.basename(result) == os.path.basename(ref_result)[4:]:
                    verification_pairs[posixpath.join(
                        "/golem/resources",
                        os.path.basename(result))] = posixpath.join(
                        "/golem/work/tmp/output", os.path.basename(ref_result))

        # This is failsafe in 99% cases there will be only one result file
        # in subtask, so match it even if outfilebasename doesnt match pattern
        if not verification_pairs:
            verification_pairs[posixpath.join(
                "/golem/resources",
                os.path.basename(
                    self.current_results_files[0]))] = posixpath.join(
                "/golem/work/tmp/output", os.path.basename(filtered_results[0]))

        crop = verification_context.get_crop_with_id(str(crop_number))
        if not crop:
            raise Exception("Crop %s not found", crop_number)

        x, y = crop.get_relative_top_left()
        return dict(
            verification_files=verification_pairs,
            xres=x,
            yres=y,
        )

    def make_verdict(self, result):
        labels = []
        for crop_idx in range(len(self.metrics.keys())):
            for frame_idx, metric in self.metrics[crop_idx].items():
                labels.append(metric['Label'])
                logger.debug(
                    "METRIC: Subtask: %r crop no: %r, frame %r "
                    "scene %s \n"
                    "requestor %r\n"
                    "provider %r "
                    "metrics %s",
                    self.subtask_info['subtask_id'],
                    crop_idx,
                    frame_idx,
                    self.subtask_info['scene_file'],
                    self.subtask_info['owner'],
                    self.subtask_info['node_id'],
                    str(self.metrics))

                if metric['Label'] == "FALSE":
                    logger.warning("Subtask %r verified. Result: REJECT", self.subtask_info['subtask_id'])
                    self.call_if_not_called(False)
                    return

        if labels and all(label == "TRUE" for label in labels):
            logger.info("Subtask %r verified. Result: ACCEPT",
                        self.subtask_info['subtask_id'])
            self.call_if_not_called(True)
        else:
            logger.warning("Unexpected verification output for subtask %r,",
                           self.subtask_info['subtask_id'])
            self.call_if_not_called(False)

    def call_if_not_called(self, callback):
        with self.lock:
            if self.already_called is False:
                self.already_called = True
                if callback is True:
                    self.finished.callback(True)
                else:
                    self.finished.errback(False)
