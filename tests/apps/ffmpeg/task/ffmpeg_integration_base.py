import logging
import os

from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container

from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.testutils import TestTaskIntegration
from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.utils.ffprobe_report_set import FfprobeReportSet

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
            f'ffmpeg-integration-test-transcoding-diffs-{cls.__name__}.md'
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
