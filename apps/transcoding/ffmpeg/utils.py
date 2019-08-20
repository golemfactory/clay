import enum
import json
import logging
import os
from pathlib import Path
import shutil
from typing import List, Optional

from apps.transcoding import common
from apps.transcoding.common import ffmpegException, ffmpegExtractSplitError, \
    ffmpegMergeReplaceError
from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from golem.core.common import HandleError
from golem.docker.image import DockerImage
from golem.docker.job import DockerJob
from golem.docker.task_thread import DockerTaskThread, DockerBind
from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.resource.dirmanager import DirManager

FFMPEG_DOCKER_IMAGE = ffmpegEnvironment.DOCKER_IMAGE
FFMPEG_DOCKER_TAG = ffmpegEnvironment.DOCKER_TAG
FFMPEG_BASE_SCRIPT = '/golem/scripts/ffmpeg_task.py'
FFMPEG_ENTRYPOINT = 'python3 ' + FFMPEG_BASE_SCRIPT
FFMPEG_RESULT_FILE = '/golem/scripts/ffmpeg_task.py'

# Suffix used to distinguish the temporary container that has no audio or data
# streams from a complete video
VIDEO_ONLY_CONTAINER_SUFFIX = '[video-only]'

logger = logging.getLogger(__name__)


class Commands(enum.Enum):
    EXTRACT_AND_SPLIT = ('extract-and-split', 'extract-and-split-results.json')
    TRANSCODE = ('transcode', '')
    MERGE_AND_REPLACE = ('merge-and-replace', '')
    COMPUTE_METRICS = ('compute-metrics', '')


class StreamOperator:
    @HandleError(ValueError, common.not_valid_json)
    def extract_video_streams_and_split(self, # noqa pylint: disable=too-many-locals
                                        input_file_on_host: str,
                                        parts: int,
                                        dir_manager: DirManager,
                                        task_id: str):

        host_dirs = {
            'tmp': dir_manager.get_task_temporary_dir(task_id),
            'output': dir_manager.get_task_output_dir(task_id),
        }

        input_file_basename = os.path.basename(input_file_on_host)
        input_file_in_container = os.path.join(
            # FIXME: This is a path on the host but docker will create it in
            # the container. It's unlikely that there's anything there but
            # it's not guaranteed.
            host_dirs['tmp'],
            input_file_basename)

        # FIXME: The environment is stored globally. Changing it will affect
        # containers started by other functions that do not do it themselves.
        env = ffmpegEnvironment(binds=[DockerBind(
            Path(input_file_on_host),
            input_file_in_container,
            'ro')])

        extra_data = {
            'entrypoint': FFMPEG_ENTRYPOINT,
            'command': Commands.EXTRACT_AND_SPLIT.value[0],
            'input_file': input_file_in_container,
            'parts': parts,
        }

        logger.debug(
            'Running video stream extraction and splitting '
            '[params = %s]',
            extra_data)
        try:
            result = self._do_job_in_container(
                self._get_dir_mapping(dir_manager, task_id),
                extra_data,
                env)
        except ffmpegException as exception:
            raise ffmpegExtractSplitError(str(exception)) from exception

        split_result_file = os.path.join(host_dirs['output'],
                                         Commands.EXTRACT_AND_SPLIT.value[1])
        output_files = result.get('data', [])
        if split_result_file not in output_files:
            raise ffmpegExtractSplitError(
                f"Result file {split_result_file} does not exist")

        logger.debug('Split result file is = %s [parts = %d]',
                     split_result_file,
                     parts)

        with open(split_result_file) as f:
            params = json.load(f)  # FIXME: check status of splitting
            if params.get('status', 'Success') != 'Success':
                raise ffmpegExtractSplitError('Splitting video failed')

            streams_list = list(map(
                lambda x: x.get('video_segment'),
                params.get('segments', [])))
            logger.info(
                "Stream %s has successfully passed the "
                "extract+split operation. Segments: %s",
                input_file_on_host,
                streams_list)
            return streams_list, params.get('metadata', {})

    def _prepare_merge_job(self, task_dir, chunks_on_host):
        host_dirs = {
            'resources': os.path.join(task_dir, 'merge', 'resources'),
            'temporary': os.path.join(task_dir, 'merge', 'work'),
            'work': os.path.join(task_dir, 'merge', 'work'),
            'output': os.path.join(task_dir, 'merge', 'output'),
            'logs': os.path.join(task_dir, 'merge', 'output'),
        }

        try:
            os.makedirs(host_dirs['resources'])
            os.makedirs(host_dirs['output'])
            os.makedirs(host_dirs['work'])
        except OSError:
            raise ffmpegMergeReplaceError(
                "Failed to prepare video merge directory structure")
        chunks_in_container = self._collect_files(
            task_dir, chunks_on_host,
            host_dirs['resources'])

        return (host_dirs, chunks_in_container)

    @staticmethod
    def _collect_files(directory, files, resources_dir):
        # each chunk must be in the same directory
        results = list()
        for file in files:
            if not os.path.isfile(file):
                raise ffmpegMergeReplaceError("Missing result file: {}".format(
                    file))
            if os.path.dirname(file) != directory:
                raise ffmpegMergeReplaceError("Result file: {} should be in \
                    the proper directory: {}".format(file, directory))

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

    # pylint: disable=too-many-arguments
    def merge_and_replace_video_streams(self,
                                        input_file_on_host,
                                        chunks_on_host,
                                        output_file_basename,
                                        task_dir,
                                        container,
                                        strip_unsupported_data_streams=False,
                                        strip_unsupported_subtitle_streams=
                                        False):

        assert os.path.isdir(task_dir), \
            "Caller is responsible for ensuring that task dir exists."
        assert os.path.isfile(input_file_on_host), \
            "Caller is responsible for ensuring that input file exists."

        (host_dirs, chunks_in_container) = self._prepare_merge_job(
            task_dir,
            chunks_on_host)

        container_files = {
            # FIXME: /golem/tmp should not be hard-coded.
            'in': os.path.join(
                '/golem/tmp',
                os.path.basename(input_file_on_host)),
            'out': os.path.join(DockerJob.OUTPUT_DIR, output_file_basename),
        }
        extra_data = {
            'entrypoint': FFMPEG_ENTRYPOINT,
            'command': Commands.MERGE_AND_REPLACE.value[0],
            'input_file': container_files['in'],
            'chunks': chunks_in_container,
            'output_file': container_files['out'],
            'container': container.value if container is not None else None,
            'strip_unsupported_data_streams': strip_unsupported_data_streams,
            'strip_unsupported_subtitle_streams':
                strip_unsupported_subtitle_streams
        }

        logger.debug('Merge and replace params: %s', extra_data)

        # FIXME: The environment is stored globally. Changing it will affect
        # containers started by other functions that do not do it themselves.
        env = ffmpegEnvironment(binds=[DockerBind(
            Path(input_file_on_host),
            container_files['in'],
            'ro')])

        try:
            self._do_job_in_container(
                DockerTaskThread.specify_dir_mapping(**host_dirs),
                extra_data,
                env)
        except ffmpegException as exception:
            raise ffmpegMergeReplaceError(str(exception)) from exception

        return os.path.join(host_dirs['output'], output_file_basename)

    @staticmethod
    def _do_job_in_container(dir_mapping, extra_data: dict,
                             env: Optional[Environment] = None,
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

    def get_metadata(self,
                     input_files: List[str],
                     resources_dir: str,
                     work_dir: str,
                     output_dir: str) -> dict:

        assert os.path.isdir(resources_dir)
        assert all([
            os.path.isfile(os.path.join(resources_dir, input_file))
            for input_file in input_files
        ])

        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError:
            raise ffmpegException(
                "Failed to prepare directory structure for get_metadata")

        metadata_requests = [{
            'video': input_file,
            'output': f'metadata-logs-{os.path.splitext(input_file)[0]}.json'
        } for input_file in input_files]

        extra_data = {
            'entrypoint': FFMPEG_ENTRYPOINT,
            'command': Commands.COMPUTE_METRICS.value[0],
            'metrics_params': {
                'metadata': metadata_requests,
            },
        }

        dir_mapping = DockerTaskThread.specify_dir_mapping(
            output=output_dir,
            temporary=work_dir,
            resources=resources_dir,
            logs=work_dir,
            work=work_dir)

        logger.info('Obtaining video metadata.')
        logger.debug('Command params: %s', extra_data)

        job_result = self._do_job_in_container(dir_mapping, extra_data)
        if 'data' not in job_result:
            raise ffmpegException(
                "Failed to obtain video metadata. "
                "'data' not found in the returned JSON.")

        if len(job_result['data']) < len(input_files):
            raise ffmpegException(
                "Failed to obtain video metadata. "
                "Missing output for at least one input file.")

        if len(job_result['data']) > len(input_files):
            raise ffmpegException(
                "Failed to obtain video metadata. Too many results.")

        logger.info('Video metadata obtained successfully!')
        return job_result
