from pathlib import Path
from unittest import TestCase

from golem.envs.docker.cpu import DockerCPUConfig


class TestFromDict(TestCase):

    def test_missing_values(self):
        with self.assertRaises((TypeError, KeyError)):
            DockerCPUConfig.from_dict({})

    def test_extra_values(self):
        with self.assertRaises(TypeError):
            DockerCPUConfig.from_dict({
                'work_dirs': ['/tmp/golem'],
                'memory_mb': 2000,
                'cpu_count': 2,
                'extra': 'value'
            })

    def test_default_values(self):
        config = DockerCPUConfig.from_dict({
            'work_dirs': ['/tmp/golem']
        })

        self.assertEqual(config.work_dirs, [Path('/tmp/golem')])
        self.assertIsNotNone(config.memory_mb)
        self.assertIsNotNone(config.cpu_count)

    def test_custom_values(self):
        config = DockerCPUConfig.from_dict({
            'work_dirs': ['/tmp/golem'],
            'memory_mb': 2137,
            'cpu_count': 12
        })

        self.assertEqual(config.work_dirs, [Path('/tmp/golem')])
        self.assertEqual(config.memory_mb, 2137)
        self.assertEqual(config.cpu_count, 12)


class TestToDict(TestCase):

    def test_to_dict(self):
        config_dict = DockerCPUConfig(
            work_dirs=[Path('/tmp/golem')],
            memory_mb=2137,
            cpu_count=12
        ).to_dict()

        # We cannot assert exact path string because it depends on OS
        _work_dirs = config_dict.pop('work_dirs')
        self.assertEqual(Path(_work_dirs[0]), Path('/tmp/golem'))
        self.assertEqual(config_dict, {
            'memory_mb': 2137,
            'cpu_count': 12
        })
