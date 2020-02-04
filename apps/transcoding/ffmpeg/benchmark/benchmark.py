import logging
import pathlib
import uuid
import sys

from os.path import dirname, join

from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.transcoding.ffmpeg.task import ffmpegTaskDefinition
from apps.transcoding.task import TranscodingTaskOptions

logger = logging.getLogger(__name__)


class ffmpegBenchmark(CoreBenchmark):
    # TODO, FIXME
    def __init__(self):
        self._normalization_constant = 1000
        super(ffmpegBenchmark, self).__init__()

        if hasattr(sys, 'frozen') and sys.frozen:
            exec_dir = dirname(sys.executable)
            video_dir = join(exec_dir, 'examples', 'transcoding')
        else:
            video_dir = pathlib.Path(__file__).resolve().parent

        video = video_dir / 'resources' / 'test_video.mp4'

        task_def = ffmpegTaskDefinition()
        task_def.task_id = str(uuid.uuid4())
        task_def.resources = [video]
        task_def.options.video_params = TranscodingTaskOptions.VideoParams(
            VideoCodec.H_264, '18k', 25, (320, 240))
        task_def.options.output_container = Container.c_MP4
        task_def.options.input_stream_path = video
        task_def.subtasks_count = 1
        self._task_definition = task_def

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result):
        return True
