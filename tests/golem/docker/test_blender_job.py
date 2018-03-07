import os
import pathlib
import shutil

from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.core.common import get_golem_path
from golem.docker.job import DockerJob
from golem.resource.dirmanager import find_task_script
from .test_docker_job import TestDockerJob


class TestBlenderDockerJob(TestDockerJob):
    """Tests for Docker image golem/base"""

    def _get_test_repository(self):
        return "golemfactory/blender"

    def _get_test_tag(self):
        return "1.4"

    def test_blender_job(self):
        app_dir = os.path.join(get_golem_path(), "apps", "blender")
        task_script = find_task_script(app_dir, "docker_blendertask.py")
        with open(task_script) as f:
            task_script_src = f.read()

        # prepare dummy crop script
        crop_script_contents = generate_blender_crop_file(
            resolution=(800, 600),
            borders_x=(0, 1),
            borders_y=(0, 1),
            use_compositing=True,
        )

        # copy the scene file to the resources dir
        scene_file = pathlib.Path(get_golem_path())
        scene_file /= "apps/blender/benchmark/test_task/cube.blend"
        shutil.copy(str(scene_file), self.resources_dir)
        dest_scene_file = pathlib.PurePosixPath(DockerJob.RESOURCES_DIR)
        dest_scene_file /= scene_file.name

        params = {
            "outfilebasename": "out",
            "scene_file": str(dest_scene_file),
            "script_src": crop_script_contents,
            "start_task": 42,
            "end_task": 42,
            "output_format": "EXR",
            "frames": [1],
        }

        with self._create_test_job(script=task_script_src, params=params) as job:  # noqa
            job.start()
            exit_code = job.wait()
            self.assertEqual(exit_code, 0)

        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ['out_420001.exr'])
