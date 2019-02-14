import shutil
import uuid
import os
from unittest import mock

from coverage.annotate import os

from apps.transcoding.common import ffmpegException
from apps.transcoding.ffmpeg.utils import StreamOperator, Commands, \
    FFMPEG_BASE_SCRIPT, collect_files
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
        parts = 2
        task_id = str(uuid.uuid4())
        output_name = 'test.mp4'
        playlist_dir = self.dir_manager.get_task_output_dir(task_id)
        chunks = self.stream_operator.split_video(
            self.RESOURCE_STREAM, parts,
            self.dir_manager, task_id)
        self.assertEqual(len(chunks), parts)
        playlists = [os.path.join(playlist_dir, file)
                     for chunk in chunks for file in chunk if file.endswith('m3u8')]
        assert len(playlists) == parts
        tc_playlists = list()
        for playlist in playlists:
            name, ext = os.path.splitext(os.path.basename(playlist))
            transcoded = os.path.join(os.path.dirname(playlist),
                                      "{}_TC{}".format(name, ext))
            shutil.copy2(playlist, transcoded)
            assert os.path.isfile(transcoded)
            tc_playlists.append(transcoded)

        self.stream_operator.merge_video(output_name, playlist_dir,
                                         tc_playlists)
        assert os.path.isfile(os.path.join(playlist_dir, 'merge',
                                           'output', output_name))

    def test_merge_video_empty_dir(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator.merge_video('output.mp4', self.tempdir, [])

    def test_collect_nonexistent_results(self):
        with self.assertRaises(OSError):
            collect_files(self.tempdir, ['/tmp/testtest_TC.m3u8', '/tmp/testtest_TC.ts'])

    def test_collect_results(self):
        results = collect_files(self.tempdir, [self.RESOURCE_STREAM])
        assert len(results) == 1
        assert results[0] == os.path.join(self.tempdir, os.path.basename(self.RESOURCE_STREAM))

    def test_prepare_merge_job(self):
        resource_dir, output_dir, work_dir, chunks = \
            self.stream_operator.prepare_merge_job(self.tempdir, [self.RESOURCE_STREAM])

        assert len(chunks) == 1
        assert resource_dir == self.tempdir
        assert os.path.isdir(output_dir)
        assert output_dir == os.path.join(self.tempdir, 'merge', 'output')
        assert os.path.isdir(output_dir)
        assert work_dir == os.path.join(self.tempdir, 'merge', 'work')
        assert os.path.isdir(work_dir)

    def test_prepare_merge_job_nonexistent_results(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator.prepare_merge_job(self.tempdir, ['/tmp/testtest_TC.m3u8', '/tmp/testtest_TC.ts'])

    def test_merge_nonexistent_files(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator.merge_video('output.mp4', self.tempdir, ['test_TC.m3u8', 'test_TC.ts'])


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
