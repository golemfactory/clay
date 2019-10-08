import logging
import os

from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.testutils import TestTaskIntegration
from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.utils.ffprobe_report_set import FfprobeReportSet

logger = logging.getLogger(__name__)


def create_split_and_merge_with_codec_change_test_name(
        testcase_func,
        param_num,
        param):
    source_video_codec = param[0][0]['video_codec'].value
    destination_video_codec = param[0][1].value
    destination_container = param[0][2].value

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
    source_width = param[0][0]['resolution'][0]
    source_height = param[0][0]['resolution'][1]
    destination_width = param[0][1][0]
    destination_height = param[0][1][1]
    return (
        f'{testcase_func.__name__}_{param_num}_from_'
        f'{source_width}x'
        f'{source_height}_to_'
        f'{destination_width}x{destination_height}'
    )


def create_split_and_merge_with_frame_rate_change_test_name(
        testcase_func,
        param_num,
        param):
    source_video_codec = param[0][0]['video_codec'].value
    source_video_container = param[0][0]['container'].value
    destination_frame_rate = str(param[0][1]).replace('/', '_')
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
    source_video_codec = param[0][0]['video_codec'].value
    source_video_container = param[0][0]['container'].value
    number_of_subtasks = param[0][1]
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
