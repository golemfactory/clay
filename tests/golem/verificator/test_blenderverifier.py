import os
import random
import shutil
import time
from unittest import mock
from typing import List, Optional
import cv2

from golem_messages.message import ComputeTaskDef
import pytest

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

    def _create_basic_subtask_info(  # pylint: disable=too-many-arguments
            self,
            resolution: Optional[List[int]] = None,
            samples: Optional[int] = None,
            borders_y: Optional[List[float]] = None,
            entrypoint: Optional[str] = None,
            outfilebasename: Optional[str] = None,
    ) -> dict:
        return dict(
            scene_file='/golem/resources/bmw.blend',
            resolution=resolution if resolution is not None else [150, 150],
            use_compositing=False,
            samples=samples if samples is not None else 35,
            frames=[1],
            output_format='PNG',
            use_frames=False,
            start_task=1,
            total_tasks=1,
            crops=list(
                dict(
                    outfilebasename=outfilebasename if \
                        outfilebasename is not None else "GolemTask_1",
                    borders_x=[0.0, 1.0],
                    borders_y=(
                        borders_y if borders_y is not None else [0.0, 1.0]
                    ),
                )
            ),
            entrypoint=entrypoint if entrypoint is not None else \
                'python3 /golem/entrypoints/verifier_entrypoint.py',
            path_root=os.path.dirname(self.resources[0]),
            subtask_id=str(random.randint(1 * 10 ** 36, 9 * 10 ** 36)),
        )

    def _create_subtask_info(  # pylint: disable=too-many-arguments
            self,
            resolution: Optional[List[int]] = None,
            samples: Optional[int] = None,
            borders_y: Optional[List[float]] = None,
            entrypoint: Optional[str] = None,
            outfilebasename: Optional[str] = None,
    ) -> dict:
        return dict(
            **self._create_basic_subtask_info(
                resolution,
                samples,
                borders_y,
                entrypoint,
                outfilebasename
            ),
            ctd=ComputeTaskDef(
                deadline=time.time() + 3600,
                docker_images=[
                    DockerImage('golemfactory/blender', tag='1.9').to_dict()
                ],
                extra_data=dict(**self._create_basic_subtask_info(
                    resolution,
                    samples,
                    borders_y,
                    entrypoint,
                    outfilebasename,
                ))
            ),
            crop_window=[0.0, 1.0, borders_y[0], borders_y[1]] \
                if borders_y is not None else [0.0, 1.0, 0.0, 1.0],
            tmp_dir=self.tempdir,
            subtask_timeout=600,
            parts=1,
        )

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
        self.subtask_info = self._create_subtask_info()

    def _test_image(self, results, exception_regex=None):
        verification_data = {}
        verification_data['subtask_info'] = self.subtask_info
        verification_data['results'] = []
        for result in results:
            result_path = os.path.join(self.tempdir, result)
            shutil.copyfile(
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
        d = verifier.start_verification()

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


    def test_multiple_subtasks_in_task(self):
        result_image = cv2.imread(os.path.join(
            get_golem_path(),
            'tests/apps/blender/verification/test_data',
            'GolemTask_10001.png',
        ))
        y_crop_cord_step = 0
        y_crop_float_cord_step = 0.0
        splited_images = {}
        for i in range(1, 6):
            # Split image to cropped parts
            splited_images[f'image_part_{i}'] = \
                result_image[y_crop_cord_step:y_crop_cord_step + 30, 0:150]

            # Store images in temporary directory to load them to verification
            temp_path = os.path.join(self.tempdir, f'GolemTask_1000{i}.png')
            cv2.imwrite(temp_path, splited_images[f'image_part_{i}'])

            # Create clear verification_data for every crop image
            verification_data = dict(
                subtask_info=self._create_subtask_info(
                    borders_y=[
                        0.8 - y_crop_float_cord_step,
                        1.0 - y_crop_float_cord_step
                    ],
                    outfilebasename=f'GolemTask_{i}'
                ),
                results=[temp_path],
                resources=self.resources,
                paths=os.path.dirname(self.resources[0]),
            )
            verifier = BlenderVerifier(verification_data, DockerTaskThread)
            d = verifier.start_verification()
            sync_wait(d, self.TIMEOUT)

            # Change crop coordinates for next image verification
            y_crop_cord_step += 30
            y_crop_float_cord_step = round(y_crop_float_cord_step + 0.2, 2)

    def _prep_sanity_check_data(self):
        self.subtask_info['entrypoint'] = \
            'python3 /golem/entrypoints/test_entrypoint.py'
        self.subtask_info['samples'] = 30
        self.subtask_info['scene_file'] = \
            '/golem/resources/chessboard_400x400_5x5.blend'
        self.resources = [
            os.path.join(
                get_golem_path(),
                'tests/apps/blender/verification/test_data/'
                'chessboard_400x400_5x5.blend'
            ),
        ]
        self.subtask_info['resolution'] = [400, 400]
        self.subtask_info['crops'] = [
            {
                'outfilebasename':
                    'GolemTask_{}'.format(self.subtask_info['start_task']),
                'borders_x': [0.0, 1.0],
                'borders_y': [0.0, 0.53]
            }
        ]
        self.subtask_info['crop_window'] = [0.0, 1.0, 0.0, 0.53]

    @pytest.mark.skip(reason="Need new version of docker image on dockerhub.")
    def test_docker_sanity_check(self):
        self._prep_sanity_check_data()

        verification_data = {
            'subtask_info': self.subtask_info,
            'results': [os.path.join(self.tempdir, 'GolemTask_10001.png')],
            'reference_data': [],
            'resources': self.resources,
            'paths': os.path.dirname(self.resources[0])
        }

        verifier = BlenderVerifier(verification_data, DockerTaskThread)
        d = verifier.start_verification()

        sync_wait(d, self.TIMEOUT)

    # todo review: typo
    @pytest.mark.skip(reason="Need new version of docker image on dockerhub.")
    def test_random_crop_widow(self):
        self._prep_sanity_check_data()

        # todo review: Non deterministic test. We expected test for randomly chosen values
        # but they should be hardcoded in test. Otherwise it's difficult to reproduce results.
        subtask_height = random.randint(20, 50)
        subtask_ymin = round(random.randint(0, 100 - subtask_height)/100, 2)
        subtask_ymax = round(subtask_ymin + subtask_height/100, 2)

        self.subtask_info['crops'] = [
            {
                'outfilebasename':
                    'GolemTask_{}'.format(self.subtask_info['start_task']),
                'borders_x': [0.0, 1.0],
                'borders_y': [subtask_ymin, subtask_ymax]
            }
        ]
        self.subtask_info['crop_window'] = [
            0.0, 1.0, subtask_ymin, subtask_ymax
        ]

        verification_data = {
            'subtask_info': self.subtask_info,
            'results': [os.path.join(self.tempdir, 'GolemTask_10001.png')],
            'reference_data': [],
            'resources': self.resources,
            'paths': os.path.dirname(self.resources[0])
        }

        verifier = BlenderVerifier(verification_data, DockerTaskThread)
        d = verifier.start_verification()

        sync_wait(d, self.TIMEOUT)


class TestUnitBlenderVerifier:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.width = 400
        self.height = 350
        self.subtask_info_stub = {
            'all_frames': [1, 2, 3],
            'total_tasks': 3,
            'use_frames': True,
            'resolution': [self.width, self.height]
        }

    def test__get_part_size_no_crops(self):
        result = BlenderVerifier._get_part_size(self.subtask_info_stub)
        assert result[0] == self.width
        assert result[1] == self.height

    @pytest.mark.parametrize(
        "start_border_y, expected_height", [
            (0, 140),
            (0.1, 105),
            (0.33, 24),
            (0.37, 10)
        ]
    )
    def test__get_part_size_with_crops(self, start_border_y, expected_height):
        crops = [{
            "id": 11,
            "outfilebasename": "crop11_",
            "borders_x": [0.2, 0.3],
            "borders_y": [start_border_y, 0.4]
        }]
        self.subtask_info_stub.update({
            'use_frames': False,
            'crops': crops
        })

        result = BlenderVerifier._get_part_size(self.subtask_info_stub)
        assert result[0] == self.width
        assert result[1] == expected_height

    def test_start_verification_exception_is_logged(self):
        class MyException(Exception):
            def __repr__(self):
                return ">This is Sparta!<"

        DockerTaskThreadMock = mock.Mock()
        DockerTaskThreadMock.return_value.start.side_effect = MyException()
        verification_data = {
            'subtask_info': {
                'path_root': 'some/path/',
                'crop_window': [0.1, 0.2, 0.3, 0.4],
                'scene_file': '/golem/resources/bmw.blend',
                'resolution': [600, 400],
                'frames': [1],
                'samples': 35,
                'output_format': 'PNG',
                'subtask_id': 'qwerty1234',
                'entrypoint': 'python3 /golem/entrypoints/'
                              'verifier_entrypoint.py'
            },
            'resources': mock.sentinel.resources,
            'results': ['/some/other/path/result.png'],
        }

        blender_verifier = BlenderVerifier(verification_data,
                                           DockerTaskThreadMock)
        with mock.patch('golem.verificator.blender_verifier.logger') \
                as mocked_logger:
            blender_verifier.start_verification()

        assert mocked_logger.error.call_count == 1
        assert 'Verification failed %r' in mocked_logger.error.call_args[0][0]
