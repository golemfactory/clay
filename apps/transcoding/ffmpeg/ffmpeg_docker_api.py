import enum
import json
import logging
import os
import shutil
import glob

from pathlib import Path
from typing import List, Optional, Tuple
from threading import Lock

from apps.transcoding import common
from apps.transcoding.common import ffmpegException, ffmpegExtractSplitError, \
    ffmpegMergeReplaceError
from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from golem.core.common import HandleError
from golem.docker.image import DockerImage
from golem.docker.job import DockerJob
from golem.docker.task_thread import DockerTaskThread, \
    DockerBind, DockerDirMapping
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

split_lock = Lock()


class Commands(enum.Enum):
    EXTRACT_AND_SPLIT = ('extract-and-split', 'extract-and-split-results.json')
    TRANSCODE = ('transcode', '')
    MERGE_AND_REPLACE = ('merge-and-replace', '')
    COMPUTE_METRICS = ('compute-metrics', '')




class FfmpegDockerAPI:

    def extract_video_streams_and_split(self,
                                        directory_mapping: DockerDirMapping,
                                        input_file_on_host: str,
                                        parts: int,
                                        remove_intermediate_videos=True):

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

        with split_lock:
            try:
                result = self._do_job_in_container(
                    directory_mapping,
                    extra_data,
                    env)
            except ffmpegException as exception:
                raise ffmpegExtractSplitError(str(exception)) from exception

        if remove_intermediate_videos:
            self._remove_split_intermediate_videos(directory_mapping)

        return result

    @classmethod
    def _removed_intermediate_video_placeholder(cls, filepath: Path):
        # This function creates placeholder after removing
        # intermediate file. It will be usefull for debugging.
        placeholder_name = filepath.with_suffix(".removed")
        Path(placeholder_name).touch()


    @classmethod
    def _remove_split_intermediate_videos(cls, dir_mapping: DockerDirMapping):
        pattern = '*{}'.format(glob.escape(VIDEO_ONLY_CONTAINER_SUFFIX))
        files_to_remove = list(Path(dir_mapping.work).glob(pattern))

        logger.info("Removing intermediate files: %s", files_to_remove)

        for file in files_to_remove:
            cls._removed_intermediate_video_placeholder(file)
            os.remove(file)

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
