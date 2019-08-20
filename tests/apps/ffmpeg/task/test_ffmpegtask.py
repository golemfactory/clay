import os
import shutil
import uuid
from tempfile import TemporaryDirectory
from unittest import mock
from freezegun import freeze_time

from golem_messages.factories.datastructures import p2p as dt_p2p_factory

from ffmpeg_tools.codecs import VideoCodec, AudioCodec
from ffmpeg_tools.formats import Container
from ffmpeg_tools.validation import UnsupportedVideoCodec, \
    UnsupportedAudioCodec, UnsupportedVideoFormat

from apps.transcoding.common import TranscodingTaskBuilderException
from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from apps.transcoding.ffmpeg.utils import Commands
from golem.core.common import timeout_to_deadline
from golem.docker.job import DockerJob
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip


# TODO: test invalid video file

@ci_skip
class TestffmpegTask(TempDirFixture):
    RESOURCES = os.path.join(os.path.dirname(
        os.path.dirname(os.path.realpath(__file__))), 'resources')
    RESOURCE_STREAM = os.path.join(RESOURCES, 'test_video.mp4')
    RESOURCE_STREAM2 = os.path.join(RESOURCES, 'test_video2')

    def setUp(self):
        super(TestffmpegTask, self).setUp()

        self.tt = ffmpegTaskTypeInfo()
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dir=self.new_path,
            in_background=True)

    def _build_ffmpeg_task(self, subtasks_count=1, stream=RESOURCE_STREAM):
        td = self.tt.task_builder_type.build_definition(
            self.tt, self._task_dictionary(subtasks_count, stream))
        
        dir_manager = DirManager(self.tempdir)
        task = self.tt.task_builder_type(dt_p2p_factory.Node(), td,
                                         dir_manager).build()
        task.initialize(dir_manager)
        return task

    def _task_dictionary(self, subtasks_count=1, stream=RESOURCE_STREAM):
        return {
            'type': 'FFMPEG',
            'name': 'test task',
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': subtasks_count,
            'bid': 1.0,
            'resources': [stream],
            'options': {
                'output_path': '/tmp/',
                'video': {
                    'bit_rate': 18,
                    'codec': 'h264',
                    'resolution': [320, 240],
                    'frame_rate': 25
                },
                'audio': {
                    'bit_rate': 18,
                    'codec': 'mp3'
                },
                'container': 'mp4',
                'strip_unsupported_data_streams': False,
                'strip_unsupported_subtitle_streams': False,
            }
        }

    def test_build_task_def_from_task_type(self):
        d = self._task_dictionary()
        for m in [True, False]:
            with self.subTest(msg='Test different level of task', p1=m):
                self.tt.task_builder_type.build_definition(self.tt, d, m)

    def test_build_task_def_no_resources(self):
        d = self._task_dictionary()
        d['resources'] = []
        with self.assertRaises(TranscodingTaskBuilderException) as cxt:
            self.tt.task_builder_type.build_definition(self.tt, d)
        assert 'Field resources is required in the task definition' \
               in str(cxt.exception)

    def test_build_task_resource_does_not_exist(self):
        d = self._task_dictionary()
        d['resources'] = [os.path.join(self.tempdir, 'not_exists')]
        with self.assertRaises(TranscodingTaskBuilderException) as cxt:
            self.tt.task_builder_type.build_definition(self.tt, d)
        self.assertIn('does not exist', str(cxt.exception))

    def test_build_task_video_codec_not_match_to_container(self):
        invalid_params = [('avi', 'not_supported'), ('mkv', 'not_supported'),
                          ('mp4', 'vp6')]
        d = self._task_dictionary()

        for container, codec in invalid_params:
            with self.subTest('Testing container and codec',
                              container=container, codec=codec):
                d['options']['video']['codec'] = codec
                d['options']['container'] = container
                with self.assertRaises(UnsupportedVideoCodec):
                    self.tt.task_builder_type.build_definition(self.tt, d)

    def test_build_task_audio_codec_not_match_to_container(self):
        invalid_params = [('avi', 'not_supported'), ('mkv', 'not_supported'),
                          ('mp4', 'pcm')]
        d = self._task_dictionary()
        for container, codec in invalid_params:
            with self.subTest('Testing container and codec',
                              container=container, codec=codec):
                d['options']['audio']['codec'] = codec
                d['options']['container'] = container
                with self.assertRaises(UnsupportedAudioCodec):
                    self.tt.task_builder_type.build_definition(self.tt, d)

    def test_build_task_not_supported_container(self):
        d = self._task_dictionary()
        d['options']['container'] = 'xxx'
        with self.assertRaises(UnsupportedVideoFormat) as _:
            self.tt.task_builder_type.build_definition(self.tt, d)

    def test_build_task_different_codecs(self):
        params = [('mov', 'h265', 'aac'), ('mp4', 'h264', 'aac')]
        d = self._task_dictionary()

        for container, vcodec, acodec in params:
            with self.subTest('Test container and codecs', container=container,
                              vcodec=vcodec, acodec=acodec):
                d['options']['audio']['codec'] = acodec
                d['options']['video']['codec'] = vcodec
                d['options']['container'] = container
                self.tt.task_builder_type.build_definition(self.tt, d)

    @freeze_time('2019-01-01 00:00:00')
    def test_valid_task_definition(self):
        d = self._task_dictionary()
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
            voptions['codec']))

        self.assertEqual(options.audio_params.bitrate, aoptions['bit_rate'])
        self.assertEqual(options.audio_params.codec,
                         AudioCodec(aoptions['codec']))

        self.assertEqual(options.output_container,
                         Container(d['options']['container']))

        self.assertEqual(td.output_file,
                         '/tmp/test task.mp4')

    def test_invalid_extra_data(self):
        ffmpeg_task = self._build_ffmpeg_task()
        with self.assertRaises(AssertionError):
            ffmpeg_task._get_extra_data(1)

    def test_extra_data_for_files_with_multiple_dots_in_name(self):
        with TemporaryDirectory(prefix='test-with-dots') as tmp_dir:
            resource_stream_with_dot = os.path.join(tmp_dir, 'test.video.mp4')
            shutil.copyfile(self.RESOURCE_STREAM, resource_stream_with_dot)

            ffmpeg_task = self._build_ffmpeg_task(
                stream=resource_stream_with_dot
            )

            extra_data = ffmpeg_task._get_extra_data(0)
            self.assertEqual(
                extra_data['track'],
                os.path.join(
                    DockerJob.RESOURCES_DIR,
                    'test.video[video-only]_0.mp4'))
            self.assertEqual(
                extra_data['output_stream'],
                os.path.join(
                    DockerJob.OUTPUT_DIR,
                    'test.video[video-only]_0_TC.mp4'))

    def test_extra_data(self):
        ffmpeg_task = self._build_ffmpeg_task()

        d = self._task_dictionary()
        extra_data = ffmpeg_task._get_extra_data(0)
        self.assertEqual(extra_data['command'], Commands.TRANSCODE.value[0])
        self.assertEqual(extra_data['entrypoint'],
                         'python3 /golem/scripts/ffmpeg_task.py')
        self.assertEqual(extra_data['track'],
                         '/golem/resources/test_video[video-only]_0.mp4')
        vargs = extra_data['targs']['video']
        aargs = extra_data['targs']['audio']
        self.assertEqual(vargs['codec'], d['options']['video']['codec'])
        self.assertEqual(vargs['bitrate'], d['options']['video']['bit_rate'])
        self.assertEqual(extra_data['targs']['resolution'],
                         d['options']['video']['resolution'])
        self.assertEqual(extra_data['targs']['frame_rate'],
                         d['options']['video']['frame_rate'])
        self.assertEqual(aargs['codec'], d['options']['audio']['codec'])
        self.assertEqual(aargs['bitrate'], d['options']['audio']['bit_rate'])
        self.assertEqual(extra_data['output_stream'],
                         '/golem/output/test_video[video-only]_0_TC.mp4')

    def test_less_subtasks_than_requested(self):
        d = self._task_dictionary()
        d['subtasks_count'] = 2
        td = self.tt.task_builder_type.build_definition(self.tt, d)
        builder = self.tt.task_builder_type(dt_p2p_factory.Node(), td,
                                            DirManager(self.tempdir))
        from apps.transcoding.task import logger
        with self.assertLogs(logger, level="WARNING") as log:
            task = builder.build()
            task.initialize(DirManager(self.tempdir))
            assert any("subtasks was requested but video splitting process"
                       in log for log in log.output)

        self.assertEqual(task.total_tasks, 1)

    def test_query_extra_data(self):
        ffmpeg_task = self._build_ffmpeg_task()

        node_id = uuid.uuid4()
        ffmpeg_task.header.task_id = str(uuid.uuid4())
        extra_data = ffmpeg_task.query_extra_data(0.5, node_id)
        ctd = extra_data.ctd
        subtask = next(iter(ffmpeg_task.subtasks_given.values()))

        self.assertEqual(subtask['perf'], 0.5)
        self.assertEqual(subtask['node_id'], node_id)
        self.assertIsNotNone(subtask['subtask_id'])
        self.assertEqual(subtask['status'], SubtaskStatus.starting)
        self.assertEqual(subtask['subtask_num'], 0)

        self.assertIsNotNone(ctd['task_id'])
        self.assertEqual(ctd['subtask_id'], subtask['subtask_id'])
        self.assertEqual(ctd['extra_data'], subtask['transcoding_params'])
        self.assertEqual(ctd['docker_images'], [di.to_dict() for di in
                                                ffmpeg_task.docker_images])
        self.assertEqual(ctd['deadline'], min(
            timeout_to_deadline(ffmpeg_task.header.subtask_timeout),
            ffmpeg_task.header.deadline))

    def test_resources_distributed_per_subtasks(self):
        ffmpeg_task = self._build_ffmpeg_task(
            subtasks_count=2,
            stream=TestffmpegTask.RESOURCE_STREAM2)

        node_id = uuid.uuid4()
        ffmpeg_task.header.task_id = str(uuid.uuid4())
        resources1 = ffmpeg_task.query_extra_data(0.5, node_id).ctd['resources']
        resources2 = ffmpeg_task.query_extra_data(0.5, node_id).ctd['resources']
        self.assertEqual(len(resources1), 1)
        self.assertEqual(len(resources2), 1)
        self.assertEqual(len(set(resources1 + resources2)), 2)
