from os import path

from apps.blender.benchmark.benchmark import BlenderBenchmark
from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder
from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment
from golem.docker.job import DockerJob


class BlenderEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/blender"
    DOCKER_TAG = "1.4"
    ENV_ID = "BLENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'blender',
                        'dockerenvironment')
    SCRIPT_NAME = "docker_blendertask.py"
    SHORT_DESCRIPTION = "Blender (www.blender.org)"

    def prepare_params(self, extra_data):
        scene_file = extra_data['scene_file']
        scene_file = DockerJob.get_absolute_resource_path(scene_file)
        extra_data['scene_file'] = scene_file
        return extra_data

    def get_benchmark(self):
        return BlenderBenchmark(self), BlenderRenderTaskBuilder
