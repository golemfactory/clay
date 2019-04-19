import os
import logging

from apps.transcoding.common import TranscodingTaskBuilderException, \
    ffmpegException
from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.testutils import TestTaskIntegration


logger = logging.getLogger(__name__)


class TestffmpegIntegration(TestTaskIntegration):

    def setUp(self):
        super(TestffmpegIntegration, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.tt = ffmpegTaskTypeInfo()

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_simple_case(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2.mp4')
        result_file = os.path.join(self.root_dir, 'test_simple_case.mp4')
        task_def = {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': 2,
            'bid': 1.0,
            'resources': [resource_stream],
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

        self.execute_task(task_def)
        self.assertTrue(TestTaskIntegration.check_file_existence(result_file))

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_nonexistent_output_dir(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2.mp4')
        result_file = os.path.join(self.root_dir, 'nonexistent', 'path',
                                   'test_invalid_task_definition.mp4')
        task_def = {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': 2,
            'bid': 1.0,
            'resources': [resource_stream],
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

        logger.info("Starting test_nonexistent_output_dir execute_task")
        
        self.execute_task(task_def)

        logger.info("Finished test_nonexistent_output_dir execute_task")

        self.assertTrue(TestTaskIntegration.check_file_existence(result_file))
        self.assertTrue(TestTaskIntegration.check_dir_existence(
            os.path.dirname(result_file)))

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_nonexistent_resource(self):
        resource_stream = os.path.join(self.RESOURCES,
                                       'test_nonexistent_video.mp4')

        result_file = os.path.join(self.root_dir, 'test_nonexistent_video.mp4')
        task_def = {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:09:50',
            'subtasks_count': 2,
            'bid': 1.0,
            'resources': [resource_stream],
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

        with self.assertRaises(TranscodingTaskBuilderException):
            self.execute_task(task_def)

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_invalid_resource_stream(self):
        resource_stream = os.path.join(self.RESOURCES, 'invalid_test_video.mp4')
        result_file = os.path.join(self.root_dir,
                                   'test_invalid_resource_stream.mp4')
        task_def = {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:08:00',
            'subtasks_count': 2,
            'bid': 1.0,
            'resources': [resource_stream],
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

        with self.assertRaises(ffmpegException):
            self.execute_task(task_def)

    @TestTaskIntegration.dont_remove_dirs_on_failed_test
    def test_task_invalid_params(self):
        resource_stream = os.path.join(self.RESOURCES, 'test_video2.mp4')
        result_file = os.path.join(self.root_dir, 'test_invalid_params.mp4')
        task_def = {
            'type': 'FFMPEG',
            'name': os.path.splitext(os.path.basename(result_file))[0],
            'timeout': '0:10:00',
            'subtask_timeout': '0:08:00',
            'subtasks_count': 2,
            'bid': 1.0,
            'resources': [resource_stream],
            'options': {
                'output_path': os.path.dirname(result_file),
                'video': {
                    'codec': 'abcd',
                    'resolution': [320, 240],
                    'frame_rate': "25"
                },
                'container': os.path.splitext(result_file)[1][1:]
            }
        }

        with self.assertRaises(TranscodingTaskBuilderException):
            self.execute_task(task_def)
