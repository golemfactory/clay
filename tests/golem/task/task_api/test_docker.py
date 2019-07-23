from pathlib import Path
from unittest import TestCase

from golem_task_api import constants as api_constants

from golem.envs.docker import DockerPrerequisites, DockerBind
from golem.task.task_api.docker import DockerTaskApiPayloadBuilder


class TestDockerPayloadBuilder(TestCase):
    def test_create_task_api_payload(self):
        prereq = DockerPrerequisites(image='image', tag='tag')
        shared_dir = Path('shared_dir')
        command = 'cmd'
        port = 4444

        payload = DockerTaskApiPayloadBuilder.create_payload(
            prereq,
            shared_dir,
            command,
            port,
        )

        self.assertEqual(prereq.image, payload.image)
        self.assertEqual(prereq.tag, payload.tag)
        self.assertEqual(command, payload.command)
        self.assertEqual([port], payload.ports)
        bind = \
            DockerBind(source=shared_dir, target=f'/{api_constants.WORK_DIR}')
        self.assertEqual([bind], payload.binds)
