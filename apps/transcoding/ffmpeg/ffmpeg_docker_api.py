import enum
import logging
import os
import glob

from pathlib import Path
from typing import List, Optional
from threading import Lock

from apps.transcoding.common import ffmpegException, ffmpegExtractSplitError, \
    ffmpegMergeReplaceError
from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from golem.docker.image import DockerImage
from golem.docker.job import DockerJob
from golem.docker.task_thread import DockerTaskThread, \
    DockerBind, DockerDirMapping
from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager


FFMPEG_DOCKER_IMAGE = ffmpegEnvironment.DOCKER_IMAGE
FFMPEG_DOCKER_TAG = ffmpegEnvironment.DOCKER_TAG
FFMPEG_BASE_SCRIPT = '/golem/scripts/ffmpeg_task.py'
FFMPEG_ENTRYPOINT = 'python3 ' + FFMPEG_BASE_SCRIPT
FFMPEG_RESULT_FILE = '/golem/scripts/ffmpeg_task.py'


# Suffix used to distinguish the temporary container that has no audio or data
# streams from a complete video
VIDEO_ONLY_CONTAINER_SUFFIX = '[video-only]'

logger = logging.getLogger(__name__)

docker_lock = Lock()


class Commands(enum.Enum):
    EXTRACT_AND_SPLIT = ('extract-and-split', 'extract-and-split-results.json')
    TRANSCODE = ('transcode', '')
    MERGE_AND_REPLACE = ('merge-and-replace', '')
    COMPUTE_METRICS = ('compute-metrics', '')


class FfmpegDockerAPI:

    def __init__(self, directory_mapping: DockerDirMapping):
        self.dir_mapping = directory_mapping

    def extract_video_streams_and_split(self,
                                        input_file_on_host: str,
                                        parts: int):

        input_file_basename = os.path.basename(input_file_on_host)

        # FIXME: This is a path on the host but docker will create it in
        # the container. It's unlikely that there's anything there but
        # it's not guaranteed.
        input_file_in_container = input_file_basename

        if not os.path.isabs(input_file_in_container):
            input_file_in_container = \
                "/input/{}".format(input_file_in_container)

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

        with docker_lock:
            try:
                results = self._do_job_in_container(
                    self.dir_mapping,
                    extra_data,
                    env)
            except ffmpegException as exception:
                raise ffmpegExtractSplitError(str(exception)) from exception

        return results, os.path.join(self.dir_mapping.output,
                                     Commands.EXTRACT_AND_SPLIT.value[1])

    # pylint: disable=too-many-arguments
    def merge_and_replace_video_streams(
            self,
            input_file_on_host,
            chunks_in_container,
            output_file_basename,
            container,
            strip_unsupported_data_streams=False,
            strip_unsupported_subtitle_streams=False):

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

        with docker_lock:
            try:
                results = self._do_job_in_container(
                    self.dir_mapping,
                    extra_data,
                    env)
            except ffmpegException as exception:
                raise ffmpegMergeReplaceError(str(exception)) from exception

        return results

    def get_metadata(self, metadata_requests: List[dict]):
        extra_data = {
            'entrypoint': FFMPEG_ENTRYPOINT,
            'command': Commands.COMPUTE_METRICS.value[0],
            'metrics_params': {
                'metadata': metadata_requests,
            },
        }

        logger.info('Obtaining video metadata.')
        logger.debug('Command params: %s', extra_data)
        logger.info('Directories: work %s', self.dir_mapping.work)

        return self._do_job_in_container(self.dir_mapping, extra_data)

    @staticmethod
    def _do_job_in_container(dir_mapping: DockerDirMapping,
                             extra_data: dict,
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

    @classmethod
    def _removed_intermediate_video_placeholder(cls, filepath: Path):
        # This function creates placeholder after removing
        # intermediate file. It will be usefull for debugging.
        placeholder_name = filepath.with_suffix(".removed")
        Path(placeholder_name).touch()

    @classmethod
    def remove_intermediate_videos(cls, directory: Path, pattern: str):

        files_to_remove = list(Path(directory).glob(pattern))
        logger.debug("Removing intermediate files: %s", files_to_remove)

        for file in files_to_remove:
            cls._removed_intermediate_video_placeholder(file)
            os.remove(file)

    @classmethod
    def remove_split_intermediate_videos(cls, dir_mapping: DockerDirMapping):
        pattern = '*{}'.format(glob.escape(VIDEO_ONLY_CONTAINER_SUFFIX))
        cls.remove_intermediate_videos(dir_mapping.work, pattern)

    @classmethod
    def remove_split_output_videos(cls, dir_mapping: DockerDirMapping):
        pattern = '*{}_*'.format(glob.escape(VIDEO_ONLY_CONTAINER_SUFFIX))
        cls.remove_intermediate_videos(dir_mapping.output, pattern)

    @classmethod
    def remove_merge_intermediate_videos(cls, dir_mapping: DockerDirMapping):
        # Remove merged video without additional streams.
        pattern = '*{}*'.format(glob.escape(VIDEO_ONLY_CONTAINER_SUFFIX))
        cls.remove_intermediate_videos(dir_mapping.work, pattern)

        # Remove video segments from resource directory.
        pattern = '*{}_*'.format(glob.escape(VIDEO_ONLY_CONTAINER_SUFFIX))
        cls.remove_intermediate_videos(dir_mapping.resources, pattern)
