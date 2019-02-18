import os

from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.testutils import TestTaskIntegration


class TestffmpegIntegration(TestTaskIntegration):

    def setUp(self):
        super(TestffmpegIntegration, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.RESOURCE_STREAM = os.path.join(self.RESOURCES, 'test_video.mp4')
        self.tt = ffmpegTaskTypeInfo()

    def test_simple_case(self):
        taks_dict = {
            'type': 'FFMPEG',
            'name': 'test task',
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': 1,
            'bid': 1.0,
            'resources': [self.RESOURCE_STREAM],
            'options': {
                'output_path': '/tmp/test6969',
                'video': {
                    'codec': 'libx264',
                    'resolution': [320, 240],
                    'frame_rate': "25"
                },
                'container': 'mp4'
            }
        }

        task = self.build_task(ffmpegTaskTypeInfo(), taks_dict)
        self.execute_subtasks(1)
