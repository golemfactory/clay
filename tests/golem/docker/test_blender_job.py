import glob
import os
import shutil
from os import path

from gnr.renderingdirmanager import find_task_script
from golem.core.common import get_golem_path
from golem.docker.job import DockerJob
from test_docker_job import TestDockerJob


class TestBlenderDockerJob(TestDockerJob):
    """Tests for Docker image golem/base"""

    def _get_test_repository(self):
        return "golem/blender"

    def test_blender_job(self):
        task_script = find_task_script("docker_blendertask.py")
        with open(task_script) as f:
            task_script_src = f.read()

        # copy the blender script to the resources dir
        crop_script = find_task_script("blendercrop.py")
        with open(crop_script, 'r') as src:
            crop_script_src = src.read()

        # copy the scene file to the resources dir
        benchmarks_dir = path.join(get_golem_path(),
                                   path.normpath("apps/blender/benchmark/"))
        scene_files = glob.glob(path.join(benchmarks_dir, "**/*.blend"))
        if len(scene_files) == 0:
            self.fail("No .blend files available")
        shutil.copy(scene_files[0], self.resources_dir)

        params = {
            "outfilebasename": "out",
            "scene_file": DockerJob.RESOURCES_DIR + "/" +
                          path.basename(scene_files[0]),
            "script_src": crop_script_src,
            "start_task": 42,
            "end_task": 42,
            "output_format": "EXR",
            "frames": [1],
        }

        with self._create_test_job(script=task_script_src, params=params) as job:
            job.start()
            exit_code = job.wait()
            self.assertEqual(exit_code, 0)

        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ['out_420001.exr'])

