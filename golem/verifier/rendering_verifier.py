import logging

from apps.rendering.resources.imgrepr import load_img
from golem.verifier.subtask_verification_state import SubtaskVerificationState
from golem.verifier.core_verifier import CoreVerifier

logger = logging.getLogger('apps.rendering')


class RenderingVerifier(CoreVerifier):

    def __init__(self, verification_data):
        super().__init__(verification_data)
        self.state = SubtaskVerificationState.WAITING
        self.resources = verification_data["resources"]

    @staticmethod
    def check_size(file_path, resolution_x, resolution_y):
        image = load_img(file_path)
        if image is None:
            return False
        image_x, image_y = image.get_size()
        if image_x != resolution_x or image_y != resolution_y:
            logger.info(
                "Subtask size doesn't match, has %r,"
                " should be %r",
                image.get_size(),
                (resolution_x, resolution_y))
            return False
        return True

    @staticmethod
    def _get_part_size(subtask_info):
        return subtask_info['res_x'], subtask_info['res_y']

    def simple_verification(self):
        if not super().simple_verification():
            return False
        if not self._are_image_sizes_correct():
            self.message = 'No proper task result found'
            self.state = SubtaskVerificationState.WRONG_ANSWER
            return False
        return True

    def _are_image_sizes_correct(self):
        resolution_x, resolution_y = self._get_part_size(self.subtask_info)
        for image in self.results:
            if not self.check_size(image, resolution_x, resolution_y):
                return False
        return True


class FrameRenderingVerifier(RenderingVerifier):

    def simple_verification(self):
        if not super().simple_verification():
            return False

        use_frames = self.subtask_info['use_frames']
        total_tasks = self.subtask_info['total_tasks']
        frames = self.subtask_info['all_frames']
        if use_frames and total_tasks <= len(frames):
            frames_list = self.subtask_info['frames']
            if len(self.results) < len(frames_list):
                self.state = SubtaskVerificationState.WRONG_ANSWER
                return False
        return True
