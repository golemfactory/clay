import tempfile

import pytest
from apps.transcoding.common import TranscodingException, \
    TranscodingTaskBuilderException, AudioCodec, VideoCodec, Container
from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from coverage.annotate import os
from golem.testutils import TempDirFixture

# TODO: test invalid video file


class TestffmpegTask(TempDirFixture):
    def setUp(self):
        super(TestffmpegTask, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.RESOURCE_STREAM = os.path.join(self.RESOURCES, 'test_video.mp4')
        self.tt = ffmpegTaskTypeInfo()

    @property
    def _task_dictionary(self):
        return {
            'type': 'FFMPEG',
            'name': 'test task',
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': 1,
            'bid': 1.0,
            'resources': [self.RESOURCE_STREAM],
            'options': {
                'output_path': '/tmp/',
                'video': {
                    'bit_rate': 18,
                    'codec': 'libx264',
                    'resolution': [320, 240],
                    'frame_rate': 25
                },
                'audio': {
                    'bit_rate': 18,
                    'codec': 'mp3'
                },
                'container': 'mp4'
            }
        }

    def test_build_task_def_from_task_type(self):
        task_type = ffmpegTaskTypeInfo()
        d = self._task_dictionary
        task_type.task_builder_type.build_definition(task_type, d)
        for m in [True, False]:
            with self.subTest(msg='Test different level of task', p1=m):
                task_type.task_builder_type.build_definition(task_type, d, m)


    def test_build_task_def_no_resources(self):
        task_type = ffmpegTaskTypeInfo()
        d = self._task_dictionary
        d['resources'] = []
        with self.assertRaises(TranscodingTaskBuilderException) as cxt:
            task_type.task_builder_type.build_definition(task_type, d)
        assert 'Field resources is required in the task definition' \
               in str(cxt.exception)

    def test_build_task_resource_does_not_exist(self):
        task_type = ffmpegTaskTypeInfo()
        d = self._task_dictionary
        d['resources'] = [os.path.join(self.tempdir, 'not_exists')]
        with self.assertRaises(TranscodingTaskBuilderException) as cxt:
            task_type.task_builder_type.build_definition(task_type, d)
        self.assertIn('does not exist', str(cxt.exception))

    def test_build_task_video_codec_not_match_to_container(self):
        invalid_params = [('avi', 'not_supported'), ('mkv', 'not_supported'),
                          ('mp4', 'vp6')]
        d = self._task_dictionary
        tt = ffmpegTaskTypeInfo()

        for container, codec in invalid_params:
            with self.subTest('Testing container and codec',
                              container=container, codec=codec):
                d['options']['video']['codec'] = codec
                d['options']['container'] = container
                with self.assertRaises(TranscodingTaskBuilderException) as cxt:
                    tt.task_builder_type.build_definition(tt, d)

    def test_build_task_audio_codec_not_match_to_container(self):
        invalid_params = [('avi', 'not_supported'), ('mkv', 'not_supported'),
                          ('mp4', 'pcm')]
        d = self._task_dictionary
        tt = ffmpegTaskTypeInfo()

        for container, codec in invalid_params:
            with self.subTest('Testing container and codec',
                              container=container, codec=codec):
                d['options']['audio']['codec'] = codec
                d['options']['container'] = container
                with self.assertRaises(TranscodingTaskBuilderException) as cxt:
                    tt.task_builder_type.build_definition(tt, d)

    def test_build_task_not_supported_container(self):
        d = self._task_dictionary
        tt = ffmpegTaskTypeInfo()
        d['options']['container'] = 'xxx'
        with self.assertRaises(TranscodingTaskBuilderException) as cxt:
            tt.task_builder_type.build_definition(tt, d)

    def test_build_task_different_codecs(self):
        params = [('avi', 'MPEG-4 Part 2', 'AAC'), ('mp4', 'Libx264', 'aac')]
        d = self._task_dictionary
        tt = ffmpegTaskTypeInfo()

        for container, vcodec, acodec in params:
            with self.subTest('Test container and codecs', container=container,
                              vcodec=vcodec, acodec=acodec):
                d['options']['audio']['codec'] = acodec
                d['options']['video']['codec'] = vcodec
                d['options']['container'] = container
                tt.task_builder_type.build_definition(tt, d)

    def test_valid_task_definition(self):
        self.input_stream_path = None
        self.output_container = None

        d = self._task_dictionary
        td = self.tt.task_builder_type.build_definition(self.tt, d)
        options = td.options
        voptions = d['options']['video']
        aoptions = d['options']['audio']

        self.assertEqual(options.video_params.frame_rate,
                         voptions['frame_rate'])
        self.assertEqual(options.video_params.bitrate, voptions['bit_rate'])
        self.assertEqual(options.video_params.resolution,
                         voptions['resolution'])
        self.assertEqual(options.video_params.codec, VideoCodec(
            voptions['codec'].upper()))

        self.assertEqual(options.audio_params.bitrate, aoptions['bit_rate'])
        self.assertEqual(options.audio_params.codec,
                         AudioCodec(aoptions['codec'].upper()))

        self.assertEqual(options.output_container,
                         Container(d['options']['container']))

        self.assertEqual(td.output_file, '/tmp/test task.mp4')

