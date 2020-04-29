import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Type

import numpy
from twisted.internet.defer import Deferred

from golem.verifier.rendering_verifier import FrameRenderingVerifier
from golem.verifier.subtask_verification_state import SubtaskVerificationState

logger = logging.getLogger(__name__)


# FIXME #2086
# pylint: disable=R0902
class BlenderVerifier(FrameRenderingVerifier):
    DOCKER_NAME = 'golemfactory/blender_verifier'
    DOCKER_TAG = '1.9.2'

    def __init__(self, verification_data, docker_task_cls: Type) -> None:
        super().__init__(verification_data)
        self.verification_data = verification_data
        self.finished = Deferred()
        self.docker_task_cls = docker_task_cls
        self.timeout = 0
        self.docker_task = None

    def start_verification(self) -> Deferred:
        self.time_started = datetime.utcnow()
        logger.info(f'Start verification in BlenderVerifier. '
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
            border_y_min = numpy.float32(subtask_info['crops'][0]['borders_y'][
                0])
            border_y_max = numpy.float32(subtask_info['crops'][0]['borders_y'][
                1])

            crop_resolution_y = int(
                round(
                    numpy.float32(resolution_y * border_y_max -
                                  resolution_y * border_y_min)))
        return resolution_x, crop_resolution_y

    def stop(self):
        if self.docker_task:
            self.docker_task.end_comp()

    @staticmethod
    def _copy_files_with_directory_hierarchy(file_paths, copy_to):
        common_dir = os.path.commonpath(file_paths)
        for path in file_paths:
            relative_path = os.path.relpath(path, start=common_dir)
            target_dir = os.path.join(copy_to, relative_path)
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            shutil.copy(path, target_dir)

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

        root_dir = Path(os.path.dirname(self.results[0])).parent

        work_dir = os.path.join(root_dir, 'work')
        os.makedirs(work_dir, exist_ok=True)

        res_dir = os.path.join(root_dir, 'resources')
        os.makedirs(res_dir, exist_ok=True)
        tmp_dir = os.path.join(root_dir, "tmp")

        assert self.resources
        assert self.results

        self._copy_files_with_directory_hierarchy(self.resources, res_dir)
        self._copy_files_with_directory_hierarchy(self.results, work_dir)

        dir_mapping = self.docker_task_cls.specify_dir_mapping(
            resources=res_dir,
            temporary=tmp_dir,
            work=work_dir,
            output=os.path.join(root_dir, "output"),
            logs=os.path.join(root_dir, "logs"),
            stats=os.path.join(root_dir, "stats"))

        extra_data = self._generate_verification_params(self.subtask_info,
                                                        self.results)

        self.docker_task = self.docker_task_cls(
            docker_images=[(self.DOCKER_NAME, self.DOCKER_TAG)],
            extra_data=extra_data,
            dir_mapping=dir_mapping,
            timeout=self.timeout)

        def error(exception):
            logger.warning(f'Verification process exception. '
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

    @classmethod
    def _generate_verification_params(cls, subtask_info: dict, results: list):
        return dict(
            subtask_paths=[
                '/golem/work/{}'.format(os.path.basename(i)) for i in results
            ],
            subtask_borders=[
                subtask_info['crop_window'][0],
                subtask_info['crop_window'][2],
                subtask_info['crop_window'][1],
                subtask_info['crop_window'][3],
            ],
            scene_path=subtask_info['scene_file'],
            resolution=subtask_info['resolution'],
            samples=subtask_info['samples'],
            frames=subtask_info['frames'],
            output_format=subtask_info['output_format'],
            basefilename='crop',
            entrypoint="python3 /golem/entrypoints/verifier_entrypoint.py",
        )
