import glob
import os
import shutil
from os import path

from golem.core.common import get_golem_path
from golem.docker.job import DockerJob
from golem.resource.dirmanager import find_task_script
from golem.tools.ci import ci_skip
from test_docker_job import TestDockerJob


@ci_skip
class TestBlenderDockerJob(TestDockerJob):
    """Tests for Docker image golem/base"""

    def _get_test_repository(self):
        return "golemfactory/blender"

    def _get_test_tag(self):
        return "1.3"

    def test_blender_job(self):
        app_dir = os.path.join(get_golem_path(), "apps", "blender")
        task_script = find_task_script(app_dir, "docker_blendertask.py")
        with open(task_script) as f:
            task_script_src = f.read()

        # prepare dummy crop script
        from apps.blender.resources.scenefileeditor import generate_blender_crop_file
        crop_script_contents = generate_blender_crop_file(
            resolution=(800, 600),
            borders_x=(0, 1),
            borders_y=(0, 1),
            use_compositing=True,
        )

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
            "script_src": crop_script_contents,
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

