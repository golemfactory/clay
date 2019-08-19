from pathlib import Path
from unittest import mock, TestCase

from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.envs import EnvSupportStatus
from golem.envs.docker import DockerBind
from golem.envs.docker.gpu import DockerGPUEnvironment, DockerNvidiaGPUConfig, \
    DockerGPUConfig, DockerGPURuntime
from golem.envs.docker.vendor import nvidia


@mock.patch(
    'golem.envs.docker.gpu.DockerGPUEnvironment._get_hypervisor_class',
    mock.Mock(return_value=DummyHypervisor)
)
class TestGPUEnvironment(TestCase):

    @mock.patch('golem.envs.docker.gpu.nvidia.is_supported', return_value=True)
    @mock.patch(
        'golem.envs.docker.gpu.DockerCPUEnvironment.supported',
        return_value=EnvSupportStatus(True)
    )
    def test_supported(self, mock_super_supported, *_):
        env = DockerGPUEnvironment(DockerNvidiaGPUConfig())
        status = env.supported()

        self.assertEqual(status, EnvSupportStatus(True))
        self.assertEqual(mock_super_supported.call_count, 1)

    @mock.patch('golem.envs.docker.gpu.nvidia.is_supported', return_value=False)
    @mock.patch('golem.envs.docker.gpu.DockerCPUEnvironment.supported')
    def test_not_supported(self, mock_super_supported, *_):
        env = DockerGPUEnvironment(DockerNvidiaGPUConfig())
        status = env.supported()
        expected_status = EnvSupportStatus(False, "No supported GPU found")

        self.assertEqual(status, expected_status)
        self.assertEqual(mock_super_supported.call_count, 0)

    def test_parse_gpu_config(self):
        config_dict = {'gpu_vendor': 'test'}
        parsed = DockerGPUEnvironment.parse_config(config_dict)
        self.assertIsInstance(parsed, DockerGPUConfig)
        self.assertNotIsInstance(parsed, DockerNvidiaGPUConfig)

    def test_parse_nvidia_gpu_config(self):
        config_dict = {'gpu_vendor': nvidia.VENDOR}
        parsed = DockerGPUEnvironment.parse_config(config_dict)
        self.assertIsInstance(parsed, DockerNvidiaGPUConfig)

    def test_validate_config_success(self):
        with mock.patch('golem.envs.docker.gpu.DockerGPUConfig.validate'):
            config = DockerGPUConfig()
            DockerGPUEnvironment(config)
            # pylint: disable=no-member
            self.assertEqual(config.validate.call_count, 1)

    def test_validate_config_failure(self):
        with mock.patch(
            'golem.envs.docker.gpu.DockerGPUConfig.validate',
            side_effect=ValueError
        ):
            config = DockerGPUConfig()
            with self.assertRaises(ValueError):
                DockerGPUEnvironment(config)
            # pylint: disable=no-member
            self.assertEqual(config.validate.call_count, 1)

    @mock.patch('golem.envs.docker.cpu.local_client')
    @mock.patch('golem.envs.docker.gpu.DockerGPUConfig.validate', mock.Mock())
    def test_runtime_protected(self, local_client):
        client = mock.Mock()
        local_client.return_value = client

        config = DockerGPUConfig()
        env = DockerGPUEnvironment(config)
        container_config = dict(runtime='test')

        binds = [DockerBind(source=Path('/tmp'), target='/tmp')]
        payload = mock.Mock(binds=binds, ports=[65000])

        with mock.patch(
            'golem.envs.docker.gpu.DockerGPUConfig.container_config',
            return_value=container_config
        ):
            runtime = env._create_runtime(config, payload)

        self.assertIsInstance(runtime, DockerGPURuntime)
        self.assertEqual(client.create_container_config.call_count, 1)
