import os
import subprocess
import tempfile

import time

from apps.rendering.task.rendering_engine_requirement import RenderingEngine
from golem.core.common import get_golem_path
from golem.docker.image import DockerImage
from golem.resource import dirmanager
from golem.task.taskbase import ResultType
from golem.task.taskthread import TaskThread
from golem.vm.memorychecker import MemoryChecker

DOCKER_BLENDER_PATH = '/opt/blender/'

FIREJAIL_COMMAND = 'firejail'
BLENDER_DIR = os.path.join(tempfile.gettempdir(), 'golem_blender279')
BLENDER_BINARY_PATH = os.path.join(BLENDER_DIR, 'blender', 'blender')
SCRIPT_FILE_NAME = 'blenderscript.py'
BLENDER_IMAGE_REP = 'golemfactory/blender'
BLENDER_IMAGE_TAG = '1.4'

STDOUT_FILE = "stdout.log"
STDERR_FILE = "stderr.log"

BLENDER_SETUP_FILE = dirmanager.find_task_script(
    os.path.join(get_golem_path(), 'apps', 'blender', 'firejailenvironment'),
    'blender_setup.py')
FIREJAIL_PROFILE_TEMPLATE_PATH = dirmanager.find_task_script(
    os.path.join(get_golem_path(), 'apps', 'blender', 'firejailenvironment'),
    'blender.profile.template')


def _init_gpu_blender():
    cmd = [
        BLENDER_BINARY_PATH,
        "-b",
        "-y",  # enable scripting by default
        "-P", BLENDER_SETUP_FILE,
        "-noaudio"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Exception('Failed to initialize blender with GPU support')


class BlenderFirejailTaskThread(TaskThread):

    # pylint: disable=too-many-arguments
    def __init__(self, task_computer, subtask_id, script_dir, src_code,
                 extra_data, short_desc, res_path, tmp_path, timeout,
                 rendering_engine: RenderingEngine, check_mem=False) -> None:

        super().__init__(task_computer, subtask_id, script_dir, src_code,
                         extra_data, short_desc, res_path, tmp_path, timeout)
        self.rendering_engine = rendering_engine
        self.mc = None
        self.check_mem = check_mem
        self.work_dir = os.path.join(self.tmp_path, "work")
        self.output_dir = os.path.join(self.tmp_path, "output")
        self.profile_path = os.path.join(self.tmp_path, 'blender.profile')

    def run(self):
        try:
            self._prepare_blender()
            # don't charge for the time it takes to prepare blender env
            self.start_time = time.time()
            self._prepare_dirs()
            self._prepare_data()
            self._prepare_firejail_profile()
            if self.check_mem:
                self.mc = MemoryChecker()
                self.mc.start()
            stdout_path = os.path.join(self.output_dir, STDOUT_FILE)
            stderr_path = os.path.join(self.output_dir, STDERR_FILE)
            with open(stdout_path, "w") as out, open(stderr_path, "w") as err:
                for frame in self.extra_data['frames']:
                    blender_cmd = self._format_blender_cmd(frame)
                    firejail_cmd = self._format_firejail_cmd()
                    p = subprocess.run(firejail_cmd + blender_cmd,
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
            "--", f'GPU={self.rendering_engine.name}'
        ]
        return cmd

    def _format_firejail_cmd(self):
        return [
            FIREJAIL_COMMAND,
            f'--profile={self.profile_path}'
        ]

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

    def _prepare_firejail_profile(self):
        with open(FIREJAIL_PROFILE_TEMPLATE_PATH) as f:
            template = f.read()

        template %= {
            'blender_dir': BLENDER_DIR,
            'work_dir': self.work_dir,
            'resources_dir': self.res_path,
            'output_dir': self.output_dir
        }

        with open(self.profile_path, "w") as profile_file:
            profile_file.write(template)

    def _prepare_blender(self):
        if not os.path.isfile(BLENDER_BINARY_PATH):
            img = DockerImage(BLENDER_IMAGE_REP, tag=BLENDER_IMAGE_TAG)
            img.extract_path(DOCKER_BLENDER_PATH, BLENDER_DIR)
            # run blender with predefined task in order to load in
            # kernel modules for CUDA GPU. Must be done outside of firejail
            if self.rendering_engine == RenderingEngine.CUDA:
                _init_gpu_blender()

    def _get_script_path(self):
        return os.path.join(self.work_dir, SCRIPT_FILE_NAME)
