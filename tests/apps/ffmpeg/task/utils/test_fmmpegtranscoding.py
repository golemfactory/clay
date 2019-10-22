import shutil
import uuid
from unittest import mock

from coverage.annotate import os
from ffmpeg_tools.formats import Container

from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from apps.transcoding.common import ffmpegException
from apps.transcoding.ffmpeg.utils import StreamOperator, Commands, \
    FFMPEG_BASE_SCRIPT
from golem.docker.job import DockerJob
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.resource.dirmanager import DirManager
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from tests.golem.docker.test_docker_job import TestDockerJob



@ci_skip
class TestffmpegTranscoding(TempDirFixture):
    def setUp(self):
        super(TestffmpegTranscoding, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__)))), 'resources')
        self.RESOURCE_STREAM = os.path.join(self.RESOURCES, 'test_video2')
        self.stream_operator = StreamOperator()
        self.dir_manager = DirManager(self.tempdir)
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dirs=[self.new_path],
            in_background=True)

    def test_extract_and_split_video(self):
        for parts in [1, 2]:
            with self.subTest('Testing splitting', parts=parts):
                chunks, _ = self.stream_operator.\
                    extract_video_streams_and_split(
                        self.RESOURCE_STREAM, parts, self.dir_manager,
                        str(uuid.uuid4()))
                self.assertEqual(len(chunks), parts)

    def test_extract_and_split_invalid_video(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator.extract_video_streams_and_split(
                os.path.join(self.RESOURCES,
                             'invalid_test_video2.mp4'),
                1, self.dir_manager,
                str(uuid.uuid4()))

    def test_extract_split_merge_and_replace_video(self):
        parts = 2
        task_id = str(uuid.uuid4())
        output_extension = ".mp4"
        output_name = f"test{output_extension}"
        output_container = Container.c_MP4
        output_dir = self.dir_manager.get_task_output_dir(task_id)

        chunks, _ = self.stream_operator.extract_video_streams_and_split(
            self.RESOURCE_STREAM, parts,
            self.dir_manager, task_id)
        self.assertEqual(len(chunks), parts)
        self.assertEqual(
            set(os.path.splitext(chunk)[1] for chunk in chunks),
            {''})
        segments = [os.path.join(output_dir, chunk) for chunk in chunks]

        assert len(segments) == parts
        tc_segments = list()
        for segment in segments:
            name, _ = os.path.splitext(os.path.basename(segment))
            transcoded_segment = os.path.join(
                os.path.dirname(segment),
                "{}_TC{}".format(name, output_extension))
            shutil.copy2(segment, transcoded_segment)
            assert os.path.isfile(transcoded_segment)
            tc_segments.append(transcoded_segment)

        self.stream_operator.merge_and_replace_video_streams(
            self.RESOURCE_STREAM,
            tc_segments,
            output_name,
            output_dir,
            output_container,
        )
        assert os.path.isfile(os.path.join(output_dir, 'merge',
                                           'output', output_name))

    def test_merge_and_replace_video_empty_dir(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator.merge_and_replace_video_streams(
                self.RESOURCE_STREAM,
                [],
                'output.mp4',
                self.tempdir,
                Container.c_MP4)

    def test_collect_nonexistent_results(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator._collect_files(
                self.tempdir,
                ['/tmp/testtest_TC.ts'],
                os.path.join(self.tempdir, "merge/resources"))

    def test_collect_files_second_result_nonexistent(self):
        result_path = self.RESOURCE_STREAM.replace(
            os.path.dirname(self.RESOURCE_STREAM), self.tempdir)
        shutil.copy2(self.RESOURCE_STREAM, result_path)
        assert os.path.isfile(result_path)

        with self.assertRaises(ffmpegException):
            self.stream_operator.\
                _collect_files(self.tempdir,
                               [result_path, '/tmp/test1234.mp4'],
                               os.path.join(self.tempdir, "merge/resources"))

    def test_collect_results(self):
        result_path = self.RESOURCE_STREAM.replace(
            os.path.dirname(self.RESOURCE_STREAM), self.tempdir)
        shutil.copy2(self.RESOURCE_STREAM, result_path)
        assert os.path.isfile(result_path)
        results = self.stream_operator. \
            _collect_files(self.tempdir, [result_path],
                           os.path.join(self.tempdir, "merge/resources"))
        assert len(results) == 1

        # _collect_files returns paths in docker filesystem
        assert results[0] == os.path.join("/golem/resources",
                                          os.path.basename(
                                              self.RESOURCE_STREAM))

    def test_prepare_merge_job(self):
        merge_job_info = self.stream_operator._prepare_merge_job(
            self.tempdir,
            [])
        (host_dirs, chunks_in_container) = merge_job_info

        self.assertEqual(len(chunks_in_container), 0)
        self.assertEqual(
            host_dirs['resources'],
            os.path.join(self.tempdir, 'merge', 'resources')
        )
        self.assertTrue(os.path.isdir(host_dirs['output']))
        self.assertEqual(
            host_dirs['output'],
            os.path.join(self.tempdir, 'merge', 'output'))
        self.assertTrue(os.path.isdir(host_dirs['output']))
        self.assertEqual(
            host_dirs['work'],
            os.path.join(self.tempdir, 'merge', 'work'))
        self.assertTrue(os.path.isdir(host_dirs['work']))

    def test_prepare_merge_job_nonexistent_results(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator._prepare_merge_job(
                self.tempdir,
                ['/tmp/testtest_TC.ts'])

    def test_merge_and_replace_nonexistent_files(self):
        with self.assertRaises(ffmpegException):
            self.stream_operator.merge_and_replace_video_streams(
                self.RESOURCE_STREAM,
                ['test_TC.ts'],
                'output.mp4',
                self.tempdir,
                Container.c_MP4,
            )

class TestffmpegDockerJob(TestDockerJob):
    def _get_test_repository(self):
        return ffmpegEnvironment.DOCKER_IMAGE

    def _get_test_tag(self):
        return ffmpegEnvironment.DOCKER_TAG

    def test_ffmpeg_trancoding_job(self):
        stream_file = os.path.join(
            os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.realpath(__file__)))),
                'resources'),
            'test_video.mp4')

        shutil.copy(str(stream_file), self.resources_dir)
        out_stream_path = os.path.join(DockerJob.OUTPUT_DIR,
                                       'test_video_TC.mp4')
        params = {
            'track': os.path.join(DockerJob.RESOURCES_DIR, 'test_video.mp4'),
            'targs': {
                'resolution': [160, 120]
            },
            'output_stream': out_stream_path,
            'command': Commands.TRANSCODE.value[0],
            'script_filepath': FFMPEG_BASE_SCRIPT
        }

        with self._create_test_job(script=FFMPEG_BASE_SCRIPT,
                                   params=params) as job:
            job.start()
            exit_code = job.wait(timeout=300)
            self.assertEqual(exit_code, 0)

        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ['test_video_TC.mp4'])
