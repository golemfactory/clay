import tempfile

import pytest
from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from coverage.annotate import os
from golem.testutils import TempDirFixture


class ffmpegTaskTest(TempDirFixture):
    def setUp(self):
        super(ffmpegTaskTest, self).setUp()
        self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))), 'resources')
        self.RESOURCE_STREAM = os.path.join(self.RESOURCES, 'test_video.mp4')

    @property
    def _task_dictionary(self):
        return {
            'type': "FFMPEG",
            'name': 'test task',
            'timeout': "0:10:00",
            "subtask_timeout": "0:09:50",
            "subtasks_count": 1,
            "bid": 1.0,
            "resources": self.RESOURCE_STREAM,
            "options": {
                "output_path": '',
                "video": {
                    "resolution": [320, 240]
                }
            }
        }

    def test_build_task_def_from_task_type(self):
        task_type = ffmpegTaskTypeInfo()
        d = self._task_dictionary
        task_type.task_builder_type.build_definition(task_type, d, False)
      #  for min in [True, False]:
       #     with self.subTest(msg='Test with minimal definition', p1=min):
        #        task_type.task_builder_type.build_definition(task_type, d, min)


        # definition.task_id = CoreTask.create_task_id(self.keys_auth.public_key)
        # definition.concent_enabled = dictionary.get('concent_enabled', False)
        # builder = builder_type(self.node, definition, self.dir_manager)
        #
        # return builder.build()

        pass
