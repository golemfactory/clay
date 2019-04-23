from unittest import TestCase
from unittest.mock import patch, Mock

from golem.envs.docker import DockerPayload, DockerBind


class TestFromDict(TestCase):

    def test_missing_values(self):
        with self.assertRaises(TypeError):
            DockerPayload.from_dict({})

    def test_extra_values(self):
        with self.assertRaises(TypeError):
            DockerPayload.from_dict({
                'image': 'repo/img',
                'tag': '1.0',
                'extra': 'value'
            })

    def test_default_values(self):
        payload = DockerPayload.from_dict({
            'image': 'repo/img',
            'tag': '1.0',
        })

        self.assertEqual(payload.binds, [])
        self.assertEqual(payload.env, {})

    @patch('golem.envs.docker.DockerBind')
    def test_custom_values(self, docker_bind):
        bind_dict = Mock()
        payload = DockerPayload.from_dict({
            'image': 'repo/img',
            'tag': '1.0',
            'env': {'var': 'value'},
            'command': 'cmd',
            'user': 'user',
            'work_dir': '/tmp/',
            'binds': [bind_dict]
        })

        docker_bind.from_dict.assert_called_once_with(bind_dict)
        self.assertEqual(payload, DockerPayload(
            image='repo/img',
            tag='1.0',
            env={'var': 'value'},
            command='cmd',
            user='user',
            work_dir='/tmp/',
            binds=[docker_bind.from_dict()]
        ))


class TestToDict(TestCase):

    def test_to_dict(self):
        bind = Mock(spec=DockerBind)
        payload_dict = DockerPayload(
            image='repo/img',
            tag='1.0',
            env={'var': 'value'},
            command='cmd',
            user='user',
            work_dir='/tmp/',
            binds=[bind]
        ).to_dict()

        self.assertEqual(payload_dict, {
            'image': 'repo/img',
            'tag': '1.0',
            'env': {'var': 'value'},
            'command': 'cmd',
            'user': 'user',
            'work_dir': '/tmp/',
            'binds': [bind.to_dict()]
        })
