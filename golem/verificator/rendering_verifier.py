import logging
import math
from datetime import datetime
from collections import Callable
from .core_verifier import CoreVerifier
from .imgrepr import load_img
from .verifier import SubtaskVerificationState

logger = logging.getLogger("apps.rendering")


class RenderingVerifier(CoreVerifier):

    def __init__(self, verification_data):
        super().__init__()
        self.subtask_info = verification_data["subtask_info"]
        self.reference_data = verification_data["reference_data"]
        self.resources = verification_data["resources"]
        self.results = verification_data["results"]
        self.state = SubtaskVerificationState.WAITING

    def start_verification(self, verification_data):
        self.time_started = datetime.utcnow()
        return self._verify_with_reference(verification_data)

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

    def _get_part_img_size(self, subtask_info):
        # verification method reacts to key error
        num_task = subtask_info['start_task']
        total_tasks = subtask_info['total_tasks']
        res_x = subtask_info['res_x']
        res_y = subtask_info['res_y']
        if total_tasks == 0 \
                or num_task > total_tasks:
            logger.error("Wrong total tasks number ({}) "
                         "for subtask number {}".format(total_tasks,
                                                        num_task))
            return 0, 0, 0, 0
        img_height = int(math.floor(res_y / total_tasks))
        return 0, (num_task - 1) * img_height, res_x, num_task * img_height


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

    def _get_part_img_size(self, subtask_info):
        use_frames = subtask_info['use_frames']
        if not use_frames or self.__full_frames(subtask_info):
            return super(FrameRenderingVerifier, self)\
                ._get_part_img_size(subtask_info)
        else:
            start_task = subtask_info['start_task']
            parts = subtask_info['parts']
            num_task = self._count_part(start_task, parts)
            img_height = int(math.floor(subtask_info['res_y'] / parts))
            part_min_x = 1
            part_max_x = subtask_info['res_x'] - 1
            part_min_y = (num_task - 1) * img_height + 1
            part_max_y = num_task * img_height - 1
            return part_min_x, part_min_y, part_max_x, part_max_y

    def _count_part(self, start_num, parts):
        return ((start_num - 1) % parts) + 1

    def __full_frames(self, subtask_info):
        return subtask_info['total_tasks'] <= len(subtask_info['all_frames'])
