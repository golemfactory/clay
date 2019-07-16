import logging
import os

import pytest
from parameterized import parameterized

from ffmpeg_tools.codecs import AudioCodec
from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container
from ffmpeg_tools.formats import list_supported_frame_rates
from ffmpeg_tools.validation import InvalidResolution, InvalidFrameRate, \
    UnsupportedTargetVideoFormat, UnsupportedVideoFormat, \
    UnsupportedAudioCodec, UnsupportedVideoCodec

from apps.transcoding.common import TranscodingTaskBuilderException, \
    ffmpegException, VideoCodecNotSupportedByContainer, \
    AudioCodecNotSupportedByContainer
from golem.testutils import TestTaskIntegration, \
    remove_temporary_dirtree_if_test_passed
from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.ffmpeg_integration_base import \
    FfmpegIntegrationBase
from tests.apps.ffmpeg.task.utils.simulated_transcoding_operation import \
    SimulatedTranscodingOperation

logger = logging.getLogger(__name__)


@ci_skip
class TestFfmpegIntegration(FfmpegIntegrationBase):

    # flake8: noqa
    # pylint: disable=line-too-long,bad-whitespace
    VIDEO_FILES = [
        {"resolution": [320, 240], "container": Container.c_MP4, "video_codec": VideoCodec.H_264,     "key_frames": 1,     "path": "test_video.mp4"},
        {"resolution": [320, 240], "container": Container.c_MP4, "video_codec": VideoCodec.H_264,     "key_frames": 2,     "path": "test_video2"},
    ]
    # pylint: enable=line-too-long,bad-whitespace

    @classmethod
    def _create_task_def_for_transcoding(  # pylint: disable=too-many-arguments
            cls,
            resource_stream,
            result_file,
            container,
            video_options=None,
            audio_options=None,
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
                'audio': audio_options if audio_options is not None else {},
                'container': container,
            }
        }

        return task_def_for_transcoding

    @parameterized.expand(
        (
            (video, video_codec, container)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for video_codec, container in [
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
        ),
        testcase_func_name=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_from_"
            f"{param[0][0]['video_codec'].value}_"
            f"{param[0][0]['container'].value}_to_"
            f"{param[0][1].value}_"
            f"{param[0][2].value}"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_codec_change(self,
                                               video,
                                               video_codec,
                                               container):
        super().split_and_merge_with_codec_change(video, video_codec, container)

    @parameterized.expand(
        (
            (video, resolution)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for resolution in (
                [400, 300],
                [640, 480],
                [720, 480],
            )
        ),
        testcase_func_name=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_from_"
            f"{param[0][0]['resolution'][0]}x"
            f"{param[0][0]['resolution'][1]}_to_"
            f"{param[0][1][0]}x{param[0][1][1]}"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_resolution_change(self, video, resolution):
        super().split_and_merge_with_resolution_change(video, resolution)

    @parameterized.expand(
        (
            (video, frame_rate)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for frame_rate in (1, 25, '30000/1001', 60)
        ),
        testcase_func_name=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_of_"
            f"{param[0][0]['video_codec'].value}_"
            f"{param[0][0]['container'].value}_to_"
            f"{str(param[0][1]).replace('/', '_')}_fps"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_frame_rate_change(self, video, frame_rate):
        super().split_and_merge_with_frame_rate_change(video, frame_rate)

    @parameterized.expand(
        (
            (video, subtasks_count)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for subtasks_count in (1, 6, 10, video['key_frames'])
        ),
        name_func=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_of_"
            f"{param[0][0]['video_codec'].value}_"
            f"{param[0][0]['container'].value}_into_"
            f"{param[0][1]}_subtasks"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_different_subtask_counts(self,
                                                           video,
                                                           subtasks_count):
        super().\
            split_and_merge_with_different_subtask_counts(video, subtasks_count)

    @remove_temporary_dirtree_if_test_passed
    def test_simple_case(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2')
        result_file = os.path.join(self.root_dir, 'test_simple_case.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            container=Container.c_MP4.value,
            video_options={
                'codec': 'h265',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        task = self.execute_task(task_def)
        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))

    @remove_temporary_dirtree_if_test_passed
    def test_nonexistent_output_dir(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2')
        result_file = os.path.join(self.root_dir, 'nonexistent', 'path',
                                   'test_invalid_task_definition.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            container=Container.c_MP4.value,
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

    @remove_temporary_dirtree_if_test_passed
    def test_nonexistent_resource(self):
        resource_stream = os.path.join(self.RESOURCES,
                                       'test_nonexistent_video.mp4')

        result_file = os.path.join(self.root_dir, 'test_nonexistent_video.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            container=Container.c_MP4.value,
            video_options={
                'codec': 'h265',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        with self.assertRaises(TranscodingTaskBuilderException):
            self.execute_task(task_def)

    @remove_temporary_dirtree_if_test_passed
    def test_invalid_resource_stream(self):
        resource_stream = os.path.join(
            self.RESOURCES,
            'invalid_test_video.mp4')
        result_file = os.path.join(self.root_dir,
                                   'test_invalid_resource_stream.mp4')

        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            container=Container.c_MP4.value,
            video_options={
                'codec': 'h265',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        with self.assertRaises(ffmpegException):
            self.execute_task(task_def)

    @remove_temporary_dirtree_if_test_passed
    def test_task_invalid_params(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2')
        result_file = os.path.join(self.root_dir, 'test_invalid_params.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            container=Container.c_MP4.value,
            video_options={
                'codec': 'abcd',
                'resolution': [320, 240],
                'frame_rate': "25",
            })

        with self.assertRaises(UnsupportedVideoCodec):
            self.execute_task(task_def)

    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_unsupported_target_video_codec(self):
        assert self.VIDEO_FILES[0]["container"] != Container.c_OGG
        with self.assertRaises(VideoCodecNotSupportedByContainer):
            operation = SimulatedTranscodingOperation(
                task_executor=self,
                experiment_name=None,
                resource_dir=self.RESOURCES,
                tmp_dir=self.tempdir)
            operation.request_video_codec_change(
                self.VIDEO_FILES[0]['video_codec'])
            operation.request_container_change(Container.c_OGG)
            operation.request_resolution_change(
                self.VIDEO_FILES[0]["resolution"])
            operation.run(self.VIDEO_FILES[0]["path"])

    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_unsupported_target_container_if_exclusive_demuxer(self):
        with self.assertRaises(UnsupportedTargetVideoFormat):
            operation = SimulatedTranscodingOperation(
                task_executor=self,
                experiment_name=None,
                resource_dir=self.RESOURCES,
                tmp_dir=self.tempdir)
            operation.request_video_codec_change(
                self.VIDEO_FILES[0]['video_codec'])
            operation.request_container_change(
                Container.c_MATROSKA_WEBM_DEMUXER)
            operation.request_resolution_change(
                self.VIDEO_FILES[0]["resolution"])
            operation.run(self.VIDEO_FILES[0]["path"])

    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_invalid_resolution_should_raise_proper_exception(self):
        dst_resolution = (100, 100)
        assert self.VIDEO_FILES[0]['resolution'][0] / dst_resolution[0] != \
            self.VIDEO_FILES[0]['resolution'][1] / dst_resolution[1], \
            "Only a resolution change that involves changing aspect ratio is " \
            "supposed to trigger InvalidResolution"
        with self.assertRaises(InvalidResolution):
            operation = SimulatedTranscodingOperation(
                task_executor=self,
                experiment_name=None,
                resource_dir=self.RESOURCES,
                tmp_dir=self.tempdir)
            operation.request_video_codec_change(
                self.VIDEO_FILES[0]['video_codec'])
            operation.request_container_change(self.VIDEO_FILES[0]['container'])
            operation.request_resolution_change(dst_resolution)
            operation.run(self.VIDEO_FILES[0]["path"])

    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_invalid_frame_rate_should_raise_proper_exception(self):
        assert 55 not in list_supported_frame_rates()
        with self.assertRaises(InvalidFrameRate):
            operation = SimulatedTranscodingOperation(
                task_executor=self,
                experiment_name=None,
                resource_dir=self.RESOURCES,
                tmp_dir=self.tempdir)
            operation.request_video_codec_change(
                self.VIDEO_FILES[0]['video_codec'])
            operation.request_container_change(self.VIDEO_FILES[0]['container'])
            operation.request_resolution_change(
                self.VIDEO_FILES[0]["resolution"])
            operation.request_frame_rate_change('55')
            operation.run(self.VIDEO_FILES[0]["path"])

    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_invalid_container_should_raise_proper_exception(self):
        with self.assertRaises(UnsupportedVideoFormat):
            operation = SimulatedTranscodingOperation(
                task_executor=self,
                experiment_name=None,
                resource_dir=self.RESOURCES,
                tmp_dir=self.tempdir)
            operation.request_video_codec_change(
                self.VIDEO_FILES[0]['video_codec'])
            operation.request_container_change('invalid container', '')
            operation.request_resolution_change(
                self.VIDEO_FILES[0]["resolution"])
            operation.run(self.VIDEO_FILES[0]["path"])

    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_unsupported_audio_codec_should_raise_proper_exception(self):
        with self.assertRaises(AudioCodecNotSupportedByContainer):
            operation = SimulatedTranscodingOperation(
                task_executor=self,
                experiment_name=None,
                resource_dir=self.RESOURCES,
                tmp_dir=self.tempdir)
            operation.request_video_codec_change(VideoCodec.H_264)
            operation.request_audio_codec_change(AudioCodec.AC3)
            operation.request_container_change(Container.c_MP4)
            operation.request_resolution_change((180, 98))
            operation.run("big_buck_bunny_stereo.mp4")

    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_task_invalid_audio_params(self):
        resource_stream = os.path.join(self.RESOURCES,
                                       'big_buck_bunny_stereo.mp4')
        result_file = os.path.join(self.root_dir, 'test_invalid_params.mp4')
        task_def = self._create_task_def_for_transcoding(
            resource_stream,
            result_file,
            container=Container.c_MP4.value,
            audio_options={
                'codec': 'abcd',
            })
        with self.assertRaises(UnsupportedAudioCodec):
            self.execute_task(task_def)
