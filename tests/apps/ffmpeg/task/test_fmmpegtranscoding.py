import uuid
from unittest import mock

from apps.transcoding.common import ffmpegException
from apps.transcoding.ffmpeg.utils import StreamOperator
from coverage.annotate import os
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.resource.dirmanager import DirManager
from golem.testutils import TempDirFixture
from tests.golem.docker.test_docker_image import DockerTestCase


class TestffmpegTranscoding(TempDirFixture, DockerTestCase):
    def setUp(self):
        super(TestffmpegTranscoding, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.RESOURCE_STREAM = os.path.join(self.RESOURCES, 'test_video2.mp4')
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dir=self.new_path,
            in_background=True)

    def test_split_video(self):
        stream_operator = StreamOperator()
        for parts in [1, 2]:
            with self.subTest('Testing splitting', parts=parts):
                chunks = stream_operator.split_video(self.RESOURCE_STREAM, parts,
                                                 DirManager(self.tempdir),
                                                 str(uuid.uuid4()))
                self.assertEqual(len(chunks), parts)

    def test_split_invalid_video(self):
        stream_operator = StreamOperator()
        with self.assertRaises(ffmpegException):
            stream_operator.split_video(os.path.join(self.RESOURCES,
                                                     'invalid_test_video2.mp4'),
                                        1, DirManager(self.tempdir),
                                        str(uuid.uuid4()))
