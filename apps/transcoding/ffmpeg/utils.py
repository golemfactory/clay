import json
import logging
import os
import shutil
from pathlib import Path
from typing import List, Tuple

from apps.transcoding import common
from apps.transcoding.common import ffmpegException, ffmpegExtractSplitError, \
    ffmpegMergeReplaceError
from apps.transcoding.ffmpeg.ffmpeg_docker_api import FfmpegDockerAPI
from golem.core.common import HandleError
from golem.docker.job import DockerJob
from golem.docker.task_thread import DockerDirMapping


logger = logging.getLogger(__name__)



class StreamOperator:
    @HandleError(ValueError, common.not_valid_json)
    def extract_video_streams_and_split(self, # noqa pylint: disable=too-many-locals
                                        input_file_on_host: str,
                                        parts: int,
                                        task_dir: str,
                                        task_id: str):

        directory_mapping = self._generate_split_dir_mapping(task_dir)

        ffmpeg_docker_api = FfmpegDockerAPI(directory_mapping)
        result, split_result_file = ffmpeg_docker_api.\
            extract_video_streams_and_split(
                input_file_on_host,
                parts
            )

        FfmpegDockerAPI.remove_split_intermediate_videos(directory_mapping)

        output_files = result.get('data', [])
        if split_result_file not in output_files:
            raise ffmpegExtractSplitError(
                f"Result file {split_result_file} does not exist")

        logger.debug('[task_id = %s] Split result file is = %s [parts = %d]',
                     task_id,
                     split_result_file,
                     parts)

        with open(split_result_file) as f:
            params = json.load(f)  # FIXME: check status of splitting
            if params.get('status', 'Success') != 'Success':
                raise ffmpegExtractSplitError('Splitting video failed')

            segments = params.get('segments', [])
            streams_list = [os.path.join(directory_mapping.output,
                                         segment.get('video_segment'))
                            for segment in segments]

            logger.info(
                "Stream %s has successfully passed the "
                "extract+split operation. Segments: %s",
                input_file_on_host,
                streams_list)

            return streams_list, params.get('metadata', {})

    def _prepare_merge_job(self,
                           task_dir: str,
                           chunks_on_host)->Tuple[DockerDirMapping, List[str]]:

        directory_mapping: DockerDirMapping = self._generate_dir_mapping(
            Path(task_dir) / "merge" / "resources",
            task_dir,
            "merge")

        chunks_in_container = self._collect_files(
            task_dir,
            chunks_on_host,
            directory_mapping.resources)

        return (directory_mapping, chunks_in_container)

    @staticmethod
    def _collect_files(directory: str,
                       files: List[str],
                       resources_dir: str) -> List[str]:

        # Each chunk must be in the same directory
        results = list()
        for file in files:
            if not os.path.isfile(file):
                raise ffmpegMergeReplaceError("Missing result file: {}".format(
                    file))
            if os.path.dirname(file) != directory:
                raise ffmpegMergeReplaceError("Result file: {} should be in "
                    "the proper directory: {}".format(file, directory))

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
    def merge_and_replace_video_streams(
            self,
            input_file_on_host,
            chunks_on_host,
            output_file_basename,
            task_dir,
            container,
            strip_unsupported_data_streams=False,
            strip_unsupported_subtitle_streams=False):

        assert os.path.isdir(task_dir), \
            "Caller is responsible for ensuring that task dir exists."
        assert os.path.isfile(input_file_on_host), \
            "Caller is responsible for ensuring that input file exists."

        # Temporary videos can take big amount of disk space.
        # If we got here, we have all segments already transcoded, so we
        # can remove them. Merge will produce some new temporary videos so we
        # need to remove split results as soon as posible, otherwise we can
        # exhaust disk space.
        self._remove_split_results(task_dir)
        self._remove_providers_results_zips(task_dir)

        (dir_mapping, chunks_in_container) = self._prepare_merge_job(
            task_dir,
            chunks_on_host)

        ffmpeg_docker_api = FfmpegDockerAPI(dir_mapping)
        _ = ffmpeg_docker_api.merge_and_replace_video_streams(
            input_file_on_host,
            chunks_in_container,
            output_file_basename,
            container,
            strip_unsupported_data_streams,
            strip_unsupported_subtitle_streams
        )

        FfmpegDockerAPI.remove_merge_intermediate_videos(dir_mapping)

        return os.path.join(dir_mapping.output, output_file_basename)

    @classmethod
    def _generate_dir_mapping(cls,
                              resource_dir: str,
                              task_dir: str,
                              subdir_name: str):
        directory_mapping = DockerDirMapping.generate(
            Path(resource_dir),
            Path(task_dir) / subdir_name)

        try:
            directory_mapping.mkdirs(exist_ok=True)
        except OSError:
            raise ffmpegMergeReplaceError(
                "Failed to prepare video merge directory structure")

        return directory_mapping

    @classmethod
    def _generate_split_dir_mapping(cls, task_dir: str):
        return cls._generate_dir_mapping(
            Path(task_dir) / "split" / "resources",  # This directory is unused
            task_dir,
            "split")

    @classmethod
    def _remove_split_results(cls, task_dir: str):
        dir_mapping = cls._generate_split_dir_mapping(task_dir)
        FfmpegDockerAPI.remove_split_output_videos(dir_mapping)

    @classmethod
    def _remove_providers_results_zips(cls, task_dir: str):
        FfmpegDockerAPI.remove_intermediate_videos(Path(task_dir), '*.zip')

    def get_metadata(self,
                     input_files: List[str],
                     resources_dir: str,
                     work_dir: str) -> dict:

        dir_mapping: DockerDirMapping = self._generate_dir_mapping(
            resources_dir,
            work_dir,
            "metadata")

        # Important: This function expects only one result file.
        # We can't add logs to output.
        dir_mapping.logs = dir_mapping.work

        assert os.path.isdir(resources_dir)
        assert all([
            os.path.isfile(os.path.join(resources_dir, input_file))
            for input_file in input_files
        ])

        metadata_requests = [{
            'video': input_file,
            'output': f'metadata-logs-{os.path.splitext(input_file)[0]}.json'
        } for input_file in input_files]

        ffmpeg_docker_api = FfmpegDockerAPI(dir_mapping)
        job_result = ffmpeg_docker_api.get_metadata(metadata_requests)

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
