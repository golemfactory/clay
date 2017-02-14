from copy import copy
import logging
import math
import os
import random
import uuid

from golem.core.keysauth import get_random, get_random_float

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState
from apps.rendering.resources.imgrepr import verify_img, advance_verify_img

logger = logging.getLogger("apps.rendering")


class RenderingVerificator(CoreVerificator):
    def __init__(self, res_x, res_y, total_tasks, advance_verification=False,
                 verification_options=None):
        super(RenderingVerificator, self).__init__(advance_verification, verification_options)
        self.res_x = res_x
        self.res_y = res_y
        self.total_tasks = total_tasks
        self.tmp_dir = None
        self.verified_clients = list()

    @CoreVerificator.handle_key_error_for_state
    def verify(self, subtask_id, subtask_info, tr_files):
        if self._verify_imgs(subtask_id, subtask_info, tr_files):
            return SubtaskVerificationState.VERIFIED
        else:
            return SubtaskVerificationState.WRONG_ANSWER

    def _verify_imgs(self, subtask_id, subtask_info, tr_files):
        res_x, res_y = self._get_part_size(subtask_id)

        adv_test_file = self._choose_adv_ver_file(tr_files, subtask_id)
        x0, y0, x1, y1 = self._get_part_img_size(subtask_id, adv_test_file, subtask_info)

        for tr_file in tr_files:
            if adv_test_file is not None and tr_file in adv_test_file:
                start_box = self._get_box_start(x0, y0, x1, y1)
                logger.debug('testBox: {}'.format(start_box))
                cmp_file, cmp_start_box = self._get_cmp_file(tr_file, start_box, subtask_id,
                                                             subtask_info)
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

    def _get_part_size(self, subtask_id):
        return self.res_x, self.res_y

    def _get_box_start(self, x0, y0, x1, y1):
        ver_x = min(self.verification_options.box_size[0], x1 - x0)
        ver_y = min(self.verification_options.box_size[1], y1 - y0)
        start_x = get_random(x0, x1 - ver_x)
        start_y = get_random(y0, y1 - ver_y)
        return start_x, start_y

    def _choose_adv_ver_file(self, tr_files, subtask_id):
        adv_test_file = None
        if self.advance_verification:
            if self.__use_adv_verification(subtask_id):
                adv_test_file = random.sample(tr_files, 1)
        return adv_test_file

    def _get_part_img_size(self, subtask_id, adv_test_file, subtask_info):
        num_task = subtask_info[subtask_id]['start_task']
        img_height = int(math.floor(float(self.res_y) / float(self.total_tasks)))
        return 0, (num_task - 1) * img_height, self.res_x, num_task * img_height

    def _get_cmp_file(self, tr_file, start_box, subtask_id, subtask_info):
        extra_data, new_start_box = self._change_scope(subtask_id, start_box, tr_file,
                                                       subtask_info)
        cmp_file = self._run_task(extra_data)
        return cmp_file, new_start_box

    def _change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data = copy(subtask_info[subtask_id])
        extra_data['outfilebasename'] = str(uuid.uuid4())
        extra_data['tmp_path'] = os.path.join(self.tmp_dir,
                                              str(subtask_info[subtask_id]['start_task']))
        if not os.path.isdir(extra_data['tmp_path']):
            os.mkdir(extra_data['tmp_path'])
        return extra_data, start_box

    def __use_adv_verification(self, subtask_id):
        if self.verification_options.type == 'forAll':
            return True
        if self.verification_options.type == 'forFirst':
            if self.ver_states[subtask_id]['node_id'] not in self.verified_clients:
                return True
        if self.verification_options.type == 'random' and get_random_float() < self.verification_options.probability:
            return True
        return False
