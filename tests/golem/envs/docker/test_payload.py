from unittest import TestCase
from unittest.mock import patch

from golem.envs.docker import DockerPayload


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
        self.assertEqual(payload.env, {})

    def test_custom_values(self):
        payload = DockerPayload.from_dict({
            'image': 'repo/img',
            'tag': '1.0',
            'env': {'var': 'value'},
            'command': 'cmd',
            'user': 'user',
            'work_dir': '/tmp/',
        })

        self.assertEqual(payload, DockerPayload(
            image='repo/img',
            tag='1.0',
            env={'var': 'value'},
            command='cmd',
            user='user',
            work_dir='/tmp/',
        ))


class TestToDict(TestCase):

    def test_to_dict(self):
        payload_dict = DockerPayload(
            image='repo/img',
            tag='1.0',
            env={'var': 'value'},
            command='cmd',
            user='user',
            work_dir='/tmp/',
        ).to_dict()

        self.assertEqual(payload_dict, {
            'image': 'repo/img',
            'tag': '1.0',
            'env': {'var': 'value'},
            'command': 'cmd',
            'user': 'user',
            'work_dir': '/tmp/',
        })
