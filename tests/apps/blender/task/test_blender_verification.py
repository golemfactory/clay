import time
import os
from twisted.internet.defer import Deferred
from apps.blender.task.blendercropper import BlenderCropper
from apps.blender.task.verifier import BlenderVerifier
from golem.core.common import get_golem_path
from golem.core.deferred import sync_wait
from golem.testutils import TempDirFixture
from golem.docker.image import DockerImage
from golem.task.localcomputer import ComputerAdapter
from golem.tools.ci import ci_skip


class TestGenerateCrops(TempDirFixture):

    def setUp(self):
        # pylint: disable=R0915
        super().setUp()
        self.cropper = BlenderCropper()
        self.golem_dir = get_golem_path()
        self.resources = [os.path.join(
            self.golem_dir,
            'apps/blender/benchmark/test_task/bmw27_cpu.blend')]
        self.computer = ComputerAdapter()

        self.subtask_info = dict()
        self.subtask_info['res_x'] = 150
        self.subtask_info['res_y'] = 150
        self.subtask_info['use_frames'] = False
        self.subtask_info['end_task'] = 1
        self.subtask_info['total_tasks'] = 1
        self.subtask_info['node_id'] = 'deadbeef'
        self.subtask_info['frames'] = [1]
        self.subtask_info['start_task'] = 1
        self.subtask_info['subtask_id'] = '250771152547690738285326338136457465'
        self.subtask_info['perf'] = 713.176
        self.subtask_info['crop_window'] = (0.0, 1.0, 0.0, 1.0)
        self.subtask_info['output_format'] = 'PNG'
        self.subtask_info['all_frames'] = [1]
        self.subtask_info['script_src'] = ''
        self.subtask_info['tmp_dir'] = self.tempdir
        self.subtask_info['subtask_timeout'] = 600
        self.subtask_info['scene_file'] = '/golem/resources/bmw27_cpu.blend'
        self.subtask_info['path_root'] = os.path.dirname(self.resources[0])
        self.subtask_info['parts'] = 1
        self.subtask_info['outfilebasename'] = 'GolemTask'
        self.subtask_info['ctd'] = dict()
        self.subtask_info['ctd']['deadline'] = time.time() + 3600
        self.subtask_info['ctd']['docker_images'] = [DockerImage(
            'golemfactory/blender', tag='1.4').to_dict()]
        self.subtask_info['ctd']['environment'] = 'BLENDER'
        self.subtask_info['ctd']['extra_data'] = dict()
        self.subtask_info['ctd']['extra_data']['end_task'] =\
            self.subtask_info['end_task']
        self.subtask_info['ctd']['extra_data']['frames'] =\
            self.subtask_info['frames']
        self.subtask_info['ctd']['extra_data']['outfilebasename'] =\
            self.subtask_info['outfilebasename']
        self.subtask_info['ctd']['extra_data']['output_format'] =\
            self.subtask_info['output_format']
        self.subtask_info['ctd']['extra_data']['path_root'] =\
            self.subtask_info['path_root']
        self.subtask_info['ctd']['extra_data']['scene_file'] =\
            self.subtask_info['scene_file']
        self.subtask_info['ctd']['extra_data']['script_src'] =\
            self.subtask_info['script_src']
        self.subtask_info['ctd']['extra_data']['start_task'] =\
            self.subtask_info['start_task']
        self.subtask_info['ctd']['extra_data']['total_tasks'] =\
            self.subtask_info['total_tasks']
        self.subtask_info['ctd']['key_id'] = 'deadbeef'
        self.subtask_info['ctd']['performance'] = self.subtask_info['perf']
        self.subtask_info['ctd']['return_address'] = '127.0.0.1'
        self.subtask_info['ctd']['return_port'] = 40103
        self.subtask_info['ctd']['short_description'] = ''
        self.subtask_info['ctd']['src_code'] = open(
            os.path.join(
                self.golem_dir,
                'apps/blender/resources/scripts/docker_blendertask.py'),
            'r').read()
        self.subtask_info['ctd']['subtask_id'] = self.subtask_info['subtask_id']
        self.subtask_info['ctd']['task_id'] =\
            '7d8cb5f8-2a8c-43a1-9189-44a5f422fbe1'
        self.subtask_info['ctd']['task_owner'] = dict()
        self.subtask_info['ctd']['working_directory'] = self.tempdir

    @ci_skip
    def test_bad_image(self):

        d = Deferred()

        def success(*args, **kwargs):
            # pylint: disable=unused-argument
            assert False

        def failure(*args, **kwargs):
            # pylint: disable=unused-argument
            d.callback(True)

        def verification_finished():
            print("Verification finished")

        verifier = BlenderVerifier(verification_finished)
        verifier.computer = ComputerAdapter()

        verifier.current_results_file = os.path.join(
            self.golem_dir,
            'tests/apps/blender/task/very_bad_image.png')

        verifier.success = success
        verifier.failure = failure
        verifier.subtask_info = self.subtask_info

        self.cropper.render_crops(
            self.computer,
            self.resources,
            verifier._crop_rendered,
            verifier._crop_render_failure,
            self.subtask_info)

        sync_wait(d, 140)

    @ci_skip
    def test_good_image(self):
        d = Deferred()

        def success(*args, **kwargs):
            # pylint: disable=unused-argument
            d.callback(True)

        def failure(*args, **kwargs):
            # pylint: disable=unused-argument
            assert False

        def verification_finished():
            print("Verification finished")

        verifier = BlenderVerifier(verification_finished)
        verifier.computer = ComputerAdapter()

        verifier.current_results_file = os.path.join(
            self.golem_dir,
            'tests/apps/blender/task/good_image.png')

        verifier.success = success
        verifier.failure = failure
        verifier.subtask_info = self.subtask_info

        self.cropper.render_crops(
            self.computer,
            self.resources,
            verifier._crop_rendered,
            verifier._crop_render_failure,
            self.subtask_info)

        sync_wait(d, 140)
