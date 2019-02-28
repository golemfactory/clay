import os

from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.testutils import TestTaskIntegration


class TestffmpegIntegration(TestTaskIntegration):

    def setUp(self):
        super(TestffmpegIntegration, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.RESOURCE_STREAM = os.path.join(self.RESOURCES, 'test_video2.mp4')
        self.tt = ffmpegTaskTypeInfo()

    def test_simple_case(self):
        result_file = os.path.join(self.root_dir, 'test_simple_case.mp4')
        task_dict = {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': 2,
            'bid': 1.0,
            'resources': [self.RESOURCE_STREAM],
            'options': {
                'output_path': os.path.dirname(result_file),
                'video': {
                    'codec': 'h265',
                    'resolution': [320, 240],
                    'frame_rate': "25"
                },
                'container': os.path.splitext(result_file)[1][1:]
            }
        }

        task = self.add_task(task_dict)

        self.execute_task(task)

        asserts = [TestTaskIntegration.check_file_existence(result_file)]

        self.run_asserts(asserts)

