import os
import time
import pytest
from unittest import mock

from apps.blender.task.blenderrendertask import BlenderRenderTask
from golem.core.common import get_golem_path
from golem.core.deferred import sync_wait
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.task.localcomputer import ComputerAdapter
from golem.testutils import TempDirFixture


@pytest.mark.slow
class TestVerificatorModuleIntegration(TempDirFixture):
    TIMEOUT = 60

    def setUp(self):
        # pylint: disable=R0915
        super().setUp()
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dir=self.new_path,
            in_background=True)
        self.resources = [
            os.path.join(
                get_golem_path(),
                'tests/apps/blender/verification/test_data/bmw.blend'),
        ]
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
        self.subtask_info['crop_window'] = [0.0, 1.0, 0.0, 1.0]
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
        self.subtask_info['ctd']['subtask_id'] = self.subtask_info['subtask_id']

    def _test_image(self, results, expected_result):
        verification_data = {}
        verification_data['subtask_info'] = self.subtask_info
        verification_data['results'] = []
        for result in results:
            result_path = os.path.join(self.tempdir, result)
            os.link(
                os.path.join(
                    get_golem_path(),
                    'tests/apps/blender/verification/test_data',
                    result,
                ),
                result_path,
            )
            verification_data['results'].append(result_path)
        verification_data['reference_data'] = []
        verification_data['resources'] = self.resources
        verification_data['paths'] = os.path.dirname(self.resources[0])

        verifier = BlenderRenderTask.VERIFIER_CLASS(verification_data)
        d = verifier._verify_with_reference(verification_data)

        if expected_result:
            sync_wait(d, TestVerificatorModuleIntegration.TIMEOUT)
        else:
            with self.assertRaisesRegex(Exception, 'result negative'):
                sync_wait(d, TestVerificatorModuleIntegration.TIMEOUT)

    def test_bad_image(self):
        self._test_image(['very_bad_image.png'], False)

    def test_good_image(self):
        self._test_image(['GolemTask_10001.png'], True)

    def test_subsampled_image(self):
        self._test_image(['almost_good_image.png'], False)

    def test_multiple_frames_in_subtask(self):
        self.subtask_info['all_frames'] = [1, 2]
        self.subtask_info['frames'] = [1, 2]
        self.subtask_info['ctd']['extra_data']['frames'] = [1, 2]
        self._test_image(['GolemTask_10001.png', 'GolemTask_10002.png'], True)
