import os
import subprocess
import tempfile

import time

from golem.docker.image import DockerImage
from golem.task.taskbase import ResultType
from golem.task.taskthread import TaskThread
from golem.vm.memorychecker import MemoryChecker

DOCKER_BLENDER_PATH = '/opt/blender/'

FIREJAIL_COMMAND = 'firejail'
BLENDER_DIR = tempfile.gettempdir()
BLENDER_BINARY_PATH = os.path.join(BLENDER_DIR, 'blender', 'blender')
SCRIPT_FILE_NAME = 'blenderscript.py'
BLENDER_IMAGE_REP = 'golemfactory/blender'
BLENDER_IMAGE_TAG = '1.3'

STDOUT_FILE = "stdout.log"
STDERR_FILE = "stderr.log"


def _prepare_blender():
    if not os.path.isfile(BLENDER_BINARY_PATH):
        img = DockerImage(BLENDER_IMAGE_REP, tag=BLENDER_IMAGE_TAG)
        img.extract_path(DOCKER_BLENDER_PATH, BLENDER_DIR)


class BlenderFirejailTaskThread(TaskThread):

    # pylint: disable=too-many-arguments
    def __init__(self, task_computer, subtask_id, script_dir, src_code,
                 extra_data, short_desc, res_path, tmp_path, timeout,
                 check_mem=False) -> None:

        super().__init__(task_computer, subtask_id, script_dir, src_code,
                         extra_data, short_desc, res_path, tmp_path, timeout)
        self.mc = None
        self.check_mem = check_mem
        self.work_dir = os.path.join(self.tmp_path, "work")
        self.output_dir = os.path.join(self.tmp_path, "output")

    def run(self):
        try:
            _prepare_blender()
            # don't charge for the time it takes to prepare blender env
            self.start_time = time.time()
            self._prepare_dirs()
            self._prepare_data()
            if self.check_mem:
                self.mc = MemoryChecker()
                self.mc.start()
            stdout_path = os.path.join(self.output_dir, STDOUT_FILE)
            stderr_path = os.path.join(self.output_dir, STDERR_FILE)
            with open(stdout_path, "w") as out, open(stderr_path, "w") as err:
                for frame in self.extra_data['frames']:
                    cmd = self._format_blender_cmd(frame)
                    p = subprocess.run([FIREJAIL_COMMAND] + cmd,
                                       stdout=out,
                                       stderr=err)
                    p.check_returncode()

            estm_mem = 0
            if self.mc:
                estm_mem = self.mc.stop()

            # collect results
            out_files = []
            for root, _, files in os.walk(self.output_dir):
                for name in files:
                    out_files.append(os.path.join(root, name))
            self.result = {"data": out_files, "result_type": ResultType.FILES}
            if self.check_mem:
                self.result = (self.result, estm_mem)
            self.task_computer.task_computed(self)
        except Exception as err:  # pylint: disable=broad-except
            self._fail(err)
        finally:
            self.done = True
            if self.mc and self.mc.working:
                self.mc.stop()

    def _format_blender_cmd(self, frame):
        scene_file = os.path.join(self.res_path, self.extra_data['scene_file'])
        script_file = self._get_script_path()
        out_file = "{}/{}_{}".format(self.output_dir,
                                     self.extra_data['outfilebasename'],
                                     self.extra_data['start_task'])
        output_format = self.extra_data['output_format'].upper()
        cmd = [
            BLENDER_BINARY_PATH,
            "-b", scene_file,
            "-y",  # enable scripting by default
            "-P", script_file,
            "-o", out_file,
            "-noaudio",
            "-F", output_format,
            "-t", str(os.cpu_count()),
            "-f", str(frame),
            "--", "GPU"
        ]
        return cmd

    def _prepare_dirs(self):
        if not os.path.exists(self.work_dir):
            os.mkdir(self.work_dir)
            os.chmod(self.work_dir, 0o770)
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
            os.chmod(self.output_dir, 0o770)

    def _prepare_data(self):
        blender_script_path = self._get_script_path()
        with open(blender_script_path, "w") as script_file:
            script_file.write(self.extra_data['script_src'])

    def _get_script_path(self):
        return os.path.join(self.work_dir, SCRIPT_FILE_NAME)
