import os
import time
import pytest
from unittest import mock

from golem.core.common import get_golem_path, is_linux
from golem.core.deferred import sync_wait
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.task.localcomputer import ComputerAdapter
from golem.testutils import TempDirFixture
from golem.verificator.blender_verifier import BlenderVerifier


@pytest.mark.slow
@pytest.mark.skipif(
    not is_linux(),
    reason='Docker is only available on Linux buildbots')
class TestBlenderVerifier(TempDirFixture):
    TIMEOUT = 150

    def setUp(self):
        # pylint: disable=R0915
        super().setUp()
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dirs=[self.new_path],
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
        self.subtask_info['entrypoint'] = \
            'python3 /golem/entrypoints/render_entrypoint.py'

        self.subtask_info['path_root'] = os.path.dirname(self.resources[0])
        self.subtask_info['parts'] = 1
        self.subtask_info['owner'] = "deadbeef"
        self.subtask_info['ctd'] = dict()
        self.subtask_info['ctd']['deadline'] = time.time() + 3600
        self.subtask_info['ctd']['docker_images'] = [DockerImage(
            'golemfactory/blender', tag='1.9').to_dict()]
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
        self.subtask_info['ctd']['extra_data']['entrypoint'] = \
            self.subtask_info['entrypoint']
        self.subtask_info['ctd']['subtask_id'] = self.subtask_info['subtask_id']

    def _test_image(self, results, exception_regex=None):
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

        verifier = BlenderVerifier(verification_data, DockerTaskThread)
        d = verifier.start_verification(verification_data)

        if not exception_regex:
            sync_wait(d, self.TIMEOUT)
        else:
            with self.assertRaisesRegex(Exception, exception_regex):
                sync_wait(d, self.TIMEOUT)

    def test_bad_image(self):
        self._test_image(['very_bad_image.png'], 'Verification result negative')

    def test_good_image(self):
        self._test_image(['GolemTask_10001.png'])

    def test_subsampled_image(self):
        self._test_image(
            ['almost_good_image.png'],
            'Verification result negative',
        )

    def test_multiple_frames_in_subtask(self):
        self.subtask_info['all_frames'] = [1, 2]
        self.subtask_info['frames'] = [1, 2]
        self.subtask_info['ctd']['extra_data']['frames'] = [1, 2]
        self._test_image(['GolemTask_10001.png', 'GolemTask_10002.png'])

    def test_docker_error(self):
        # Set na invalid param so that Docker computation fails inside
        self.subtask_info['frames'] = None
        self._test_image(
            ['GolemTask_10001.png'],
            'Subtask computation failed with exit code 1',
        )
