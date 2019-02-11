import enum
import json
import logging
import os
from pathlib import Path

from apps.transcoding import common
from apps.transcoding.common import ffmpegException
from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from golem.core.common import HandleError
from golem.docker.task_thread import DockerTaskThread, DockerBind
from golem.docker.image import DockerImage
from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.resource.dirmanager import DirManager

FFMPEG_DOCKER_IMAGE = 'golemfactory/ffmpeg'
FFMPEG_DOCKER_TAG = '1.0'
FFMPEG_BASE_SCRIPT = '/golem/scripts/ffmpeg_task.py'
FFMPEG_RESULT_FILE = '/golem/scripts/ffmpeg_task.py'


logger = logging.getLogger(__name__)


class Commands(enum.Enum):
    SPLIT = ('split', 'split-results.json')
    TRANSCODE = ('transcode', '')


class StreamOperator:
    @HandleError(ValueError, common.not_valid_json)
    def split_video(self, input_stream: str, parts: int,
                    dir_manager: DirManager, task_id: str):
        name = os.path.basename(input_stream)
        tmp_task_dir = dir_manager.get_task_temporary_dir(task_id)
        stream_container_path = os.path.join(tmp_task_dir, name)
        task_output_dir = dir_manager.get_task_output_dir(task_id)
        env = ffmpegEnvironment(binds=[
            DockerBind(Path(input_stream), stream_container_path, 'ro')])
        extra_data = {
            'script_filepath': FFMPEG_BASE_SCRIPT,
            'command': Commands.SPLIT.value[0],
            'path_to_stream': stream_container_path,
            'parts': parts
        }
        logger.debug('Running video splitting [params = {}]'.format(extra_data))

        result = self._do_job_in_container(dir_manager, task_id, extra_data,
                                           env)
        split_result_file = os.path.join(task_output_dir,
                                         Commands.SPLIT.value[1])
        output_files = result.get('data', [])
        if split_result_file not in output_files:
            raise ffmpegException('Result file {} does not exist'.
                                  format(split_result_file))
        logger.debug('Split result file is = {} [parts = {}]'.
                     format(split_result_file, parts))
        with open(split_result_file) as f:
            params = json.load(f)  # FIXME: check status of splitting
            if params.get('status', 'Success') is not 'Success':
                raise ffmpegException('Splitting video failed')
            streams_list = list(map(lambda x: (x.get('video_segment'),
                                          x.get('playlist')),
                               params.get('segments', [])))
            logger.info('Stream {} was successfully splitted to {}'
                        .format(input_stream, streams_list))
            return streams_list

    def _do_job_in_container(self, dir_manager: DirManager, task_id: str,
                             extra_data: dict, env: Environment = None,
                             timeout: int = 120):

        if env:
            EnvironmentsManager().add_environment(env)

        dtt = DockerTaskThread(docker_images=[DockerImage(
            repository=FFMPEG_DOCKER_IMAGE, tag=FFMPEG_DOCKER_TAG)],
            extra_data=extra_data,
            dir_mapping=self._get_dir_mapping(dir_manager, task_id),
            timeout=timeout)

        dtt.run()
        if dtt.error:
            raise ffmpegException(dtt.error_msg)
        return dtt.result[0] if isinstance(dtt.result, tuple) else dtt.result

    def _get_dir_mapping(self, dir_manager: DirManager, task_id: str):
        tmp_task_dir = dir_manager.get_task_temporary_dir(task_id)
        resources_task_dir = dir_manager.get_task_resource_dir(task_id)
        task_output_dir = dir_manager.get_task_output_dir(task_id)

        return DockerTaskThread.specify_dir_mapping(
            output=task_output_dir, temporary=tmp_task_dir,
            resources=resources_task_dir, logs=tmp_task_dir, work=tmp_task_dir)


