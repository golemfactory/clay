import os
import tempfile
from typing import Any, Dict, Optional, Tuple

from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container

from tests.apps.ffmpeg.task.utils.ffprobe_report import FfprobeFormatReport, \
    FileExcludes, FileOverrides, fuzzy_int_if_possible, parse_ffprobe_frame_rate
from tests.apps.ffmpeg.task.utils.ffprobe_report_set import FfprobeReportSet


class SimulatedTranscodingOperation:
    def __init__(self,
                 task_executor,
                 experiment_name: str,
                 resource_dir: str,
                 tmp_dir: str,
                 dont_include_in_option_description: Optional[list] = None)\
            -> None:
        # task_executor is an object with execute_task(task_def) method
        assert hasattr(task_executor, 'execute_task')
        assert os.path.isdir(resource_dir)
        assert os.path.isdir(tmp_dir)

        self._task_executor = task_executor
        self._experiment_name: str = experiment_name
        self._host_dirs: Dict[str, str] = {
            'resource': resource_dir,
            'tmp': tmp_dir,
        }
        self._dont_include_in_option_description = (
            dont_include_in_option_description
            if dont_include_in_option_description is not None
            else []
        )
        self._diff_overrides: FileOverrides = {}
        self._diff_excludes: FileExcludes = {}
        self._video_options: Dict[str, Any] = {}
        self._task_options: Dict[str, Any] = {
            'output_container': None,
            'subtasks_count': 2,
        }
        self._ffprobe_report_set: Optional[FfprobeReportSet] = None

    def set_override(self, location, attribute, value):
        if location not in self._diff_overrides:
            self._diff_overrides[location] = {}

        self._diff_overrides[location][attribute] = value

    def attach_to_report_set(self, report_set: FfprobeReportSet):
        self._ffprobe_report_set = report_set

    def request_container_change(self, new_container: Container):
        self._task_options['output_container'] = new_container

        format_name = new_container.get_demuxer()
        self.set_override('format', 'format_name', format_name)

    def request_video_codec_change(self, new_codec: VideoCodec):
        self._video_options['codec'] = new_codec.value
        self.set_override('video', 'codec_name', new_codec.value)

    def request_video_bitrate_change(self, new_bitrate: str):
        self._video_options['bit_rate'] = new_bitrate
        self.set_override(
            'video',
            'bitrate',
            fuzzy_int_if_possible(new_bitrate, 5),
        )

    def request_resolution_change(self, new_resolution: Tuple[int, int]):
        self._video_options['resolution'] = new_resolution
        self.set_override('video', 'resolution', new_resolution)

    def request_frame_rate_change(self, new_frame_rate: str):
        self._video_options['frame_rate'] = new_frame_rate
        self.set_override(
            'video',
            'frame_rate',
            parse_ffprobe_frame_rate(new_frame_rate),
        )

    def request_subtasks_count(self, new_subtask_count: int):
        self._task_options['subtasks_count'] = new_subtask_count

    def exclude_from_diff(self, exclude: FileExcludes):
        for location, attributes in exclude.items():
            self._diff_excludes[location] = (
                self._diff_excludes.get(location, set()) |
                attributes
            )

    def _build_option_description(self):
        if self._task_options['output_container'] is not None:
            container = self._task_options['output_container'].value
        else:
            container = None

        if 'resolution' in self._video_options:
            resolution = "{}x{}".format(
                self._video_options['resolution'][0],
                self._video_options['resolution'][1],
            )
        else:
            resolution = None

        if 'subtasks_count' in self._task_options:
            subtasks = f"{self._task_options['subtasks_count']}seg"
        else:
            subtasks = None

        components = {
            'video_codec': self._video_options.get('codec', None),
            'container': container,
            'resolution': resolution,
            'frame_rate': self._video_options.get('frame_rate', None),
            'bitrate': self._video_options.get('bit_rate', None),
            'subtasks_count': subtasks,
        }
        assert any(components.values())
        return "/".join(
            str(value)
            for name, value in components.items()
            if value is not None and name not in
            self._dont_include_in_option_description
        )

    @classmethod
    def _build_task_def(cls,
                        video_file: str,
                        result_file: str,
                        container: Container,
                        video_options: Dict[str, str],
                        subtasks_count: int) -> dict:
        return {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': subtasks_count,
            'bid': 1.0,
            'resources': [video_file],
            'options': {
                'output_path': os.path.dirname(result_file),
                'video': video_options if video_options is not None else {},
                'container': container.value if container is not None else None,
            }
        }

    def _build_file_names(self, relative_input_file: str):
        if self._task_options['output_container'] is not None:
            output_extension = "." +\
                               self._task_options['output_container'].value
        else:
            output_extension = os.path.splitext(relative_input_file)[1]

        input_file = os.path.join(
            self._host_dirs['resource'],
            relative_input_file,
        )
        input_file_stem = os.path.splitext(relative_input_file)[0]
        output_file = os.path.join(
            self._host_dirs['tmp'],
            f"transcoded-{input_file_stem}{output_extension}",
        )

        return (input_file, output_file)

    def _build_result_diff(self,
                           input_file: str,
                           output_file: str) -> \
            Tuple[FfprobeFormatReport, FfprobeFormatReport, dict]:

        assert os.path.isfile(input_file)
        assert os.path.isfile(output_file)

        tmp_metadata_dir = tempfile.mkdtemp(
            prefix='metadata',
            dir=self._host_dirs['tmp']
        )
        (input_report, output_report) = FfprobeFormatReport.build(  # pylint: disable=unbalanced-tuple-unpacking
            tmp_metadata_dir,
            [input_file, output_file]
        )
        return (
            input_report,
            output_report,
            output_report.diff(
                input_report,
                self._diff_overrides,
                self._diff_excludes,
            ),
        )

    def run(self, relative_input_file: str) -> \
            Tuple[FfprobeFormatReport, FfprobeFormatReport, dict]:
        try:
            (input_file, output_file) = self._build_file_names(
                relative_input_file)
            task_def = self._build_task_def(
                input_file,
                output_file,
                self._task_options['output_container'],
                self._video_options,
                self._task_options['subtasks_count'],
            )

            self._task_executor.execute_task(task_def)

            (input_report, output_report, diff) = self._build_result_diff(
                input_file,
                output_file,
            )
        except BaseException as exception:
            if self._ffprobe_report_set is not None:
                self._ffprobe_report_set.collect_error(
                    type(exception).__name__,
                    experiment_name=self._experiment_name,
                    video_file=relative_input_file,
                    input_value=self._build_option_description(),
                )
            raise
        else:
            if self._ffprobe_report_set is not None:
                self._ffprobe_report_set.collect_reports(
                    diff,
                    experiment_name=self._experiment_name,
                    video_file=relative_input_file,
                    input_value=self._build_option_description(),
                )

        return (input_report, output_report, diff)
