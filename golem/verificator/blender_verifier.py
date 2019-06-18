import shutil
from datetime import datetime
from pathlib import Path
from typing import Type

import logging
import numpy
import os
import json

from golem.verificator.verifier import SubtaskVerificationState

from .rendering_verifier import FrameRenderingVerifier
from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)


# FIXME #2086
# pylint: disable=R0902
class BlenderVerifier(FrameRenderingVerifier):
    DOCKER_NAME = "golemfactory/blender_verifier"
    DOCKER_TAG = '1.3'

    def __init__(self, verification_data,
                 docker_task_cls: Type) -> None:
        super().__init__(verification_data)
        self.finished = Deferred()
        self.docker_task_cls = docker_task_cls
        self.timeout = 0
        self.docker_task = None

    def _get_part_size(self, subtask_info):
        if subtask_info['use_frames'] and len(subtask_info['all_frames']) \
                >= subtask_info['total_tasks']:
            res_y = subtask_info['resolution'][1]
        else:
            res_y = int(round(numpy.float32(
                numpy.float32(subtask_info['crops'][0]['borders_y'][0]) *
                numpy.float32(subtask_info['resolution'][1]))))
        return subtask_info['resolution'][0], res_y

    def start_verification(self, verification_data):
        self.time_started = datetime.utcnow()
        self.verification_data = verification_data

        try:
            self.start_rendering()
        # pylint: disable=W0703
        except Exception as e:
            logger.error("Verification failed %r", e)
            self.finished.errback(e)

        return self.finished

    def stop(self):
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

        self.finished.addCallback(success)
        self.finished.addErrback(failure)

        subtask_info = self.verification_data['subtask_info']
        root_dir = Path(os.path.dirname(
            self.verification_data['results'][0])).parent
        work_dir = os.path.join(root_dir, 'work')
        os.makedirs(work_dir, exist_ok=True)
        res_dir = os.path.join(root_dir, 'resources')
        tmp_dir = os.path.join(root_dir, "tmp")

        assert self.verification_data['resources']

        os.makedirs(res_dir, exist_ok=True)
        if os.path.isdir(self.verification_data['resources'][0]):
            shutil.copytree(self.verification_data['resources'][0], res_dir)
        else:
            for resource_file in self.verification_data['resources']:
                shutil.copy(resource_file, res_dir)

        for result_file in self.verification_data['results']:
            shutil.copy(result_file, work_dir)

        dir_mapping = self.docker_task_cls.specify_dir_mapping(
            resources=res_dir,
            temporary=tmp_dir,
            work=work_dir,
            output=os.path.join(root_dir, "output"),
            logs=os.path.join(root_dir, "logs"),
        )

        extra_data = dict(
            subtask_paths=['/golem/work/{}'.format(
                os.path.basename(i)) for i in self.verification_data['results']
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

        self.docker_task = self.docker_task_cls(
            docker_images=[(self.DOCKER_NAME, self.DOCKER_TAG)],
            extra_data=extra_data,
            dir_mapping=dir_mapping,
            timeout=self.timeout)

        def error(e):
            logger.warning("Verification process exception %s", e)
            self.finished.errback(e)

        def callback(*_):
            with open(os.path.join(dir_mapping.output, 'verdict.json'), 'r') \
                    as f:
                verdict = json.load(f)

            logger.info(
                "Subtask %s verification verdict: %s",
                subtask_info['subtask_id'],
                verdict,
            )
            if verdict['verdict']:
                self.finished.callback(True)
            else:
                self.finished.errback(
                    Exception('Verification result negative', verdict))

        d = self.docker_task.start()
        d.addErrback(error)
        d.addCallback(callback)
