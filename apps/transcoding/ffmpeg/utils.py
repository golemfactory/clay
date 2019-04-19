import enum
import json
import logging
import os
from pathlib import Path
import shutil

from apps.transcoding import common
from apps.transcoding.common import ffmpegException
from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from golem.core.common import HandleError
from golem.docker.image import DockerImage
from golem.docker.job import DockerJob
from golem.docker.task_thread import DockerTaskThread, DockerBind
from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.resource.dirmanager import DirManager

FFMPEG_DOCKER_IMAGE = 'golemfactory/ffmpeg-experimental'
FFMPEG_DOCKER_TAG = '0.94'
FFMPEG_BASE_SCRIPT = '/golem/scripts/ffmpeg_task.py'
FFMPEG_ENTRYPOINT = 'python3 ' + FFMPEG_BASE_SCRIPT
FFMPEG_RESULT_FILE = '/golem/scripts/ffmpeg_task.py'

logger = logging.getLogger(__name__)


class Commands(enum.Enum):
    SPLIT = ('split', 'split-results.json')
    TRANSCODE = ('transcode', '')
    MERGE = ('merge', '')


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
            'entrypoint': FFMPEG_ENTRYPOINT,
            'command': Commands.SPLIT.value[0],
            'path_to_stream': stream_container_path,
            'parts': parts
        }
        logger.debug('Running video splitting [params = {}]'.\
            format(extra_data))

        result = self._do_job_in_container(
            self._get_dir_mapping(dir_manager, task_id),
            extra_data, env)

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
            if params.get('status', 'Success') != 'Success':
                raise ffmpegException('Splitting video failed')

            streams_list = list(map(lambda x: (x.get('video_segment'),
                                               x.get('playlist')),
                                    params.get('segments', [])))

            logger.info('Stream {} was successfully split to {}'
                        .format(input_stream, streams_list))

            return streams_list, params.get('metadata', {})

    def _prepare_merge_job(self, task_dir, chunks):
        try:
            resources_dir = os.path.join(task_dir, 'merge', 'resources')
            os.makedirs(resources_dir)
            output_dir = os.path.join(task_dir, 'merge', 'output')
            os.makedirs(output_dir)
            work_dir = os.path.join(task_dir, 'merge', 'work')
            os.makedirs(work_dir)
        except OSError:
            raise ffmpegException("Failed to prepare video \
                merge directory structure")
        files = self._collect_files(task_dir, chunks, resources_dir)
        return resources_dir, output_dir, work_dir, files

    @staticmethod
    def _collect_files(directory, files, resources_dir):
        # each chunk must be in the same directory
        results = list()
        for file in files:
            if not os.path.isfile(file):
                raise ffmpegException("Missing result file: {}".format(file))
            if os.path.dirname(file) != directory:
                raise ffmpegException("Result file: {} should be in the \
                proper directory: {}".format(file, directory))

            results.append(file)

        # Copy files to docker resources directory
        os.makedirs(resources_dir, exist_ok=True)

        for result in results:
            result_filename = os.path.basename(result)
            target_filepath = os.path.join(resources_dir, result_filename)
            shutil.move(result, target_filepath)

        # Translate paths to docker filesystem
        return [
            path.replace(directory, DockerJob.RESOURCES_DIR)
            for path in results
        ]

    def merge_video(self, filename, task_dir, chunks):
        resources_dir, output_dir, work_dir, chunks = \
            self._prepare_merge_job(task_dir, chunks)

        extra_data = {
            'entrypoint': FFMPEG_ENTRYPOINT,
            'command': Commands.MERGE.value[0],
            'output_stream': os.path.join(DockerJob.OUTPUT_DIR, filename),
            'chunks': chunks,
        }

        logger.debug('Merge params: {}'.format(extra_data))

        dir_mapping = DockerTaskThread.specify_dir_mapping(
            output=output_dir,
            temporary=work_dir,
            resources=resources_dir,
            logs=output_dir,
            work=work_dir)

        self._do_job_in_container(dir_mapping, extra_data)
        return os.path.join(output_dir, filename)

    @staticmethod
    def _do_job_in_container(dir_mapping, extra_data: dict,
                             env: Environment = None,
                             timeout: int = 120):

        if env:
            EnvironmentsManager().add_environment(env)

        dtt = DockerTaskThread(
            docker_images=[
                DockerImage(
                    repository=FFMPEG_DOCKER_IMAGE,
                    tag=FFMPEG_DOCKER_TAG
                )
            ],
            extra_data=extra_data,
            dir_mapping=dir_mapping,
            timeout=timeout
        )

        dtt.run()
        if dtt.error:
            raise ffmpegException(dtt.error_msg)
        return dtt.result[0] if isinstance(dtt.result, tuple) else dtt.result

    @staticmethod
    def _get_dir_mapping(dir_manager: DirManager, task_id: str):
        tmp_task_dir = dir_manager.get_task_temporary_dir(task_id)
        resources_task_dir = dir_manager.get_task_resource_dir(task_id)
        task_output_dir = dir_manager.get_task_output_dir(task_id)

        return DockerTaskThread. \
            specify_dir_mapping(output=task_output_dir,
                                temporary=tmp_task_dir,
                                resources=resources_task_dir,
                                logs=tmp_task_dir,
                                work=tmp_task_dir)

    @staticmethod
    def _specify_dir_mapping(output, temporary, resources, logs, work):
        return DockerTaskThread.specify_dir_mapping(output=output,
                                                    temporary=temporary,
                                                    resources=resources,
                                                    logs=logs, work=work)
