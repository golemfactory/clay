import math
import random

from golem.core.common import timeout_to_deadline

from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from apps.blender.resources.imgcompare import check_size

import golem_verificator
import shlex
import subprocess
from subprocess import PIPE
from apps.core.task.verificator import SubtaskVerificationState

import logging
logger = logging.getLogger("apps.blender")


class BlenderVerificator(FrameRenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(BlenderVerificator, self).__init__(*args, **kwargs)
        self.box_size = [1, 1]
        self.compositing = False
        self.output_format = ""
        self.src_code = ""
        self.docker_images = []
        self.verification_timeout = 0
        self.advanced_verification = True

    # todo GG integrate CP metrics into _check_files

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        # First, assume it is wrong ;p
        self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER


        if self.use_frames and self.total_tasks <= len(self.frames):
            frames_list = subtask_info['frames']
            if len(tr_files) < len(frames_list) or len(tr_files) == 0:
                return

        res_x, res_y = self._get_part_size(subtask_info)
        for img in tr_files: # GG todo do we still need it
            if not self._check_size(img, res_x, res_y):
                return False

        #file_for_adv_ver = self._choose_adv_ver_file(tr_files, subtask_info)
        file_for_adv_ver = random.choice(tr_files)

        try:
            cmd = "./scripts/validation.py " \
                "../benchmark_blender/bmw27_cpu.blend " \
                "--crop_window_size 0,1,0,1 " \
                "--resolution 150,150 " \
                "--rendered_scene " \
                "../benchmark_blender/bad_image0001.png " \
                "--name_of_excel_file wynik_liczby"

            c = subprocess.run(
                shlex.split(cmd),
                stdin=PIPE, stdout=PIPE, stderr=PIPE, check=True)

            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
            self.verified_clients.append(subtask_info['node_id'])
            # GG what's this?
            stdout = c.stdout.decode()
            # print(stdout)
        except subprocess.CalledProcessError as e:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
            logger.info("Exception during verification of subtask %s %s: ",
                        str(subtask_id), str(e))

            logger.info("e.stdout: subtask_id %s \n %s \n",
                        str(subtask_id), str(e.stdout.decode()))

            logger.info("e.stderr: subtask_id %s \n %s \n",
                        str(subtask_id), str(e.stderr.decode()))

        logger.info("Subtask %s verification result: %s",
                    str(subtask_id), self.ver_states[subtask_id].name)

    def set_verification_options(self, verification_options):
        super(BlenderVerificator, self).set_verification_options(
            verification_options)
        if self.advanced_verification:
            box_x = min(verification_options.box_size[0], self.res_x)
            box_y = min(verification_options.box_size[1],
                        int(self.res_y / self.total_tasks))
            self.box_size = (box_x, box_y)

    def change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data, _ = super(BlenderVerificator, self).\
            change_scope(subtask_id, start_box,tr_file,subtask_info)
        min_x = start_box[0] / self.res_x
        max_x = (start_box[0] + self.verification_options.box_size[
            0] + 1) / self.res_x
        shift_y = (extra_data['start_task'] - 1) * (
        self.res_y / extra_data['total_tasks'])
        start_y = start_box[1] + shift_y
        max_y = (self.res_y - start_y) / self.res_y
        shift_y = start_y + self.verification_options.box_size[1] + 1
        min_y = max((self.res_y - shift_y) / self.res_y, 0.0)
        min_y = max(min_y, 0)
        script_src = generate_blender_crop_file(
            resolution=(self.res_x, self.res_y),
            borders_x=(min_x, max_x),
            borders_y=(min_y, max_y),
            use_compositing=self.compositing
        )
        extra_data['script_src'] = script_src
        extra_data['output_format'] = self.output_format
        return extra_data, (0, 0)

    def query_extra_data_for_advanced_verification(self, extra_data):
        ctd = super(BlenderVerificator,
                    self).query_extra_data_for_advanced_verification(extra_data)
        ctd.subtask_id = str(random.getrandbits(128))
        ctd.src_code = self.src_code
        ctd.docker_images = self.docker_images
        ctd.deadline = timeout_to_deadline(self.verification_timeout)
        return ctd

    def _get_part_img_size(self, subtask_info):
        x, y = self._get_part_size(subtask_info)
        return 0, 0, x, y

    def _get_part_size(self, subtask_info):
        start_task = subtask_info['start_task']
        if not self.use_frames:
            res_y = self._get_part_size_from_subtask_number(start_task)
        elif len(self.frames) >= self.total_tasks:
            res_y = self.res_y
        else:
            parts = int(self.total_tasks / len(self.frames))
            res_y = int(math.floor(self.res_y / parts))
        return self.res_x, res_y

    def _get_part_size_from_subtask_number(self, subtask_number):

        if self.res_y % self.total_tasks == 0:
            res_y = int(self.res_y / self.total_tasks)
        else:
            # in this case task will be divided into not equal parts: floor or ceil of (res_y/total_tasks)
            # ceiling will be height of subtasks with smaller num
            ceiling_height = int(math.ceil(self.res_y / self.total_tasks))
            ceiling_subtasks = self.total_tasks - (
            ceiling_height * self.total_tasks - self.res_y)
            if subtask_number > ceiling_subtasks:
                res_y = ceiling_height - 1
            else:
                res_y = ceiling_height
        return res_y

    def _check_size(self, file_, res_x, res_y):
        return check_size(file_, res_x, res_y)
