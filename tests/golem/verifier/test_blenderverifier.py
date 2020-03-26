import logging
import os
import random
import shutil
import time
from contextlib import suppress
from time import sleep
from typing import Iterable, Collection, Tuple, Any, Dict
from unittest import mock

import cv2
import math
import numpy as np
import pytest
from PIL import Image
from golem_messages.message import ComputeTaskDef

from golem.core.common import get_golem_path, is_linux
from golem.core.deferred import sync_wait
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.task.localcomputer import ComputerAdapter
from golem.testutils import TempDirFixture
from golem.verifier.blender_verifier import BlenderVerifier
from tests.golem.verifier.test_utils.helpers import \
    find_crop_files_in_path, \
    are_pixels_equal, find_fragments_in_path

logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.skipif(
    not is_linux(),
    reason='Docker is only available on Linux buildbots')
class TestBlenderVerifier(TempDirFixture):
    TIMEOUT = 150

    def setUp(self) -> None:
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
                'tests/apps/blender/verification/test_data/chessboard_400x400.blend'),
        ]
        self.computer = ComputerAdapter()
        self.subtask_info = self._create_subtask_info()

    def tearDown(self):
        try:
            self.remove_files()
        except OSError as e:
            logger.debug("%r", e, exc_info=True)
            tree = ''
            for path, _dirs, files in os.walk(self.path):
                tree += path + '\n'
                for f in files:
                    tree += f + '\n'
            logger.error("Failed to remove files %r", tree)
            # Tie up loose ends.
            import gc
            gc.collect()
            # On windows there's sometimes a problem with syncing all threads.
            # Try again after 3 seconds
            sleep(3)
            self.remove_files()
        super().tearDown()

    def remove_files(self):
        above_tmp_dir = os.path.dirname(self.tempdir)
        for root, dirs, files in os.walk(above_tmp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

    def test_bad_image(self):
        self._test_image(['very_bad_image.png'], 'Verification result negative')

    def test_good_image(self):
        self._test_image(['chessboard_400x400_1.png'])

    def test_blurred_image(self):
        self._test_image(
            ['almost_good_image.png'],
            'Verification result negative',
        )

    def test_multiple_frames_in_subtask(self):
        self.subtask_info['all_frames'] = [1, 2]
        self.subtask_info['frames'] = [1, 2]
        self.subtask_info['ctd']['extra_data']['frames'] = [1, 2]
        self._test_image(['chessboard_400x400_1.png', 'chessboard_400x400_2.png'])

    def test_docker_error(self):
        # Set na invalid param so that Docker computation fails inside
        self.subtask_info['frames'] = None
        self._test_image(
            ['chessboard_400x400_1.png'],
            'Subtask computation failed with exit code 1',
        )

    def test_multiple_subtasks_in_task(self):
        result_image = cv2.imread(os.path.join(
            get_golem_path(),
            'tests/apps/blender/verification/test_data',
            'chessboard_400x400_1.png',
        ))
        y_crop_coordinate_step = 0
        y_crop_float_coordinate_step = 0.0
        for i in range(1, 6):
            with self.subTest(i=i):
                # Split image to cropped parts
                split_image = result_image[
                    y_crop_coordinate_step:y_crop_coordinate_step + 80, 0:400
                ]

                # Store images in temporary directory to load them to verification
                temp_path = os.path.join(self.tempdir, f'GolemTask_1000{i}.png')
                cv2.imwrite(temp_path, split_image)

                # Create clear verification_data for every crop image
                verification_data = dict(
                    subtask_info=self._create_subtask_info(
                        borders_y=[
                            round(0.8 - y_crop_float_coordinate_step, 2),
                            round(1.0 - y_crop_float_coordinate_step, 2)
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
                y_crop_coordinate_step += 80
                y_crop_float_coordinate_step = round(
                    y_crop_float_coordinate_step + 0.2, 2
                )

    def test_cropping_mechanism_problematic_value(self):
        """
        Test that uses border_y value (0.53) that was known to be problematic
        for the old cropping mechanism
        """
        scene_y_min = 0.0
        scene_y_max = 0.53
        self._run_cropping_test(scene_y_min, scene_y_max)

    def test_random_crop_window(self):
        random.seed(0)
        for i in range(1, 100):
            with self.subTest(i=i):
                scene_y_min, scene_y_max = \
                    self._generate_random_float_coordinates()
                print(f'i={i}, y_min={scene_y_min}, y_max={scene_y_max}')

                self._run_cropping_test(scene_y_min, scene_y_max)

    def _create_basic_subtask_info(
            self,
            borders_y: Iterable[float] = (0.0, 1.0),
            outfilebasename: str = "GolemTask_1",
    ) -> Dict[str, Any]:
        return dict(
            scene_file='/golem/resources/chessboard_400x400.blend',
            resolution=[400, 400],
            use_compositing=False,
            samples=0,
            frames=[1],
            output_format='PNG',
            use_frames=False,
            start_task=1,
            total_tasks=1,
            crops=[dict(
                outfilebasename=outfilebasename,
                borders_x=[0.0, 1.0],
                borders_y=list(borders_y),
            )],
            entrypoint='python3 /golem/entrypoints/verifier_entrypoint.py',
            path_root=os.path.dirname(self.resources[0]),
            subtask_id=str(random.randint(1 * 10 ** 36, 9 * 10 ** 36)),
        )

    def _create_subtask_info(
            self,
            borders_y: Collection[float] = (0.0, 1.0),
            outfilebasename: str = "GolemTask_1"
    ) -> Dict[str, Any]:
        borders_y = list(borders_y)
        subtask_info = self._create_basic_subtask_info(
            borders_y=borders_y,
            outfilebasename=outfilebasename
        )
        subtask_info.update(
            ctd=ComputeTaskDef(
                deadline=time.time() + 3600,
                docker_images=[
                    DockerImage('golemfactory/blender', tag='1.13')
                    .to_dict()
                ],
                extra_data=self._create_basic_subtask_info(
                    borders_y=borders_y,
                    outfilebasename=outfilebasename
                )
            ),
            crop_window=[0.0, 1.0, borders_y[0], borders_y[1]],
            tmp_dir=self.tempdir,
            subtask_timeout=600,
            parts=1,
        )
        return subtask_info

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

    def _prepare_subtask_info_for_cropping_tests(
            self,
            y_min: float,
            y_max: float,
            x_min: float,
            x_max: float,
    ) -> None:
        self.subtask_info['samples'] = 0
        self.subtask_info['scene_file'] = \
            '/golem/resources/chessboard_400x400.blend'
        self.resources = [
            os.path.join(
                get_golem_path(),
                'tests/apps/blender/verification/test_data/'
                'chessboard_400x400.blend'
            ),
        ]
        self.subtask_info['resolution'] = [400, 400]
        self.subtask_info['crops'] = [
            {
                'outfilebasename':
                    'chessboard_{}'.format(self.subtask_info['start_task']),
                'borders_x': [x_min, x_max],
                'borders_y': [y_min, y_max]
            }
        ]
        self.subtask_info['crop_window'] = [x_min, x_max, y_min, y_max]

    def _prepare_verification_data(
            self,
            result_path: str,
            y_min: float,
            y_max: float,
            x_min: float,
            x_max: float,
    ) -> Dict[str, Any]:
        self._prepare_subtask_info_for_cropping_tests(y_min, y_max, x_min,
                                                      x_max)
        verification_data = {
            'subtask_info': self.subtask_info,
            'results': [result_path],
            'reference_data': [],
            'resources': self.resources,
            'paths': os.path.dirname(self.resources[0])
        }
        return verification_data

    def _prepare_image_fragment(
            self,
            image_path: str,
            y_min: float,
            y_max: float,
            x_min: float = 0.0,
            x_max: float = 1.0,
    ) -> str:
        result = 'chessboard_fragment.png'
        result_path = os.path.join(self.tempdir, result)

        image = Image.open(image_path)
        image_fragment = image.crop(
            (
                math.floor(image.width * x_min),
                image.height - math.floor(
                    (np.float32(y_max) * np.float32(image.height))),
                math.floor(image.width * x_max),
                image.height - math.floor(
                    (np.float32(y_min) * np.float32(image.height))),
            )
        )
        image_fragment.save(result_path)
        return result_path

    def _run_cropping_test(
            self,
            scene_y_min: float,
            scene_y_max: float,
            scene_x_min: float = 0.0,
            scene_x_max: float = 1.0,
    ) -> None:
        full_image_path = os.path.join(
            get_golem_path(),
            'tests/apps/blender/verification/test_data',
            'chessboard_400x400_1.png'
        )
        result_path = self._prepare_image_fragment(
            full_image_path,
            scene_y_min,
            scene_y_max
        )
        verification_data = self._prepare_verification_data(
            result_path,
            scene_y_min,
            scene_y_max,
            scene_x_min,
            scene_x_max,
        )
        verifier = BlenderVerifier(verification_data, DockerTaskThread)
        d = verifier.start_verification()

        with suppress(Exception):
            sync_wait(d, self.TIMEOUT)

        self._assert_crops_match()

    def _assert_crops_match(self) -> None:
        above_tmp_dir = os.path.dirname(self.tempdir)
        crops_paths = find_crop_files_in_path(os.path.join(above_tmp_dir,
                                                           'output'))
        fragments_paths = find_fragments_in_path(os.path.join(above_tmp_dir,
                                                              "work"))

        assert len(crops_paths) > 0, "There were no crops produced!"
        assert len(crops_paths) == len(
            fragments_paths
        ), "Amount of rendered crops != amount of image fragments!"
        for crop_path, fragment_path in zip(
                crops_paths,
                fragments_paths,
        ):
            assert are_pixels_equal(
                crop_path,
                fragment_path,
            ), f"crop: {crop_path} doesn't match: {fragment_path}"

    @staticmethod
    def _generate_random_float_coordinates() -> Tuple[float, float]:
        span = random.randint(20, 50)
        beginning = round(random.randint(0, 100 - span) / 100, 2)
        end = round(beginning + span / 100, 2)
        return beginning, end


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
                'scene_file': '/golem/resources/chessboard_400x400.blend',
                'resolution': [400, 400],
                'frames': [1],
                'samples': 0,
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
        with mock.patch('golem.verifier.blender_verifier.logger') \
                as mocked_logger:
            blender_verifier.start_verification()

        assert mocked_logger.error.call_count == 1
        assert 'Verification failed %r' in mocked_logger.error.call_args[0][0]
