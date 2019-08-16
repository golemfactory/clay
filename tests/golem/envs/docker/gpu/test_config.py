from pathlib import Path
from unittest import mock, TestCase

from golem.envs.docker.gpu import DockerGPUConfig, DockerNvidiaGPUConfig
from golem.envs.docker.vendor import nvidia


class TestNotImplemented(TestCase):

    def test_container_config_dict(self):
        with self.assertRaises(NotImplementedError):
            DockerGPUConfig().container_config()


class TestFromDict(TestCase):

    def test_missing_values(self):
        with self.assertRaises((TypeError, KeyError)):
            DockerGPUConfig.from_dict({})

    def test_extra_values(self):
        with self.assertRaises(TypeError):
            DockerGPUConfig.from_dict({
                'work_dirs': ['/tmp/golem'],
                'gpu_extra_test': ['i', 'n', 'v', 'a', 'l', 'i', 'd'],
            })

    def test_default_values(self):
        config = DockerGPUConfig.from_dict({
            'work_dirs': [],
            'gpu_vendor': 'TEST'
        })

        self.assertEqual(config.work_dirs, [])
        self.assertEqual(config.memory_mb, 1024)
        self.assertEqual(config.cpu_count, 1)
        self.assertEqual(config.gpu_vendor, 'TEST')
        self.assertEqual(config.gpu_devices, [])
        self.assertEqual(config.gpu_caps, [])
        self.assertEqual(config.gpu_requirements, [])

    def test_custom_values(self):
        config_dict = {
            'work_dirs': ['/tmp/golem'],
            'memory_mb': 2000,
            'cpu_count': 2,
            'gpu_vendor': 'TEST',
            'gpu_devices': ['device_1', 'device_2'],
            'gpu_caps': ['compute'],
            'gpu_requirements': [('driver', '>=1.0')]
        }
        config = DockerGPUConfig.from_dict(config_dict)

        self.assertEqual(config.work_dirs, [Path('/tmp/golem')])
        self.assertEqual(config.memory_mb, 2000)
        self.assertEqual(config.cpu_count, 2)
        self.assertEqual(config.gpu_vendor, 'TEST')
        self.assertEqual(config.gpu_devices, ['device_1', 'device_2'])
        self.assertEqual(config.gpu_caps, ['compute'])
        self.assertEqual(config.gpu_requirements, [('driver', '>=1.0')])


class TestToDict(TestCase):

    def test_to_dict(self):
        config_dict = DockerGPUConfig(
            work_dirs=[Path('/tmp/golem')],
            memory_mb=2137,
            cpu_count=12,
            gpu_vendor='TEST',
            gpu_devices=['device_1', 'device_2'],
            gpu_caps=['compute'],
            gpu_requirements=[('driver', '>=1.0')],
        ).to_dict()

        # We cannot assert exact path string because it depends on OS
        _work_dirs = config_dict.pop('work_dirs')
        self.assertEqual(Path(_work_dirs[0]), Path('/tmp/golem'))
        self.assertEqual(config_dict, {
            'memory_mb': 2137,
            'cpu_count': 12,
            'gpu_vendor': 'TEST',
            'gpu_devices': ['device_1', 'device_2'],
            'gpu_caps': ['compute'],
            'gpu_requirements': [('driver', '>=1.0')]
        })


class TestNvidiaConfig(TestCase):

    def test_default_values(self):
        config = DockerNvidiaGPUConfig()

        self.assertEqual(config.gpu_vendor, nvidia.VENDOR)
        self.assertEqual(config.gpu_devices, nvidia.DEFAULT_DEVICES)
        self.assertEqual(config.gpu_caps, nvidia.DEFAULT_CAPABILITIES)
        self.assertEqual(config.gpu_requirements, nvidia.DEFAULT_REQUIREMENTS)

    @mock.patch('golem.envs.docker.gpu.nvidia')
    def test_validate_calls(self, nvidia_mock):
        config = DockerNvidiaGPUConfig()
        config.validate()

        nvidia_mock.validate_devices.assert_called_with(
            config.gpu_devices)
        nvidia_mock.validate_capabilities.assert_called_with(
            config.gpu_caps)
        nvidia_mock.validate_requirements.assert_called_with(
            config.gpu_requirements)

    def test_container_config_dict(self):
        config = DockerNvidiaGPUConfig(
            gpu_vendor=nvidia.VENDOR,
            gpu_devices=['0', '1'],
            gpu_caps=['display', 'video'],
            gpu_requirements=[
                ('driver', '>=400.0'),
                ('brand', 'Tesla'),
            ]
        )
        self.assertEqual(config.container_config(), {
            'runtime': 'nvidia',
            'environment': {
                'GPU_ENABLED': '1',
                'GPU_VENDOR': nvidia.VENDOR,
                'NVIDIA_VISIBLE_DEVICES': '0,1',
                'NVIDIA_DRIVER_CAPABILITIES': 'display,video',
                'NVIDIA_REQUIRE_DRIVER': '>=400.0',
                'NVIDIA_REQUIRE_BRAND': 'Tesla'
            }
        })
