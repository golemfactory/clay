import logging
import pathlib
import uuid

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.transcoding.common import AudioCodec, VideoCodec, Container
from apps.transcoding.ffmpeg.task import ffmpegTaskDefinition
from apps.transcoding.task import TranscodingTaskDefinition

logger = logging.getLogger(__name__)


class ffmpegBenchmark(CoreBenchmark):
    # TODO, FIXME
    def __init__(self):
        self._normalization_constant = 1000
        super(ffmpegBenchmark, self).__init__()

        video = pathlib.Path(__file__).resolve().parent
        video = video / 'resources' / 'test_video.mp4'

        self._task_definition = ffmpegTaskDefinition(
            video, TranscodingTaskDefinition.TranscodingAudioParams(
                AudioCodec.AAC),
            TranscodingTaskDefinition.TranscodingVideoParams(VideoCodec.MPEG_4),
            Container.MP4, str(uuid.uuid4()), 2)

        self._task_definition.resources = [video]
#        self._task_definition.total_tasks = 1

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        return True
