import logging
import math

from apps.core.task.verificator import CoreFilesVerificator, \
    SubtaskVerificationState
from apps.rendering.resources.imgcompare import check_size


logger = logging.getLogger("apps.rendering")


class RenderingVerificator(CoreFilesVerificator):
    def __init__(self, verification_options=None):
        super(RenderingVerificator, self).\
            __init__(verification_options)
        self.tmp_dir = None
        self.res_x = 0
        self.res_y = 0
        self.total_tasks = 0
        self.root_path = ""
        self.verified_clients = list()

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        if self._verify_imgs(subtask_id, subtask_info, tr_files, task):
            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
        else:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER

    def _verify_imgs(self, subtask_id, subtask_info, tr_files, task):
        if len(tr_files) == 0:
            return False

        res_x, res_y = self._get_part_size(subtask_info)

        for img in tr_files:
            if not self._check_size(img, res_x, res_y):
                return False
        return True

    def _check_size(self, file_, res_x, res_y):
        return check_size(file_, res_x, res_y)

    def _get_part_size(self, subtask_info):
        return self.res_x, self.res_y

    def _get_part_img_size(self, subtask_info):
        # verification method reacts to key error
        num_task = subtask_info['start_task']
        if self.total_tasks == 0 \
                or num_task > self.total_tasks:
            logger.error("Wrong total tasks number ({}) "
                         "for subtask number {}".format(
                            self.total_tasks, num_task))
            return 0, 0, 0, 0
        img_height = int(math.floor(self.res_y / self.total_tasks))
        return 0, (num_task - 1) * img_height, self.res_x, num_task * img_height


class FrameRenderingVerificator(RenderingVerificator):

    def __init__(self, *args, **kwargs):
        super(FrameRenderingVerificator, self).\
            __init__(*args, **kwargs)
        self.use_frames = False
        self.frames = []

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        if self.use_frames and self.total_tasks <= len(self.frames):
            frames_list = subtask_info['frames']
            if len(tr_files) < len(frames_list):
                self.ver_states[subtask_id] = \
                    SubtaskVerificationState.WRONG_ANSWER
                return
        if not self._verify_imgs(
                subtask_id,
                subtask_info,
                tr_files,
                task):
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
        else:
            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED

    def _get_part_img_size(self, subtask_info):
        if not self.use_frames or self.__full_frames():
            return super(FrameRenderingVerificator, self)\
                ._get_part_img_size(subtask_info)
        else:
            start_task = subtask_info['start_task']
            parts = subtask_info['parts']
            num_task = self._count_part(start_task, parts)
            img_height = int(math.floor(self.res_y / parts))
            part_min_x = 1
            part_max_x = self.res_x - 1
            part_min_y = (num_task - 1) * img_height + 1
            part_max_y = num_task * img_height - 1
            return part_min_x, part_min_y, part_max_x, part_max_y

    def _count_part(self, start_num, parts):
        return ((start_num - 1) % parts) + 1

    def __full_frames(self):
        return self.total_tasks <= len(self.frames)
