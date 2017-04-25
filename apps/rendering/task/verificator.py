from __future__ import division
from copy import copy
import logging
import math
import os
import random
import uuid

from golem.core.keysauth import get_random, get_random_float
from golem.core.fileshelper import ensure_dir_exists, find_file_with_ext
from golem.task.taskbase import ComputeTaskDef
from golem.task.localcomputer import LocalComputer

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState
from apps.rendering.resources.imgrepr import verify_img, advance_verify_img

logger = logging.getLogger("apps.rendering")


class RenderingVerificator(CoreVerificator):
    def __init__(self, verification_options=None, advanced_verification=False):
        super(RenderingVerificator, self).__init__(verification_options, advanced_verification)
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

        res_x, res_y = self._get_part_size(subtask_id, subtask_info)

        adv_test_file = self._choose_adv_ver_file(tr_files, subtask_info)
        x0, y0, x1, y1 = self._get_part_img_size(subtask_id, adv_test_file, subtask_info)

        for tr_file in tr_files:
            if adv_test_file is not None and tr_file in adv_test_file:
                start_box = self._get_box_start(x0, y0, x1, y1)
                logger.debug('testBox: {}'.format(start_box))
                cmp_file, cmp_start_box = self._get_cmp_file(tr_file, start_box, subtask_id,
                                                             subtask_info, task)
                logger.debug('cmp_start_box {}'.format(cmp_start_box))
                if not advance_verify_img(tr_file, res_x, res_y, start_box,
                                          self.verification_options.box_size, cmp_file,
                                          cmp_start_box):
                    return False
                else:
                    self.verified_clients.append(subtask_info['node_id'])
            if not self._verify_img(tr_file, res_x, res_y):
                return False

        return True

    def _verify_img(self, file_, res_x, res_y):
        return verify_img(file_, res_x, res_y)

    def _get_part_size(self, subtask_id, subtask_info):
        return self.res_x, self.res_y

    def _get_box_start(self, x0, y0, x1, y1):
        ver_x = min(self.verification_options.box_size[0], x1 - x0)
        ver_y = min(self.verification_options.box_size[1], y1 - y0)
        start_x = get_random(x0, x1 - ver_x)
        start_y = get_random(y0, y1 - ver_y)
        return start_x, start_y

    def _choose_adv_ver_file(self, tr_files, subtask_info):
        adv_test_file = None
        if self.advanced_verification:
            if self.__use_adv_verification(subtask_info):
                adv_test_file = random.choice(tr_files)
        return adv_test_file

    def _get_part_img_size(self, subtask_id, adv_test_file, subtask_info):
        num_task = subtask_info['start_task']  # verification method reacts to key error
        if self.total_tasks == 0 or num_task > self.total_tasks:
            logger.error("Wrong total tasks number ({}) for subtask number {}".format(
                self.total_tasks, num_task))
            return 0, 0, 0, 0
        img_height = int(math.floor(self.res_y / self.total_tasks))
        return 0, (num_task - 1) * img_height, self.res_x, num_task * img_height

    def _get_cmp_file(self, tr_file, start_box, subtask_id, subtask_info, task):
        extra_data, new_start_box = self.change_scope(subtask_id, start_box, tr_file, subtask_info)
        cmp_file = self._run_task(extra_data, task)

        return cmp_file, new_start_box

    def change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data = copy(subtask_info)
        extra_data['outfilebasename'] = str(uuid.uuid4())
        extra_data['tmp_path'] = os.path.join(self.tmp_dir, str(subtask_info['start_task']))
        ensure_dir_exists(extra_data['tmp_path'])
        return extra_data, start_box

    def _run_task(self, extra_data, task):
        computer = LocalComputer(task, self.root_path,
                                 self.__box_rendered,
                                 self.__box_render_error,
                                 lambda: self.query_extra_data_for_advanced_verification(
                                     extra_data),
                                 additional_resources=[])
        computer.run()
        results = None
        if computer.tt:
            computer.tt.join()
            results = computer.tt.result.get("data")
        if results:
            commonprefix = os.path.commonprefix(results)
            img = find_file_with_ext(commonprefix, ["." + extra_data['output_format']])
            if img is None:
                logger.error("No image file created")
            return img

    def query_extra_data_for_advanced_verification(self, extra_data):
        ctd = ComputeTaskDef()
        ctd.extra_data = extra_data
        return ctd

    def __box_rendered(self, results, time_spent):
        logger.info("Box for advanced verification created")

    def __box_render_error(self, error):
        logger.error("Cannot verify img: {}".format(error))

    def __use_adv_verification(self, subtask_info):
        if self.verification_options.type == 'forAll':
            return True
        if self.verification_options.type == 'forFirst':
            if subtask_info['node_id'] not in self.verified_clients:
                return True
        if self.verification_options.type == 'random':
            if get_random_float() < self.verification_options.probability:
                return True
        return False


class FrameRenderingVerificator(RenderingVerificator):

    def __init__(self, *args, **kwargs):
        super(FrameRenderingVerificator, self).__init__(*args, **kwargs)
        self.use_frames = False
        self.frames = []

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        if self.use_frames and self.total_tasks <= len(self.frames):
            frames_list = subtask_info['frames']
            if len(tr_files) < len(frames_list):
                self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
                return
        if not self._verify_imgs(subtask_id, subtask_info, tr_files, task):
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
        else:
            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED

    def _get_part_img_size(self, subtask_id, adv_test_file, subtask_info):
        if not self.use_frames or self.__full_frames():
            return super(FrameRenderingVerificator, self)._get_part_img_size(subtask_id,
                                                                             adv_test_file,
                                                                             subtask_info)
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

    def __full_frames(self):
        return self.total_tasks <= len(self.frames)

    def _count_part(self, start_num, parts):
        return ((start_num - 1) % parts) + 1
