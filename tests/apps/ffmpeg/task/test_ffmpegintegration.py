import os
import logging

from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container
from ffmpeg_tools.validation import UnsupportedVideoCodec

from parameterized import parameterized
import pytest

from apps.transcoding.common import TranscodingTaskBuilderException, \
    ffmpegException
from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.testutils import TestTaskIntegration
from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.utils.ffprobe_report_set import FfprobeReportSet
from tests.apps.ffmpeg.task.utils.simulated_transcoding_operation import \
    SimulatedTranscodingOperation

logger = logging.getLogger(__name__)


@ci_skip
class TestFfmpegIntegration(TestTaskIntegration):

    VIDEO_FILES = [
        "test_video.mp4",
        "test_video2.mp4",
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ffprobe_report_set = FfprobeReportSet()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        report_file_name = os.path.join(
            cls.root_dir,
            'ffmpeg-integration-test-transcoding-diffs.md'
        )
        with open(report_file_name, 'w') as file:
            file.write(cls._ffprobe_report_set.to_markdown())

    def setUp(self):
        super().setUp()

        # We'll be comparing output from FfprobeFormatReport.diff() which
        # can be long but we still want to see it all.
        self.maxDiff = None

        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.tt = ffmpegTaskTypeInfo()

    @classmethod
    def _create_task_def_for_transcoding(
            cls,
            resource_stream,
            result_file,
            video_options=None,
            subtasks_count=2,
    ):
        task_def_for_transcoding = {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': subtasks_count,
            'bid': 1.0,
            'resources': [resource_stream],
            'options': {
                'output_path': os.path.dirname(result_file),
                'video': video_options if video_options is not None else {},
                'container': os.path.splitext(result_file)[1][1:]
            }
        }

        return task_def_for_transcoding

    @parameterized.expand(
        (video_file, video_codec, container)
        for video_file in VIDEO_FILES
        for video_codec, container in [
            (VideoCodec.H_264, Container.c_AVI),
        ]
    )
    @pytest.mark.slow
    def test_split_and_merge_with_codec_change(self,
                                               video_file,
                                               video_codec,
                                               container):
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="codec change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_video_codec_change(video_codec)
        operation.request_container_change(container)
        operation.request_resolution_change((320, 240))
        operation.exclude_from_diff({'video': {'bitrate', 'frame_count'}})
        (_input_report, _output_report, diff) = operation.run(video_file)
        self.assertEqual(diff, [])

    @parameterized.expand(
        (video_file, resolution)
        for video_file in VIDEO_FILES
        for resolution in (
            (320, 240),
        )
    )
    @pytest.mark.slow
    def test_split_and_merge_with_resolution_change(self,
                                                    video_file,
                                                    resolution):
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="resolution change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir)
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_resolution_change(resolution)
        operation.request_video_codec_change(VideoCodec.H_264)
        operation.exclude_from_diff({'video': {'bitrate'}})
        (_input_report, _output_report, diff) = operation.run(video_file)
        self.assertEqual(diff, [])

    @parameterized.expand(
        (video_file, frame_rate)
        for video_file in VIDEO_FILES
        for frame_rate in ('25/1', '25/2')
    )
    @pytest.mark.slow
    def test_split_and_merge_with_frame_rate_change(self,
                                                    video_file,
                                                    frame_rate):
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="frame rate change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution", "video_codec"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_frame_rate_change(frame_rate)
        operation.request_video_codec_change(VideoCodec.H_264)
        operation.request_resolution_change((320, 240))
        operation.exclude_from_diff({'video': {'bitrate', 'frame_count'}})
        (_input_report, _output_report, diff) = operation.run(video_file)
        self.assertEqual(diff, [])

    @parameterized.expand(
        (video_file, subtasks_count)
        for video_file in VIDEO_FILES
        for subtasks_count in (1, 6, 10)
    )
    @pytest.mark.slow
    def test_split_and_merge_with_different_subtask_counts(self,
                                                           video_file,
                                                           subtasks_count):
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="number of subtasks",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution", "video_codec"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_subtasks_count(subtasks_count)
        operation.request_video_codec_change(VideoCodec.H_264)
        operation.request_resolution_change((320, 240))
        operation.exclude_from_diff({'video': {'bitrate'}})
        (_input_report, _output_report, diff) = operation.run(video_file)
        self.assertEqual(diff, [])

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_simple_case(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2.mp4')
        result_file = os.path.join(self.root_dir, 'test_simple_case.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            video_options={
                'codec': 'h265',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        task = self.execute_task(task_def)
        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_nonexistent_output_dir(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2.mp4')
        result_file = os.path.join(self.root_dir, 'nonexistent', 'path',
                                   'test_invalid_task_definition.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            video_options={
                'codec': 'h265',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        task = self.execute_task(task_def)

        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))
        self.assertTrue(TestTaskIntegration.check_dir_existence(
            os.path.dirname(result_file)))

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_nonexistent_resource(self):
        resource_stream = os.path.join(self.RESOURCES,
                                       'test_nonexistent_video.mp4')

        result_file = os.path.join(self.root_dir, 'test_nonexistent_video.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            video_options={
                'codec': 'h265',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        with self.assertRaises(TranscodingTaskBuilderException):
            self.execute_task(task_def)

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_invalid_resource_stream(self):
        resource_stream = os.path.join(self.RESOURCES, 'invalid_test_video.mp4')
        result_file = os.path.join(self.root_dir,
                                   'test_invalid_resource_stream.mp4')

        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            video_options={
                'codec': 'h265',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        with self.assertRaises(ffmpegException):
            self.execute_task(task_def)

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_task_invalid_params(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2.mp4')
        result_file = os.path.join(self.root_dir, 'test_invalid_params.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            video_options={
                'codec': 'abcd',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        with self.assertRaises(UnsupportedVideoCodec):
            self.execute_task(task_def)
