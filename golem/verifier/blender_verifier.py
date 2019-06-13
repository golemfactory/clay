import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Type

import numpy
from twisted.internet.defer import Deferred

from golem.verifier.subtask_verification_state import SubtaskVerificationState
from golem.verifier.rendering_verifier import FrameRenderingVerifier


logger = logging.getLogger(__name__)


# FIXME #2086
# pylint: disable=R0902
class BlenderVerifier(FrameRenderingVerifier):
    DOCKER_NAME = 'golemfactory/blender_verifier'
    DOCKER_TAG = '1.4'

    def __init__(self, verification_data, docker_task_cls: Type) -> None:
        super().__init__(verification_data)
        self.finished = Deferred()
        self.docker_task_cls = docker_task_cls
        self.timeout = 0
        self.docker_task = None

    def start_verification(self) -> Deferred:
        self.time_started = datetime.utcnow()
        logger.info(
            f'Start verification in BlenderVerifier. '
            f'Subtask_id: {self.subtask_info["subtask_id"]}.')
        try:
            self.start_rendering()
        # pylint: disable=W0703
        except Exception as exception:
            logger.error('Verification failed %r', exception)
            self.finished.errback(exception)

        return self.finished

    @staticmethod
    def _get_part_size(subtask_info):
        resolution_x = subtask_info['resolution'][0]
        resolution_y = subtask_info['resolution'][1]

        if subtask_info['use_frames'] and len(subtask_info['all_frames']) \
                >= subtask_info['total_tasks']:
            crop_resolution_y = resolution_y
        else:
            border_y_min = numpy.float32(subtask_info['crops'][0]['borders_y'][0])  # noqa pylint: disable=line-too-long
            border_y_max = numpy.float32(subtask_info['crops'][0]['borders_y'][1])  # noqa pylint: disable=line-too-long

            crop_resolution_y = int(round(numpy.float32(
                resolution_y * border_y_max -
                resolution_y * border_y_min
            )))
        return resolution_x, crop_resolution_y

    def stop(self):
        if self.docker_task:
            self.docker_task.end_comp()

    def start_rendering(self, timeout=0) -> None:
        self.timeout = timeout
        subtask_id = self.subtask_info['subtask_id']

        def success(_result):
            logger.info(
                f'Verification completed. '
                f'Subtask_id: {subtask_id}. Verification verdict: positive. ')
            self.state = SubtaskVerificationState.VERIFIED
            return self.verification_completed()

        def failure(exception):
            logger.info(
                f'Verification completed. '
                f'Subtask_id: {subtask_id}. Verification verdict: negative. ')
            self.state = SubtaskVerificationState.WRONG_ANSWER
            return exception

        self.finished.addCallback(success)
        self.finished.addErrback(failure)

        root_dir = Path(os.path.dirname(
            self.results[0])).parent
        work_dir = os.path.join(root_dir, 'work')
        os.makedirs(work_dir, exist_ok=True)
        res_dir = os.path.join(root_dir, 'resources')
        tmp_dir = os.path.join(root_dir, "tmp")

        assert self.resources

        os.makedirs(res_dir, exist_ok=True)
        if os.path.isdir(self.resources[0]):
            shutil.copytree(self.resources[0], res_dir)
        else:
            for resource_file in self.resources:
                shutil.copy(resource_file, res_dir)

        for result_file in self.results:
            shutil.copy(result_file, work_dir)

        dir_mapping = self.docker_task_cls.specify_dir_mapping(
            resources=res_dir,
            temporary=tmp_dir,
            work=work_dir,
            output=os.path.join(root_dir, 'output'),
            logs=os.path.join(root_dir, 'logs'),
        )

        extra_data = dict(
            subtask_paths=['/golem/work/{}'.format(
                os.path.basename(i)) for i in self.results
            ],
            subtask_borders=[
                self.subtask_info['crop_window'][0],
                self.subtask_info['crop_window'][2],
                self.subtask_info['crop_window'][1],
                self.subtask_info['crop_window'][3],
            ],
            scene_path=self.subtask_info['scene_file'],
            resolution=self.subtask_info['resolution'],
            samples=self.subtask_info['samples'],
            frames=self.subtask_info['frames'],
            output_format=self.subtask_info['output_format'],
            basefilename='crop',
            entrypoint="python3 /golem/entrypoints/verifier_entrypoint.py",
        )

        self.docker_task = self.docker_task_cls(
            docker_images=[(self.DOCKER_NAME, self.DOCKER_TAG)],
            extra_data=extra_data,
            dir_mapping=dir_mapping,
            timeout=self.timeout)

        def error(exception):
            logger.warning(
                f'Verification process exception. '
                f'Subtask_id: {subtask_id}. Exception: {exception}')
            self.finished.errback(exception)

        def callback(*_):
            with open(os.path.join(dir_mapping.output, 'verdict.json'), 'r') \
                    as f:
                verdict = json.load(f)

            logger.info(
                "Subtask %s verification verdict: %s",
                subtask_id,
                verdict,
            )
            if verdict['verdict']:
                self.finished.callback(True)
            else:
                self.finished.errback(
                    Exception('Verification result negative', verdict))

        logger.info(
            f' Starting docker thread for:  '
            f'Subtask_id: {subtask_id}. Extra data:{json.dumps(extra_data)}.')
        d = self.docker_task.start()
        d.addErrback(error)
        d.addCallback(callback)
