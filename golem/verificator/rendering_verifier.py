import logging

from apps.rendering.resources.imgrepr import load_img
from .core_verifier import CoreVerifier
from .verifier import SubtaskVerificationState

logger = logging.getLogger("apps.rendering")


class RenderingVerifier(CoreVerifier):

    def __init__(self, verification_data):
        super().__init__()
        self.subtask_info = verification_data["subtask_info"]
        self.resources = verification_data["resources"]
        self.results = verification_data["results"]
        self.state = SubtaskVerificationState.WAITING

    @staticmethod
    def check_size(file_, res_x, res_y):
        img = load_img(file_)
        if img is None:
            return False
        img_x, img_y = img.get_size()
        if img_x != res_x:
            logger.info("Subtask size doesn't match, has %r,"
                        " should be %r", img.get_size(), (res_x, res_y))
            return False
        return True

    def _get_part_size(self, subtask_info):
        return subtask_info['res_x'], subtask_info['res_y']


class FrameRenderingVerifier(RenderingVerifier):

    def __init__(self, verification_data):
        super().__init__(verification_data)

    def simple_verification(self, verification_data):
        if not super().simple_verification(verification_data):
            return False

        subtask_info = verification_data['subtask_info']
        results = verification_data['results']
        use_frames = subtask_info['use_frames']
        total_tasks = subtask_info['total_tasks']
        frames = subtask_info['all_frames']
        if use_frames and total_tasks <= len(frames):
            frames_list = subtask_info['frames']
            if len(results) < len(frames_list):
                self.state = SubtaskVerificationState.WRONG_ANSWER
                return False

        res_x, res_y = self._get_part_size(subtask_info)

        for img in results:
            if not self.check_size(img, res_x, res_y):
                self.state = SubtaskVerificationState.WRONG_ANSWER
                return False
        self.state = SubtaskVerificationState.VERIFIED
        return True
