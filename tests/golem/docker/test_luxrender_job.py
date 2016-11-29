import os
from os import path
import shutil

from gnr.renderingdirmanager import find_task_script
from golem.core.common import get_golem_path

from test_docker_job import TestDockerJob


class TestLuxRenderDockerJob(TestDockerJob):
    """Tests for Docker image golem/base"""

    def _get_test_repository(self):
        return "golem/luxrender"

    def test_luxrender_job(self):
        lux_task_file = path.join(get_golem_path(), "apps", "lux", "task", "luxtask.py")
        task_script = find_task_script(lux_task_file, "docker_luxtask.py")

        with open(task_script) as f:
            task_script_src = f.read()

        # read the scene file and copy the resources to the resources dir
        lux_task_dir = path.join(get_golem_path(),
                                 "apps", "lux", "benchmark", "test_task")
        scene_src = None
        for f in os.listdir(lux_task_dir):
            task_file = path.join(lux_task_dir, f)
            if path.isfile(task_file) and task_file.endswith(".lxs"):
                if scene_src is not None:
                    self.fail("Multiple .lxs files found in {}"
                              .format(lux_task_dir))
                with open(task_file, "r") as scene_file:
                    scene_src = scene_file.read()
            elif path.isdir(task_file):
                shutil.copytree(task_file, path.join(self.resources_dir, f))

        if scene_src is None:
            self.fail("No .lxs files found in {}".format(lux_task_dir))

        params = {
            "outfilebasename": "out",
            "output_format": "png",
            "scene_file_src": scene_src,
            "start_task": 42,
            "end_task": 42,
            "frames": [1],
            "scene_dir": "/golem/resources/",
            "num_threads": 1
        }

        with self._create_test_job(script=task_script_src, params=params) as job:
            job.start()
            exit_code = job.wait()
            self.assertEqual(exit_code, 0)

        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ['out42.png'])




