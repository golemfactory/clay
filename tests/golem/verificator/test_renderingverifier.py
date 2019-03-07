import os

from PIL import Image

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verificator.constants import SubtaskVerificationState
from golem.verificator.rendering_verifier import (
    RenderingVerifier,
    FrameRenderingVerifier,
)


class TestRenderingVerifier(TempDirFixture, LogTestCase):
    def setUp(self):
        super().setUp()
        self.x = 80
        self.y = 60
        self.subtask_info = {
            "res_x": self.x,
            "res_y": self.y,
            "subtask_id": "subtask1"
        }
        self.verification_data = {
            'subtask_info': self.subtask_info,
            'results': [],
            'reference_data': [],
            'resources': []
        }

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

    def test_simple_verification_wrong_answer_when_no_data(self):
        path = os.path.join(self.path, 'not_image.txt')
        with open(path, 'w') as f:
            f.write("This is not an image, this is SPARTA!!!")

        # Result is not an image
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

    def _create_images(self):
        image_path = os.path.join(self.path, "img1.png")
        self._save_image(image_path)
        image_path2 = os.path.join(self.path, "img2.png")
        self._save_image(image_path2)
        return [image_path, image_path2]

    def _save_image(self, image_path):
        image = Image.new("RGB", (self.x, self.y))
        image.save(image_path)


class TestFrameRenderingVerifier(TempDirFixture):

    def test_simple_verification_frames(self):

        subtask_info = {"frames": [3],
                        "use_frames": False,
                        "total_tasks": 20,
                        "all_frames": [3],
                        "res_x": 800,
                        "res_y": 600,
                        "subtask_id": "2432423"}

        verification_data = {'subtask_info': subtask_info, 'results': [], 'reference_data': [], 'resources': []}

        frame_rendering_verifier = FrameRenderingVerifier(verification_data)

        frame_rendering_verifier.subtask_info = subtask_info
        frame_rendering_verifier.simple_verification(verification_data)
        frame_rendering_verifier.verification_completed()
        assert frame_rendering_verifier.state == SubtaskVerificationState.WRONG_ANSWER

        subtask_info["use_frames"] = True
        subtask_info["all_frames"] = [3, 4, 5, 6]
        frame_rendering_verifier.simple_verification(verification_data)
        frame_rendering_verifier.verification_completed()
        assert frame_rendering_verifier.state == SubtaskVerificationState.WRONG_ANSWER

        subtask_info["total_tasks"] = 2
        frame_rendering_verifier.simple_verification(verification_data)
        frame_rendering_verifier.verification_completed()
        assert frame_rendering_verifier.state == SubtaskVerificationState.WRONG_ANSWER

        subtask_info["frames"] = [3, 4]
        verification_data["results"] = ["file1"]
        frame_rendering_verifier.simple_verification(verification_data)
        frame_rendering_verifier.verification_completed()
        assert frame_rendering_verifier.state == SubtaskVerificationState.WRONG_ANSWER

        subtask_info["start_task"] = 1
        verification_data["results"] = ["file1", "file2"]
        frame_rendering_verifier.simple_verification(verification_data)
        frame_rendering_verifier.verification_completed()
        assert frame_rendering_verifier.state == \
               SubtaskVerificationState.WRONG_ANSWER

        img_path = os.path.join(self.path, "img1.png")
        img = Image.new("RGB", (800, 600))
        img.save(img_path)
        subtask_info["start_task"] = 1
        verification_data["results"] = [img_path]
        frame_rendering_verifier.simple_verification(verification_data)
        frame_rendering_verifier.verification_completed()
        assert frame_rendering_verifier.state == \
               SubtaskVerificationState.WRONG_ANSWER
