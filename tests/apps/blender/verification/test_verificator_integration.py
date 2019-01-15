import logging
import os
import time
from unittest import skip, mock

from twisted.internet.defer import Deferred

from apps.blender.blender_reference_generator import BlenderReferenceGenerator
from apps.blender.blenderenvironment import BlenderEnvironment
from apps.blender.task.blenderrendertask import BlenderRenderTask
from golem.verificator.common.ci import ci_skip
from golem.core.common import get_golem_path
from golem.core.deferred import sync_wait
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.task.localcomputer import ComputerAdapter
from golem.testutils import TempDirFixture


@ci_skip
class TestVerificatorModuleIntegration(TempDirFixture):
    TIMEOUT = 30

    def setUp(self):
        # pylint: disable=R0915
        super().setUp()
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dir=self.new_path,
            in_background=True)
        self.blender_reference_generator = BlenderReferenceGenerator()
        self.golem_dir = get_golem_path()
        self.resources = ['tests/apps/blender/verification/test_data/bmw.blend']
        self.computer = ComputerAdapter()

        self.subtask_info = dict()
        self.subtask_info['scene_file'] = '/golem/resources/bmw.blend'
        self.subtask_info['resolution'] = [150, 150]
        self.subtask_info['use_compositing'] = False
        self.subtask_info['samples'] = 35
        self.subtask_info['frames'] = [1]
        self.subtask_info['output_format'] = 'PNG'
        self.subtask_info['use_frames'] = False
        self.subtask_info['start_task'] = 1
        self.subtask_info['total_tasks'] = 1
        self.subtask_info['crops'] = [
            {
                'outfilebasename':
                    'GolemTask_{}'.format(self.subtask_info['start_task']),
                'borders_x': [0.0, 1.0],
                'borders_y':[0.0, 1.0]
            }
        ]
        self.subtask_info['node_id'] = 'deadbeef'
        self.subtask_info['subtask_id'] = '250771152547690738285326338136457465'
        self.subtask_info['all_frames'] = [1]
        self.subtask_info['tmp_dir'] = self.tempdir
        self.subtask_info['subtask_timeout'] = 600
        self.subtask_info['script_filepath'] = '/golem/scripts/job.py'

        self.subtask_info['path_root'] = os.path.dirname(self.resources[0])
        self.subtask_info['parts'] = 1
        self.subtask_info['owner'] = "deadbeef"
        self.subtask_info['ctd'] = dict()
        self.subtask_info['ctd']['deadline'] = time.time() + 3600
        self.subtask_info['ctd']['docker_images'] = [DockerImage(
            'golemfactory/blender', tag='1.8').to_dict()]
        self.subtask_info['ctd']['extra_data'] = dict()
        self.subtask_info['ctd']['extra_data']['scene_file'] = \
            self.subtask_info['scene_file']
        self.subtask_info['ctd']['extra_data']['resolution'] = \
            self.subtask_info['resolution']
        self.subtask_info['ctd']['extra_data']['use_compositing'] = \
            self.subtask_info['use_compositing']
        self.subtask_info['ctd']['extra_data']['samples'] = \
            self.subtask_info['samples']
        self.subtask_info['ctd']['extra_data']['frames'] = \
            self.subtask_info['frames']
        self.subtask_info['ctd']['extra_data']['output_format'] = \
            self.subtask_info['output_format']
        self.subtask_info['ctd']['extra_data']['start_task'] = \
            self.subtask_info['start_task']
        self.subtask_info['ctd']['extra_data']['total_tasks'] = \
            self.subtask_info['total_tasks']
        self.subtask_info['ctd']['extra_data']['crops'] = \
            self.subtask_info['crops']
        self.subtask_info['ctd']['extra_data']['path_root'] = \
            self.subtask_info['path_root']
        self.subtask_info['ctd']['extra_data']['script_filepath'] = \
            self.subtask_info['script_filepath']
        self.subtask_info['ctd']['short_description'] = ''
        self.subtask_info['ctd']['subtask_id'] = self.subtask_info['subtask_id']

    def test_bad_image(self):

        d = Deferred()

        def success(*args, **kwargs):
            # pylint: disable=unused-argument
            assert False

        def failure(*args, **kwargs):
            # pylint: disable=unused-argument
            d.callback(True)

        verification_data = {}
        verification_data['subtask_info'] = self.subtask_info
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = self.resources
        verification_data['paths'] = os.path.dirname(self.resources[0])

        verifier = BlenderRenderTask.VERIFIER_CLASS(verification_data)
        verifier.default_crops_number = 1
        verifier.current_results_files = ['tests/apps/blender/verification/'
                                          'test_data/very_bad_image.png']

        verifier.subtask_info = self.subtask_info
        verifier.resources = self.resources

        finished = self.blender_reference_generator.render_crops(
            self.resources,
            self.subtask_info,
            1
        )

        for deferred in finished:
            deferred.addCallback(success)
            deferred.addErrback(failure)

        sync_wait(d, TestVerificatorModuleIntegration.TIMEOUT)

    def test_good_image(self):
        d = Deferred()

        def success(*args, **kwargs):
            # pylint: disable=unused-argument
            d.callback(True)

        def failure(*args, **kwargs):
            # pylint: disable=unused-argument
            assert False

        verification_data = {}
        verification_data['subtask_info'] = self.subtask_info
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = self.resources
        verification_data['paths'] = os.path.dirname(self.resources[0])

        verifier = BlenderRenderTask.VERIFIER_CLASS(verification_data)
        verifier.default_crops_number = 1
        verifier.current_results_files = \
            ['tests/apps/blender/verification/test_data/GolemTask_10001.png']

        verifier.subtask_info = self.subtask_info
        verifier.resources = self.resources

        finished = self.blender_reference_generator.render_crops(
            self.resources,
            self.subtask_info,
            1
        )

        for deferred in finished:
            deferred.addCallback(success)
            deferred.addErrback(failure)

        sync_wait(d, TestVerificatorModuleIntegration.TIMEOUT)

    def test_subsampled_image(self):
        d = Deferred()

        def success(*args, **kwargs):
            # pylint: disable=unused-argument
            assert False

        def failure(*args, **kwargs):
            # pylint: disable=unused-argument
            d.callback(True)

        verification_data = {}
        verification_data['subtask_info'] = self.subtask_info
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = self.resources
        verification_data['paths'] = os.path.dirname(self.resources[0])

        verifier = BlenderRenderTask.VERIFIER_CLASS(verification_data)
        verifier.default_crops_number = 1
        verifier.current_results_files = \
            ['tests/apps/blender/verification/test_data/almost_good_image.png']

        verifier.subtask_info = self.subtask_info
        verifier.resources = self.resources

        finished = self.blender_reference_generator.render_crops(
            self.resources,
            self.subtask_info,
            1
        )

        for deferred in finished:
            deferred.addCallback(success)
            deferred.addErrback(failure)

        sync_wait(d, TestVerificatorModuleIntegration.TIMEOUT)

    def test_multiple_frames_in_subtask(self):
        d = Deferred()

        self.subtask_info['all_frames'] = [1, 2]
        self.subtask_info['frames'] = [1, 2]
        self.subtask_info['ctd']['extra_data']['frames'] = [1, 2]

        def success(*args, **kwargs):
            # pylint: disable=unused-argument
            d.callback(True)

        def failure(*args, **kwargs):
            # pylint: disable=unused-argument
            assert False

        verification_data = {}
        verification_data['subtask_info'] = self.subtask_info
        verification_data['results'] = []
        verification_data['reference_data'] = []
        verification_data['resources'] = self.resources
        verification_data["reference_generator"] = \
            self.blender_reference_generator
        verification_data['paths'] = os.path.dirname(self.resources[0])

        verifier = BlenderRenderTask.VERIFIER_CLASS(verification_data)
        verifier.default_crops_number = 1
        verifier.current_results_files = [
            'tests/apps/blender/verification/test_data/GolemTask_10001.png',
            'tests/apps/blender/verification/test_data/GolemTask_10002.png']

        verifier.subtask_info = self.subtask_info
        verifier.resources = self.resources

        finished = self.blender_reference_generator.render_crops(
            self.resources,
            self.subtask_info,
            1
        )

        for deferred in finished:
            deferred.addCallback(success)
            deferred.addErrback(failure)

        sync_wait(d, TestVerificatorModuleIntegration.TIMEOUT)
