from os import path

from apps.lux.benchmark.benchmark import LuxBenchmark
from apps.lux.task.luxrendertask import LuxRenderTaskBuilder
from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment
from golem.docker.job import DockerJob


class LuxRenderEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/luxrender"
    DOCKER_TAG = "1.2"
    ENV_ID = "LUXRENDER"
    APP_DIR = path.join(get_golem_path(), 'apps', 'lux')
    SCRIPT_NAME = "docker_luxtask.py"
    SHORT_DESCRIPTION = "LuxRender (www.luxrender.net)"

    def prepare_params(self, extra_data):
        if 'scene_dir' in extra_data:
            scene_dir = extra_data['scene_dir']
            scene_dir = DockerJob.get_absolute_resource_path(scene_dir)
            extra_data['scene_dir'] = path.dirname(scene_dir)
        return extra_data

    def get_benchmark(self):
        return LuxBenchmark(self), LuxRenderTaskBuilder
