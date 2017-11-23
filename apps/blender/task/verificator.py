import math
import random

from golem.core.common import timeout_to_deadline

from apps.rendering.task.verificator import FrameRenderingVerificator
from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from apps.blender.resources.imgcompare import check_size
from apps.blender.task import blenderrendertask

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
        self.compositing = False
        self.output_format = ""
        self.src_code = ""
        self.docker_images = []
        self.verification_timeout = 0

    def _blender_check(self, subtask_id: str, frames:list, parts: int,
                       num_of_parts: int,
                       resolution_x :int ,resolution_y: int,
                       output_fomat: str, compositing: bool, timeout: int,
                       reference_data, resources, results
                       ):
        """
        :param subtask_id:
        :param frames: list of ints
        which frames should be rendered

        :param parts: int
        if there is only one frame than to how many parts it’s splitted
        :param num_of_parts: int int
        if there is only one frame, which part we should render

        :param resolution_x:
        :param resolution_y:
        :param output_fomat:
        Possible values: "PNG", "TGA", "EXR", "JPEG", "BMP"
        :param compositing:
        Is compositing turn on?
        :param timeout:
        How many seconds are to compute this task.
	    If verification timeouts then it returns enum: NOT_SURE.

        :param reference_data:
        Path to files that were already present on the machine.
        These files has been already produced by requestor for verification purpose.
        If start_verification is used by Consent,
        then it shall generate the reference_data by itself based on ‘resources’
        :param resources:
        Path to files that are present on the machine.
        Should contain all the input resources used to produce a result.
        :param results:
        Path to files that have been already downloaded to this machine.
        Should contain final images produced for this subtask info.
        :return: None.
        However an exception shall be thrown if there were problems during start
        (ex. missing files, missing access, unknown subtask_type, too much overload)
        """
        pass

    def _check_files(self, subtask_id, subtask_info, tr_files,
                     task: 'blenderrendertask.BlenderRenderTask'):
        # First, assume it is wrong ;p
        self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER

        if len(tr_files) == 0:
            logger.warning("Subtask %s verification failed. \n"
                           "Not enough files received", str(subtask_id))
            return

        if self.use_frames and self.total_tasks <= len(self.frames):
            frames_list = subtask_info['frames']
            if len(tr_files) < len(frames_list) or len(tr_files) == 0:
                logger.warning("Subtask %s verification failed. \n"
                               "Not enough files received", str(subtask_id))
                return

        res_x, res_y = self._get_part_size(subtask_info)
        for img in tr_files:  # GG todo do we still need it - yes?
            if not self._check_size(img, res_x, res_y):
                logger.warning("Subtask %s verification failed. \n"
                               "Img size mismatch", str(subtask_id))
                return

        if len(tr_files) > 1:
            raise ValueError("Received more than 1 file: len(tr_files) > 1")

        file_for_verification = tr_files[0]

        try:
            start_task = subtask_info['start_task']
            frames, parts = task.get_frames_and_parts(start_task)
            min_x, max_x, min_y, max_y = task.get_crop_window(start_task, parts)

            scene_file = task.main_scene_file

            cmd = "validation.py " + scene_file + " " \
                "--crop_window_size " \
                + str(min_x) + "," + str(max_x) + "," \
                + str(min_y) + "," + str(max_x) + " " \
                "--resolution " + str(res_x) + "," + str(res_y) + " "\
                "--rendered_scene " + file_for_verification + " " \
                "--name_of_excel_file wynik_liczby"  # noqa

            c = subprocess.run(
                shlex.split(cmd),
                stdin=PIPE, stdout=PIPE, stderr=PIPE, check=True)

            self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
            stdout = c.stdout.decode()
            print(stdout)
        except subprocess.CalledProcessError as e:
            self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER
            logger.warning("Subtask %s verification failed %s: ",
                           str(subtask_id), str(e))

            logger.info("e.stderr: subtask_id %s \n %s \n",
                        str(subtask_id), str(e.stderr.decode()))

            logger.info("e.stdout: subtask_id %s \n %s \n",
                        str(subtask_id), str(e.stdout.decode()))

            # GG todo remove prints
            print(str(e))
            print(str(e.stdout.decode()))
            print(str(e.stderr.decode()))

        logger.info("Subtask %s verification result: %s",
                    str(subtask_id), self.ver_states[subtask_id].name)


    def change_scope(self, subtask_id, start_box, tr_file, subtask_info):
        extra_data, _ = super(BlenderVerificator, self). \
            change_scope(subtask_id, start_box, tr_file, subtask_info)
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
            # in this case task will be divided into not equal parts:
            # floor or ceil of (res_y/total_tasks)
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
