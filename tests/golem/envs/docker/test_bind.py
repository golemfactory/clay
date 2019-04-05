from pathlib import Path
from unittest import TestCase

from golem.envs.docker import DockerBind


class TestFromDict(TestCase):

    def test_missing_values(self):
        with self.assertRaises((TypeError, KeyError)):
            DockerBind.from_dict({})

    def test_extra_values(self):
        with self.assertRaises(TypeError):
            DockerBind.from_dict({
                'source': '/tmp/golem',
                'target': '/work',
                'mode': 'XD',
                'extra': 'value'
            })

    def test_default_values(self):
        bind = DockerBind.from_dict({
            'source': '/tmp/golem',
            'target': '/work',
        })

        self.assertEqual(bind.source, Path('/tmp/golem'))
        self.assertEqual(bind.target, '/work')
        self.assertIsNotNone(bind.mode)

    def test_custom_values(self):
        bind = DockerBind.from_dict({
            'source': '/tmp/golem',
            'target': '/work',
            'mode': 'XD',
        })

        self.assertEqual(bind.source, Path('/tmp/golem'))
        self.assertEqual(bind.target, '/work')
        self.assertEqual(bind.mode, 'XD')


class TestToDict(TestCase):

    def test_to_dict(self):
        bind_dict = DockerBind(
            source=Path('/tmp/golem'),
            target='/work',
            mode='XD'
        ).to_dict()

        # We cannot assert exact path string because it depends on OS
        self.assertEqual(Path(bind_dict.pop('source')), Path('/tmp/golem'))
        self.assertEqual(bind_dict, {
            'target': '/work',
            'mode': 'XD',
        })
