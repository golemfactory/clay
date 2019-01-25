import enum
import json
import os

from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from golem.docker.task_thread import DockerTaskThread
from golem.docker.image import DockerImage
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.resource.dirmanager import DirManager

FFMPEG_DOCKER_IMAGE = 'golemfactory/ffmpeg'
FFMPEG_DOCKER_TAG = '1.0'
FFMPEG_BASE_SCRIPT = '/golem/scripts/ffmpeg_task.py'
FFMPEG_RESULT_FILE = '/golem/scripts/ffmpeg_task.py'


class Commands(enum.Enum):
    SPLIT = ('split', 'split-results.json')


class StreamOperator:
    def __init__(self):
        self.environment_manager = EnvironmentsManager()
        self.env = ffmpegEnvironment()

    def _add_binding_to_container(self, left, right, mode='ro'):
        self.env.add_binding(left, right, mode)
        self.environment_manager.add_environment(self.env) # POPRAWIC

    def split_video(self, input_stream, parts, dir_manager: DirManager, task_id):
        name = os.path.basename(input_stream)
        tmp_task_dir = dir_manager.get_task_temporary_dir(task_id)
        resources_task_dir = dir_manager.get_task_resource_dir(task_id)
        # do kwargs to cos
        task_output_dir = dir_manager.get_task_output_dir(task_id)
        stream_container_path = os.path.join(tmp_task_dir, name)
        self._add_binding_to_container(input_stream, stream_container_path)
        extra_data = {
            'script_filepath': FFMPEG_BASE_SCRIPT,
            'command': Commands.SPLIT,
            'path_to_stream': stream_container_path,
            'parts': parts
        }
        dir_mapping = DockerTaskThread.specify_dir_mapping(output=dir_manager.get_task_output_dir(task_id),
            temporary=tmp_task_dir, resources=resources_task_dir)

        dtt = DockerTaskThread(docker_images=[DockerImage(
            repository=FFMPEG_DOCKER_IMAGE, tag=FFMPEG_DOCKER_TAG)],
            extra_data=extra_data,
            dir_mapping=dir_mapping, timeout=1024)  # TIMEOUT!!

        dtt.run()
        if dtt.error:
            raise ffmpegException(dtt.error_msg)
        result = dtt.result[0] if isinstance(dtt.result, tuple) else dtt.result
        split_result_file = os.path.join(task_output_dir, Commands.SPLIT[1])
        output_files = result.get('data', [])
        if split_result_file not in output_files:
            raise ffmpegException('Result file {} does not exist'.format(split_result_file))

        # REMOVE BINDING

        with open(split_result_file) as f:
            # obsluga ze nieporawny json
            params = json.loads(f)  # wait for status implementation
            if(params.get('status', 'Success') is not 'Success'):
                raise ffmpegException()
            return map(lambda x: x.get('video_segment'), params.get('segments', []))


class ffmpegException(Exception):
    pass
