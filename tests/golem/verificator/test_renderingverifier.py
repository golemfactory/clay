import os

from PIL import Image

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verificator.constants import SubtaskVerificationState
from golem.verificator.rendering_verifier import (
    RenderingVerifier,
    FrameRenderingVerifier,
)


class VerificationMixin(TempDirFixture, LogTestCase):
    def setUp(self):
        super().setUp()
        self.x = 80
        self.y = 60
        self.subtask_info = {
            "frames": [3],
            "use_frames": False,
            "total_tasks": 2,
            "all_frames": [3],
            "res_x": self.x,
            "res_y": self.y,
            "subtask_id": "2432423"
        }

        self.verification_data = {
            'subtask_info': self.subtask_info,
            'results': [],
            'reference_data': [],
            'resources': []
        }

    def _create_images(self):
        image_path = os.path.join(self.path, "img1.png")
        self._save_image(image_path)
        image_path2 = os.path.join(self.path, "img2.png")
        self._save_image(image_path2)
        return [image_path, image_path2]

    def _save_image(self, image_path):
        image = Image.new("RGB", (self.x, self.y))
        image.save(image_path)


class TestRenderingVerifier(VerificationMixin):
    def test_get_part_size(self):
        rendering_verifier = RenderingVerifier(self.verification_data)

        assert rendering_verifier._get_part_size(
            self.subtask_info) == (self.x, self.y)

    def test_simple_verification_wrong_answer_when_not_a_file(self):
        # Result is not a file
        self.verification_data['results'] = ['non_exiting_file']

        rendering_verifier = RenderingVerifier(self.verification_data)
        rendering_verifier.simple_verification(self.verification_data)
        verifier_state = rendering_verifier.verification_completed()[1]

        assert verifier_state == SubtaskVerificationState.WRONG_ANSWER

    def test_simple_verification_wrong_answer_when_result_is_not_an_image(self):
        # Result is not an image
        path = os.path.join(self.path, 'not_image.txt')
        with open(path, 'w') as f:
            f.write("This is not an image, this is SPARTA!!!")

        self.verification_data['results'] = [path]

        rendering_verifier = RenderingVerifier(self.verification_data)
        rendering_verifier.simple_verification(self.verification_data)
        verifier_state = rendering_verifier.verification_completed()[1]

        assert verifier_state == SubtaskVerificationState.WRONG_ANSWER

    def test_simple_verification_correct_results(self):
        # Proper simple verification - just check if images have proper sizes
        self.verification_data['results'] = self._create_images()

        rendering_verifier = RenderingVerifier(self.verification_data)
        rendering_verifier.simple_verification(self.verification_data)
        verifier_state = rendering_verifier.verification_completed()[1]

        assert verifier_state == SubtaskVerificationState.VERIFIED


class TestFrameRenderingVerifier(VerificationMixin):
    def setUp(self):
        super().setUp()
        self.verification_data['results'] = self._create_images()

    def test_simple_verification_frames_correct_results(self):
        frame_rendering_verifier = FrameRenderingVerifier(
            self.verification_data
        )
        frame_rendering_verifier.simple_verification(self.verification_data)
        frame_rendering_verifier.verification_completed()

        assert frame_rendering_verifier.state == \
               SubtaskVerificationState.VERIFIED

    def test_simple_verification_frames_less_tasks_than_frames(self):
        self.subtask_info["use_frames"] = True
        self.subtask_info["all_frames"] = [3, 4, 5, 6]
        self.subtask_info["frames"] = [3, 4, 5, 6]

        frame_rendering_verifier = FrameRenderingVerifier(
            self.verification_data
        )
        frame_rendering_verifier.simple_verification(self.verification_data)
        frame_rendering_verifier.verification_completed()

        assert frame_rendering_verifier.state == \
               SubtaskVerificationState.WRONG_ANSWER

    def test_simple_verification_frames_no_results(self):
        self.verification_data["results"] = ["file1"]

        frame_rendering_verifier = FrameRenderingVerifier(
            self.verification_data
        )
        frame_rendering_verifier.simple_verification(self.verification_data)
        frame_rendering_verifier.verification_completed()

        assert frame_rendering_verifier.state == \
               SubtaskVerificationState.WRONG_ANSWER

    def test_simple_verification_frames_wrong_resolution(self):
        img_path = os.path.join(self.path, "img1.png")
        img = Image.new("RGB", (800, 600))
        img.save(img_path)
        self.verification_data["results"] = [img_path]

        frame_rendering_verifier = FrameRenderingVerifier(
            self.verification_data
        )
        frame_rendering_verifier.simple_verification(self.verification_data)
        frame_rendering_verifier.verification_completed()

        assert frame_rendering_verifier.state == \
               SubtaskVerificationState.WRONG_ANSWER
