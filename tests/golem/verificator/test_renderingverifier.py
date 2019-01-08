import os

from PIL import Image

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verificator.rendering_verifier import (
    RenderingVerifier,
    logger,
    FrameRenderingVerifier,
)
from golem.verificator.verifier import SubtaskVerificationState


class TestRenderingVerifier(TempDirFixture, LogTestCase):

    last_verdict = None

    def test_get_part_size(self):
        subtask_info = {
            "res_x": 800,
            "res_y": 600}
        verification_data = {'subtask_info': subtask_info, 'results': [], 'reference_data': [], 'resources': []}
        rendering_verifier = RenderingVerifier(verification_data)
        assert rendering_verifier._get_part_size(subtask_info) == (800, 600)

    def test_simple_verification(self):
        self.last_verdict = None
        # Result us not a file
        subtask_info = {
            "res_x": 80,
            "res_y": 60,
            "subtask_id": "subtask1"
        }

        verification_data = {'subtask_info': subtask_info, 'results': ["file1"], 'reference_data': [], 'resources': []}

        rendering_verifier = RenderingVerifier(verification_data)

        rendering_verifier.simple_verification(verification_data)
        self.last_verdict = rendering_verifier.verification_completed()[1]
        assert self.last_verdict == SubtaskVerificationState.WRONG_ANSWER

        subtask_info["total_tasks"] = 30
        subtask_info["start_task"] = 3
        # No data
        self.last_verdict = None
        rendering_verifier.simple_verification(verification_data)
        self.last_verdict = rendering_verifier.verification_completed()[1]
        assert self.last_verdict == SubtaskVerificationState.WRONG_ANSWER

        # Result is not an image
        self.last_verdict = None
        rendering_verifier.simple_verification(verification_data)
        self.last_verdict = rendering_verifier.verification_completed()[1]
        assert self.last_verdict == SubtaskVerificationState.WRONG_ANSWER

        img_path = os.path.join(self.path, "img1.png")
        img = Image.new("RGB", (80, 60))
        img.save(img_path)

        img_path2 = os.path.join(self.path, "img2.png")
        img = Image.new("RGB", (80, 60))
        img.save(img_path2)

        ver_dir = os.path.join(self.path, "ver_img")
        os.makedirs(ver_dir)
        img_path3 = os.path.join(ver_dir, "img3.png")
        img.save(img_path3)

        # Proper simple verification - just check if images have proper sizes
        self.last_verdict = None
        verification_data['results'] = [img_path, img_path2]

        rendering_verifier.simple_verification(verification_data)
        self.last_verdict = rendering_verifier.verification_completed()[1]
        assert self.last_verdict == SubtaskVerificationState.VERIFIED

    def test_get_part_img_size(self):
        subtask_info = {
            "res_x": 800,
            "res_y": 600,
            "total_tasks": 30,
            "start_task": 3
        }

        verification_data = {'subtask_info': subtask_info, 'results': ["file1"], 'reference_data': [], 'resources': []}

        rendering_verifier = RenderingVerifier(verification_data)

        assert rendering_verifier._get_part_img_size(subtask_info) == (0, 40, 800, 60)

        subtask_info["total_tasks"] = 0
        with self.assertLogs(logger, level="WARNING"):
            assert rendering_verifier._get_part_img_size(subtask_info) == (0, 0, 0, 0)

        subtask_info["total_tasks"] = 30
        subtask_info["start_task"] = 34
        with self.assertLogs(logger, level="WARNING"):
            assert rendering_verifier._get_part_img_size(subtask_info) == (0, 0, 0, 0)

        subtask_info["total_tasks"] = 11
        subtask_info["res_y"] = 211
        subtask_info["start_task"] = 5
        assert rendering_verifier._get_part_img_size(subtask_info) == (0, 76, 800, 95)


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
        assert frame_rendering_verifier.state == SubtaskVerificationState.WRONG_ANSWER

    def test_get_part_img_size(self):
        verification_data = {'subtask_info': {}, 'results': [], 'reference_data': [], 'resources': []}
        frame_rendering_verifier = FrameRenderingVerifier(verification_data)
        subtask_info = {
            "res_x": 600,
            "res_y": 800,
            "total_tasks": 20,
            "all_frames": [5, 6, 7, 8, 9],
            "start_task": 1,
            "parts": 4,
            "use_frames": True}
        assert frame_rendering_verifier._get_part_img_size(subtask_info) == (1, 1, 599, 199)
        subtask_info["use_frames"] = False
        assert frame_rendering_verifier._get_part_img_size(subtask_info) == (0, 0, 600, 40)
