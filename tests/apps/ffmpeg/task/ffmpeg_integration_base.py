import logging
import os

import pytest
from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container, list_supported_frame_rates
from ffmpeg_tools.validation import InvalidResolution, \
    UnsupportedVideoCodecConversion, InvalidFrameRate, validate_resolution

from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.testutils import TestTaskIntegration
from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.utils.ffprobe_report import FuzzyDuration, \
    parse_ffprobe_frame_rate
from tests.apps.ffmpeg.task.utils.ffprobe_report_set import FfprobeReportSet
from tests.apps.ffmpeg.task.utils.simulated_transcoding_operation import \
    SimulatedTranscodingOperation

logger = logging.getLogger(__name__)


CODEC_CONTAINER_PAIRS_TO_TEST = [
    (VideoCodec.FLV1, Container.c_FLV),
    (VideoCodec.H_264, Container.c_AVI),
    (VideoCodec.HEVC, Container.c_MP4),
    (VideoCodec.MJPEG, Container.c_MOV),
    (VideoCodec.MPEG_1, Container.c_MPEG),
    (VideoCodec.MPEG_2, Container.c_MPEG),
    (VideoCodec.MPEG_4, Container.c_MPEGTS),
    (VideoCodec.THEORA, Container.c_OGG),
    (VideoCodec.VP8, Container.c_WEBM),
    (VideoCodec.VP9, Container.c_MATROSKA),
    (VideoCodec.WMV1, Container.c_ASF),
    (VideoCodec.WMV2, Container.c_ASF),
]


def create_split_and_merge_with_codec_change_test_name(
        testcase_func,
        param_num,
        param):
    source_video_codec = {param[0][0]['video_codec'].value}
    destination_video_codec = {param[0][1].value}
    destination_container = {param[0][2].value}

    return (
        f'{testcase_func.__name__}_{param_num}_from_'
        f'{source_video_codec}_to_video_codec_'
        f'{destination_video_codec}_and_container_'
        f'{destination_container}'
    )


def create_split_and_merge_with_resolution_change_test_name(
        testcase_func,
        param_num,
        param):
    source_width = f"{param[0][0]['resolution'][0]}"
    source_height = f"{param[0][0]['resolution'][1]}"
    destination_resolution = f"{param[0][1][0]}x{param[0][1][1]}"
    return (
        f'{testcase_func.__name__}_{param_num}_from_'
        f'{source_width}x'
        f'{source_height}_to_'
        f'{destination_resolution}'
    )


def create_split_and_merge_with_frame_rate_change_test_name(
        testcase_func,
        param_num,
        param):
    source_video_codec = f"{param[0][0]['video_codec'].value}"
    source_video_container = f"{param[0][0]['container'].value}"
    destination_frame_rate = f"{str(param[0][1]).replace('/', '_')}"
    return (
        f'{testcase_func.__name__}_{param_num}_of_codec_'
        f'{source_video_codec}_and_container_'
        f'{source_video_container}_to_'
        f'{destination_frame_rate}_fps'
    )


def create_split_and_merge_with_different_subtask_counts_test_name(
        testcase_func,
        param_num,
        param):
    source_video_codec = f"{param[0][0]['video_codec'].value}_"
    source_video_container = f"{param[0][0]['container'].value}"
    number_of_subtasks = f"{param[0][1]}_subtasks"
    return (
        f'{testcase_func.__name__}_{param_num}_of_codec_'
        f'{source_video_codec}_and_container_'
        f'{source_video_container}_into_'
        f'{number_of_subtasks}_subtasks'
    )


@ci_skip
class FfmpegIntegrationBase(TestTaskIntegration):

    ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS = {
        'video': {
            'bitrate',
            'pixel_format',
        },
        'audio': {
            'codec_name',
            'sample_rate',
            'sample_format',
            'bitrate',

            # It's the total number of samples that is preserved. The number
            # of samples per frame and the number of frames often both change
            # without affecting the total.
            'frame_count',
        },
        'subtitle': {
            'codec_name',
        },
    }

    # flake8: noqa
    # pylint: disable=line-too-long
    _IGNORED_ATTRIBUTES_OF_BROKEN_FILE = {
        # The merge step (using ffmpeg’s concat demuxer) changes FPS from 29.97
        # to 30. This happens only for this particular file and there does not
        # seem to be anything unusual about the input file itself. We have
        # decided to ignore this problem for now because we can’t do anything
        # about it and it’s likely to be a bug in ffmpeg. So bad output is
        # unfortunately the expected result here.
        'standalone-tra3106[mjpeg,720x496,17s,v1a0s0d0,i1525p1016b1016,29.97fps][segment1of17].avi': {'video': {'frame_rate'}},
        # This wmv3/wmv file has incorrect FPS in metadata (or at least ffprobe
        # returns an incorrect value). This makes ffmpeg (incorrectly) double
        # the number of frames while keeping the FPS in output file metadata the
        # same as in the original. We can’t help it. We’re going to assume that
        # this is the expected result, i.e. garbage in, garbage out.”
        'standalone-catherine[wmv3+wmav2,180x140,42s,v1a1s0d0,i637p1257b631,_][segment1of6].wmv': {'video': {'frame_rate'}},
    }
    # pylint: enable=line-too-long

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

    def split_and_merge_with_codec_change(
            self,
            video,
            video_codec,
            container):
        # FIXME: These tests should be re-enabled once all the fixes needed
        # to make them pass are done and merged.
        if video["path"].startswith("videos/"):
            pytest.skip("Files from transcoding-video-bundle disabled for now")

        source_codec = video["video_codec"]
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="codec change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_video_codec_change(video_codec)
        operation.request_container_change(container)
        operation.request_resolution_change(video["resolution"])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.exclude_from_diff({'video': {'frame_count'}})
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Source container not supported")
        if not Container.is_supported(container.value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Source video codec not supported by the container")
        if not container.is_supported_video_codec(video_codec.value):
            pytest.skip("Target video codec not supported by the container")

        supported_conversions = source_codec.get_supported_conversions()
        if video_codec.value in supported_conversions:
            (_input_report, _output_report, diff) = operation.run(
                video["path"])
            self.assertEqual(diff, [])
        else:
            with self.assertRaises(UnsupportedVideoCodecConversion):
                operation.run(video["path"])
            pytest.skip("Video codec conversion not supported")

    def split_and_merge_with_resolution_change(self, video, resolution):
        # FIXME: These tests should be re-enabled once all the fixes needed
        # to make them pass are done and merged.
        if video["path"].startswith("videos/"):
            pytest.skip("Files from transcoding-video-bundle disabled for now")

        source_codec = video["video_codec"]
        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="resolution change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir)
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_resolution_change(resolution)
        operation.request_video_codec_change(source_codec)
        operation.request_container_change(video['container'])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        supported_conversions = source_codec.get_supported_conversions()
        if source_codec.value not in supported_conversions:
            pytest.skip("Transcoding is not possible for this file without"
                        "also changing the video codec.")

        try:
            validate_resolution(video["resolution"], resolution)
            (_input_report, _output_report, diff) = operation.run(video["path"])
            self.assertEqual(diff, [])
        except InvalidResolution:
            with self.assertRaises(InvalidResolution):
                operation.run(video["path"])
            pytest.skip("Target resolution not supported")

    def split_and_merge_with_frame_rate_change(self, video, frame_rate):
        # FIXME: These tests should be re-enabled once all the fixes needed
        # to make them pass are done and merged.
        if video["path"].startswith("videos/"):
            pytest.skip("Files from transcoding-video-bundle disabled for now")

        source_codec = video["video_codec"]
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="frame rate change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution", "video_codec"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_frame_rate_change(frame_rate)
        operation.request_video_codec_change(source_codec)
        operation.request_container_change(video['container'])
        operation.request_resolution_change(video["resolution"])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.exclude_from_diff({'video': {'frame_count'}})
        fuzzy_rate = FuzzyDuration(parse_ffprobe_frame_rate(frame_rate), 0.5)
        operation.set_override('video', 'frame_rate', fuzzy_rate)
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        supported_conversions = source_codec.get_supported_conversions()
        if source_codec.value not in supported_conversions:
            pytest.skip("Transcoding is not possible for this file without"
                        "also changing the video codec.")

        frame_rate_as_str_or_int = set([frame_rate, str(frame_rate)])
        if frame_rate_as_str_or_int & list_supported_frame_rates() != set():
            (_input_report, _output_report, diff) = operation.run(
                video["path"])
            self.assertEqual(diff, [])
        else:
            with self.assertRaises(InvalidFrameRate):
                operation.run(video["path"])
            pytest.skip("Target frame rate not supported")

    def split_and_merge_with_different_subtask_counts(
            self,
            video,
            subtasks_count):
        # FIXME: These tests should be re-enabled once all the fixes needed
        # to make them pass are done and merged.
        if video["path"].startswith("videos/"):
            pytest.skip("Files from transcoding-video-bundle disabled for now")

        source_codec = video["video_codec"]
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="number of subtasks",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution", "video_codec"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_subtasks_count(subtasks_count)
        operation.request_video_codec_change(source_codec)
        operation.request_container_change(video['container'])
        operation.request_resolution_change(video["resolution"])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        supported_conversions = source_codec.get_supported_conversions()
        if source_codec.value not in supported_conversions:
            pytest.skip("Transcoding is not possible for this file without"
                        "also changing the video codec.")

        (_input_report, _output_report, diff) = operation.run(video["path"])
        self.assertEqual(diff, [])
