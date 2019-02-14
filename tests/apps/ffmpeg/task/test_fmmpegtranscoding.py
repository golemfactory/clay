import shutil
import uuid
from os import rename
from os.path import splitext, join
from unittest import mock

from coverage.annotate import os

from apps.transcoding.common import ffmpegException
from apps.transcoding.ffmpeg.utils import StreamOperator, Commands, \
    FFMPEG_BASE_SCRIPT
from golem.docker.job import DockerJob
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.resource.dirmanager import DirManager
from golem.testutils import TempDirFixture
from tests.golem.docker.test_docker_image import DockerTestCase
from tests.golem.docker.test_docker_job import TestDockerJob


class TestffmpegTranscoding(TempDirFixture, DockerTestCase):
    def setUp(self):
        super(TestffmpegTranscoding, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.RESOURCE_STREAM = os.path.join(self.RESOURCES, 'test_video2.mp4')
        self.stream_operator = StreamOperator()
        self.dir_manager = DirManager(self.tempdir)
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dir=self.new_path,
            in_background=True)

    def test_split_video(self):
        for parts in [1, 2]:
            with self.subTest('Testing splitting', parts=parts):
                chunks = self.stream_operator.split_video(
                    self.RESOURCE_STREAM, parts, self.dir_manager,
                    str(uuid.uuid4()))
                self.assertEqual(len(chunks), parts)

    def test_split_invalid_video(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator.split_video(os.path.join(self.RESOURCES,
                                                          'invalid_test_video2.mp4'),
                                             1, self.dir_manager,
                                             str(uuid.uuid4()))

    def test_split_and_merge_video(self):
        print("\n\n{}\n\n".format(self.tempdir))
        parts = 2
        chunks = self.stream_operator.split_video(
            self.RESOURCE_STREAM, parts,
            self.dir_manager, str(uuid.uuid4()))
        self.assertEqual(len(chunks), parts)
        playlists = [file for chunk in chunks for file in chunk if file.endswith('m3u8')]
        for playlist in playlists:
            name, ext = splitext(playlist)
            ttt = join(self.dir_manager.get_task_output_dir(str(uuid.uuid4())), playlist)
            rename(join(self.dir_manager.get_task_output_dir(str(uuid.uuid4())), playlist),
                   join(self.dir_manager.get_task_output_dir(str(uuid.uuid4())), "{}_TC{}".format(name, ext)))

        assert True

    def test_merge_video_empty_dir(self):
        assert True


class TestffmpegDockerJob(TestDockerJob):
    def _get_test_repository(self):
        return "golemfactory/ffmpeg"

    def _get_test_tag(self):
        return "1.0"

    def test_ffmpeg_trancoding_job(self):
        stream_file = os.path.join(os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources'),
            'test_video.mp4')
        shutil.copy(str(stream_file), self.resources_dir)
        out_stream_path = os.path.join(DockerJob.OUTPUT_DIR, 'test_video_TC.mp4')
        params = {
            'track': os.path.join(DockerJob.RESOURCES_DIR, 'test_video.mp4'),
            'targs': {
                'resolution': [160, 120]
            },
            'output_stream': out_stream_path,
            'command': Commands.TRANSCODE.value[0],
            'use_playlist': 0,
            'script_filepath': FFMPEG_BASE_SCRIPT
        }

        # porownac paramsy.json

        with self._create_test_job(script=FFMPEG_BASE_SCRIPT,
                                   params=params) as job:
            job.start()
            exit_code = job.wait(timeout=300)
            self.assertEqual(exit_code, 0)

        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ['test_video_TC.mp4'])

    def test_ffmpeg_merge_job(self):
        assert True
