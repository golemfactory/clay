import os
import pathlib
import shutil

from apps.blender.blenderenvironment import BlenderEnvironment
from golem.core.common import get_golem_path
from golem.docker.job import DockerJob
from .test_docker_job import TestDockerJob


class TestBlenderDockerJob(TestDockerJob):
    """Tests for Docker image golem/base"""

    def _get_test_repository(self):
        return "golemfactory/blender"

    def _get_test_tag(self):
        return BlenderEnvironment.DOCKER_TAG

    def test_blender_job(self):
        # copy the scene file to the resources dir
        scene_file = pathlib.Path(get_golem_path())
        scene_file /= "apps/blender/benchmark/test_task/cube.blend"
        shutil.copy(str(scene_file), self.resources_dir)
        dest_scene_file = pathlib.PurePosixPath(DockerJob.RESOURCES_DIR)
        dest_scene_file /= scene_file.name
        start_task = 42

        crops = [
            {
                "outfilebasename": "out_{}".format(start_task),
                "borders_x": [0.0, 1.0],
                "borders_y": [0.0, 1.0]
            }
        ]
        params = {
            "scene_file": str(dest_scene_file),
            "resolution": [800, 600],
            "use_compositing": True,
            "samples": 5,
            "frames": [1],
            "output_format": "EXR",
            "start_task": start_task,
            "crops": crops
        }

        with self._create_test_job(
                script="/golem/entrypoints/render_entrypoint.py",
                params=params) as job:
            job.start()
            exit_code = job.wait(timeout=300)
            self.assertEqual(exit_code, 0)

        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ['out_420001.exr'])
