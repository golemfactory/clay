import os

import mock
import pytest
from parameterized import parameterized
from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container

from golem.testutils_app_integration import TestTaskIntegration
from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.utils.ffprobe_report import \
    FfprobeFormatReport, FuzzyInt
from tests.apps.ffmpeg.task.utils.ffprobe_report_set import FfprobeReportSet
from tests.apps.ffmpeg.task.utils.simulated_transcoding_operation import \
    SimulatedTranscodingOperation


class TestSimulatedTranscodingOperationIntegration(TestTaskIntegration):

    def setUp(self):
        super(TestSimulatedTranscodingOperationIntegration, self).setUp()

        self.RESOURCES = self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
            'resources')

        self.operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="codec change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir)
        self.ffprobe_report_set = FfprobeReportSet()
        self.operation.attach_to_report_set(self.ffprobe_report_set)

    @ci_skip
    @pytest.mark.slow
    def test_run_collects_reports_and_diff(self):
        self.operation.request_video_codec_change(VideoCodec.H_264)
        self.operation.request_container_change(Container.c_MP4)
        self.operation.request_resolution_change((320, 240))
        input_report, output_report, diff = self.operation.run('test_video.mp4')

        self.assertIsInstance(input_report, FfprobeFormatReport)
        self.assertIsInstance(output_report, FfprobeFormatReport)
        self.assertIsInstance(diff, list)
        self.assertEqual(
            set(self.ffprobe_report_set._report_tables[
                'codec change']['test_video.mp4']),
            {'h264/mp4/320x240/2seg'},
        )

    @mock.patch(
        'golem.testutils_app_integration.TestTaskIntegration.execute_task',
        side_effect=BaseException
    )
    def test_exceptions_are_collected_but_not_silenced(self, _executor):
        self.operation.request_video_codec_change(VideoCodec.H_264)
        self.operation.request_container_change(Container.c_MP4)
        with self.assertRaises(BaseException):
            _input, _output, _diff = self.operation.run('test_video.mp4')
        self.assertEqual(
            self.ffprobe_report_set._report_tables, {
                'codec change': {
                    'test_video.mp4': {'h264/mp4/2seg': 'BaseException'}
                }
            }
        )

    @parameterized.expand([
        (
            'request_container_change',
            Container.c_MPEG,
            {'format': {'format_name': 'mpeg'}},
        ),
        (
            'request_video_codec_change',
            VideoCodec.H_264,
            {'video': {'codec_name': 'h264'}},
        ),
        (
            'request_video_bitrate_change',
            100,
            {'video': {'bitrate': FuzzyInt(100, 5)}},
        ),
        (
            'request_resolution_change',
            'custom_value',
            {'video': {'resolution': 'custom_value'}},
        ),
        (
            'request_frame_rate_change',
            'custom_value',
            {'video': {'frame_rate': 'custom_value'}},
        ),
    ])
    def test_diff_overrides_are_equal_to_expected_if_function_changing_parameter_called(  # noqa pylint: disable=line-too-long
            self,
            function_name,
            new_value,
            expected_diff_overrides,
    ):
        function = getattr(self.operation, function_name)
        function(new_value)
        diff_overrides = self.operation._diff_overrides
        self.assertEqual(diff_overrides, expected_diff_overrides)

    @parameterized.expand([
        ({'format': {'format_name'}},),
        ({'video': {'codec_name', 'bitrate'}},),
        ({'video': {'codec_name', 'bitrate'}},),
        ({'video': {'resolution', 'bitrate'}},),
        ({
            'format': {'format_name'},
            'video': {'bitrate'},
        },),
        ({
            'format': {'format_name'},
            'video': {'resolution', 'bitrate'},
        },),
    ])
    def test_exclude_from_diff_excludes_parameters_correctly(self, exclude):
        self.operation.exclude_from_diff(exclude)
        self.assertEqual(self.operation._diff_excludes, exclude)
