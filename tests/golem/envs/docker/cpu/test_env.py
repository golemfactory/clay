from logging import Logger
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock, ANY

from twisted.trial.unittest import TestCase

from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.task_thread import DockerBind
from golem.envs import EnvStatus
from golem.envs.docker import DockerPrerequisites, DockerRuntimePayload
from golem.envs.docker.cpu import (
    DockerCPUEnvironment,
    DockerCPUConfig,
)

cpu = CONSTRAINT_KEYS['cpu']
mem = CONSTRAINT_KEYS['mem']


def patch_cpu(name: str, *args, **kwargs):
    return patch(f'golem.envs.docker.cpu.{name}', *args, **kwargs)


def patch_handler(name: str, *args, **kwargs):
    return patch_cpu(f'DockerCommandHandler.{name}', *args, **kwargs)


def patch_env(name: str, *args, **kwargs):
    return patch_cpu(f'DockerCPUEnvironment.{name}', *args, **kwargs)


# pylint: disable=too-many-arguments
def patch_hypervisors(linux=False, windows=False, mac_os=False, hyperv=False,
                      vbox=False, docker_for_mac=False):
    def _wrapper(func):
        return_values = {
            'is_linux': linux,
            'is_windows': windows,
            'is_osx': mac_os,
            'HyperVHypervisor.is_available': hyperv,
            'VirtualBoxHypervisor.is_available': vbox,
            'DockerForMac.is_available': docker_for_mac,
        }
        for k, v in return_values.items():
            func = patch_cpu(k, return_value=v)(func)
        return func
    return _wrapper


class TestSupported(TestCase):

    @patch_env('_get_hypervisor_class', return_value=None)
    def test_no_hypervisor(self, *_):
        self.assertFalse(DockerCPUEnvironment.supported().supported)

    @patch_env('_get_hypervisor_class')
    def test_ok(self, *_):
        self.assertTrue(DockerCPUEnvironment.supported().supported)


class TestGetHypervisorClass(TestCase):

    @patch_hypervisors()
    def test_unknown_os(self, *_):
        self.assertIsNone(DockerCPUEnvironment._get_hypervisor_class())

    @patch_hypervisors(linux=True)
    def test_linux(self, *_):
        self.assertEqual(
            DockerCPUEnvironment._get_hypervisor_class(), DummyHypervisor)

    @patch_hypervisors(windows=True)
    def test_windows_no_available_hypervisor(self, *_):
        self.assertIsNone(DockerCPUEnvironment._get_hypervisor_class())

    @patch_hypervisors(windows=True, hyperv=True)
    def test_windows_only_hyperv(self, *_):
        self.assertEqual(
            DockerCPUEnvironment._get_hypervisor_class(), HyperVHypervisor)

    @patch_hypervisors(windows=True, vbox=True)
    def test_windows_only_virtualbox(self, *_):
        self.assertEqual(
            DockerCPUEnvironment._get_hypervisor_class(), VirtualBoxHypervisor)

    @patch_hypervisors(windows=True, hyperv=True, vbox=True)
    def test_windows_hyperv_and_virtualbox(self, *_):
        # If this was possible (but isn't) Hyper-V should be preferred
        self.assertEqual(
            DockerCPUEnvironment._get_hypervisor_class(), HyperVHypervisor)

    @patch_hypervisors(mac_os=True)
    def test_macos_no_available_hypervisor(self, *_):
        self.assertIsNone(DockerCPUEnvironment._get_hypervisor_class())

    @patch_hypervisors(mac_os=True, docker_for_mac=True)
    def test_macos_only_docker_for_mac(self, *_):
        self.assertEqual(
            DockerCPUEnvironment._get_hypervisor_class(), DockerForMac)


class TestInit(TestCase):

    @patch_env('_validate_config', side_effect=ValueError)
    def test_invalid_config(self, *_):
        with self.assertRaises(ValueError):
            DockerCPUEnvironment(Mock(spec=DockerCPUConfig), dev_mode=False)

    @patch_env('_validate_config')
    @patch_env('_get_hypervisor_class', return_value=None)
    def test_no_hypervisor(self, *_):
        with self.assertRaises(EnvironmentError):
            DockerCPUEnvironment(Mock(spec=DockerCPUConfig), dev_mode=False)

    @patch_env('_constrain_hypervisor')
    @patch_env('_update_work_dirs')
    @patch_env('_validate_config')
    @patch_env('_get_hypervisor_class')
    def test_ok(
            self,
            get_hypervisor,
            validate_config,
            update_work_dirs,
            constrain_hypervisor):
        config = DockerCPUConfig(
            work_dirs=[Mock(spec=Path)],
            memory_mb=2137,
            cpu_count=12
        )

        def _instance(get_config_fn):
            self.assertDictEqual(get_config_fn(), {
                mem: config.memory_mb,
                cpu: config.cpu_count
            })
        get_hypervisor.return_value.instance = _instance

        DockerCPUEnvironment(config, dev_mode=False)

        get_hypervisor.assert_called_once()
        validate_config.assert_called_once_with(config)
        update_work_dirs.assert_called_once_with(config.work_dirs)
        constrain_hypervisor.assert_called_once_with(config)


class TestDockerCPUEnv(TestCase):

    @patch_env('_constrain_hypervisor')
    @patch_env('_update_work_dirs')
    @patch_env('_validate_config')
    @patch_env('_get_hypervisor_class')
    def setUp(self, get_hypervisor, *_):  # pylint: disable=arguments-differ
        self.hypervisor = Mock(spec=Hypervisor)
        self.config = DockerCPUConfig(work_dirs=[Path('test')])
        get_hypervisor.return_value.instance.return_value = self.hypervisor
        self.logger = Mock(spec=Logger)
        with patch_cpu('logger', self.logger):
            self.env = DockerCPUEnvironment(self.config, dev_mode=False)

    def _patch_async(self, name, *args, **kwargs):
        patcher = patch_cpu(name, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _patch_env_async(self, name, *args, **kwargs):
        patcher = patch_env(name, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()


class TestPrepare(TestDockerCPUEnv):

    def test_enabled_status(self):
        self.env._status = EnvStatus.ENABLED
        with self.assertRaises(ValueError):
            self.env.prepare()

    def test_preparing_status(self):
        self.env._status = EnvStatus.PREPARING
        with self.assertRaises(ValueError):
            self.env.prepare()

    def test_cleaning_up_status(self):
        self.env._status = EnvStatus.CLEANING_UP
        with self.assertRaises(ValueError):
            self.env.prepare()

    def test_hypervisor_setup_error(self):
        error = OSError("test")
        self.hypervisor.setup.side_effect = error
        error_occurred = self._patch_env_async('_error_occurred')

        deferred = self.env.prepare()
        self.assertEqual(self.env.status(), EnvStatus.PREPARING)
        deferred = self.assertFailure(deferred, OSError)

        def _check(_):
            error_occurred.assert_called_once_with(error, ANY)
        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        env_enabled = self._patch_env_async('_env_enabled')

        deferred = self.env.prepare()
        self.assertEqual(self.env.status(), EnvStatus.PREPARING)

        def _check(_):
            env_enabled.assert_called_once_with()
        deferred.addCallback(_check)
        return deferred


class TestCleanup(TestDockerCPUEnv):

    def test_disabled_status(self):
        with self.assertRaises(ValueError):
            self.env.clean_up()

    def test_preparing_status(self):
        self.env._status = EnvStatus.PREPARING
        with self.assertRaises(ValueError):
            self.env.clean_up()

    def test_cleaning_up_status(self):
        self.env._status = EnvStatus.CLEANING_UP
        with self.assertRaises(ValueError):
            self.env.clean_up()

    def test_hypervisor_quit_error(self):
        self.env._status = EnvStatus.ENABLED
        error = OSError("test")
        self.hypervisor.quit.side_effect = error
        error_occurred = self._patch_env_async('_error_occurred')

        deferred = self.env.clean_up()
        self.assertEqual(self.env.status(), EnvStatus.CLEANING_UP)
        deferred = self.assertFailure(deferred, OSError)

        def _check(_):
            error_occurred.assert_called_once_with(error, ANY)
        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        self.env._status = EnvStatus.ENABLED
        env_disabled = self._patch_env_async('_env_disabled')

        deferred = self.env.clean_up()
        self.assertEqual(self.env.status(), EnvStatus.CLEANING_UP)

        def _check(_):
            env_disabled.assert_called_once_with()
        deferred.addCallback(_check)
        return deferred


class TestInstallPrerequisites(TestDockerCPUEnv):

    def test_wrong_type(self):
        with self.assertRaises(AssertionError):
            self.env.install_prerequisites(object())

    def test_env_disabled(self):
        prereqs = Mock(spec=DockerPrerequisites)
        with self.assertRaises(ValueError):
            self.env.install_prerequisites(prereqs)

    def test_pull_image_error(self):
        error = OSError("test")
        local_client = MagicMock()
        local_client.return_value.pull.side_effect = error
        self._patch_async("local_client", local_client)
        self._patch_async('Whitelist.is_whitelisted', return_value=True)
        error_occurred = self._patch_env_async('_error_occurred')
        self.env._status = EnvStatus.ENABLED

        prereqs = Mock(spec=DockerPrerequisites)
        deferred = self.env.install_prerequisites(prereqs)
        deferred = self.assertFailure(deferred, OSError)

        def _check(_):
            error_occurred.assert_called_once_with(error, ANY, set_status=False)
        deferred.addCallback(_check)
        return deferred

    def test_not_whitelisted(self):
        self.env._status = EnvStatus.ENABLED
        self._patch_async('Whitelist.is_whitelisted', return_value=False)
        prereqs_installed = self._patch_env_async('_prerequisites_installed')

        prereqs = Mock(spec=DockerPrerequisites)
        deferred = self.env.install_prerequisites(prereqs)

        def _check(return_value):
            self.assertFalse(return_value)
            prereqs_installed.assert_not_called()
        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        self.env._status = EnvStatus.ENABLED
        self._patch_async('Whitelist.is_whitelisted', return_value=True)
        prereqs_installed = self._patch_env_async('_prerequisites_installed')
        local_client = self._patch_async('local_client')

        prereqs = Mock(spec=DockerPrerequisites)
        deferred = self.env.install_prerequisites(prereqs)

        def _check(return_value):
            self.assertTrue(return_value)
            prereqs_installed.assert_called_once_with(prereqs)
            local_client().pull.assert_called_once_with(
                prereqs.image,
                tag=prereqs.tag
            )
        deferred.addCallback(_check)
        return deferred


class TestUpdateConfig(TestDockerCPUEnv):

    def test_wrong_type(self):
        with self.assertRaises(AssertionError):
            self.env.update_config(object())

    @patch_env('_validate_config', side_effect=ValueError)
    def test_invalid_config(self, validate):
        config = Mock(spec=DockerCPUConfig)
        with self.assertRaises(ValueError):
            self.env.update_config(config)

        validate.assert_called_once_with(config)

    @patch_env('_update_work_dirs')
    @patch_env('_config_updated')
    @patch_env('_validate_config')
    @patch_env('_constrain_hypervisor')
    def test_work_dirs_unchanged(
            self, constrain, validate, config_updated, update_work_dirs):
        config = DockerCPUConfig(work_dirs=self.config.work_dirs)
        self.env.update_config(config)

        validate.assert_called_once_with(config)
        constrain.assert_called_once_with(config)
        update_work_dirs.assert_not_called()
        config_updated.assert_called_once_with(config)

    @patch_env('_update_work_dirs')
    @patch_env('_config_updated')
    @patch_env('_validate_config')
    @patch_env('_constrain_hypervisor')
    def test_config_changed(
            self, constrain, validate, config_updated, update_work_dirs):
        config = DockerCPUConfig(
            work_dirs=[Path('test_2')],
            memory_mb=2137,
            cpu_count=12
        )
        self.env.update_config(config)

        validate.assert_called_once_with(config)
        constrain.assert_called_once_with(config)
        update_work_dirs.assert_called_once_with(config.work_dirs)
        config_updated.assert_called_once_with(config)
        self.assertEqual(self.env.config(), config)


class TestValidateConfig(TestCase):

    @patch('pathlib.Path.is_dir', return_value=False)
    def test_invalid_work_dir(self, *_):
        config = DockerCPUConfig(work_dirs=[Path('/a')])
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    @patch('pathlib.Path.is_dir', return_value=True)
    def test_too_low_memory(self, *_):
        config = DockerCPUConfig(work_dirs=[Path('/a')], memory_mb=0)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    @patch('pathlib.Path.is_dir', return_value=True)
    def test_too_few_memory(self, *_):
        config = DockerCPUConfig(work_dirs=[Path('/a')], cpu_count=0)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    @patch('pathlib.Path.is_dir', return_value=True)
    def test_valid_config(self, *_):
        config = DockerCPUConfig(work_dirs=[Path('/a')])
        DockerCPUEnvironment._validate_config(config)

    @patch('pathlib.Path.is_dir', return_value=True)
    def test_valid_multi_work_dir(self, *_):
        work_dirs = [Path('/a'), Path('/b')]
        config = DockerCPUConfig(work_dirs=work_dirs)
        DockerCPUEnvironment._validate_config(config)

    @patch('pathlib.Path.is_dir', return_value=True)
    def test_multi_work_dir_same_error(self, *_):
        work_dirs = [Path('/a'), Path('/a')]
        config = DockerCPUConfig(work_dirs=work_dirs)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    @patch('pathlib.Path.is_dir', return_value=True)
    def test_multi_work_dir_child_error(self, *_):
        work_dirs = [Path('/a/b'), Path('/a')]
        config = DockerCPUConfig(work_dirs=work_dirs)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    @patch('pathlib.Path.is_dir', return_value=True)
    def test_multi_work_dir_parent_error(self, *_):
        work_dirs = [Path('/a'), Path('/a/b')]
        config = DockerCPUConfig(work_dirs=work_dirs)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)


class TestUpdateWorkDir(TestDockerCPUEnv):

    @patch_env('_error_occurred')
    def test_hypervisor_error(self, error_occurred):
        work_dir = Mock(spec=Path)
        error = OSError("test")
        self.hypervisor.update_work_dirs.side_effect = error

        with self.assertRaises(OSError):
            self.env._update_work_dirs([work_dir])
        error_occurred.assert_called_once_with(error, ANY)

    def test_ok(self):
        work_dirs = [Mock(spec=Path)]
        self.env._update_work_dirs(work_dirs)
        self.hypervisor.update_work_dirs.assert_called_once_with(work_dirs)


class TestConstrainHypervisor(TestDockerCPUEnv):

    def test_config_unchanged(self):
        config = DockerCPUConfig(work_dirs=[Mock()])
        self.hypervisor.constraints.return_value = {
            mem: config.memory_mb,
            cpu: config.cpu_count
        }

        self.env._constrain_hypervisor(config)
        self.hypervisor.reconfig_ctx.assert_not_called()
        self.hypervisor.constrain.assert_not_called()

    @patch_env('_error_occurred')
    def test_constrain_error(self, error_occurred):
        config = DockerCPUConfig(
            work_dirs=[Mock()],
            memory_mb=1000,
            cpu_count=1
        )
        self.hypervisor.constraints.return_value = {
            mem: 2000,
            cpu: 2
        }
        self.hypervisor.reconfig_ctx = MagicMock()
        error = OSError("test")
        self.hypervisor.constrain.side_effect = error

        with self.assertRaises(OSError):
            self.env._constrain_hypervisor(config)
        error_occurred.assert_called_once_with(error, ANY)

    def test_config_changed(self):
        config = DockerCPUConfig(
            work_dirs=[Mock()],
            memory_mb=1000,
            cpu_count=1
        )
        self.hypervisor.constraints.return_value = {
            mem: 2000,
            cpu: 2
        }
        self.hypervisor.reconfig_ctx = MagicMock()

        self.env._constrain_hypervisor(config)
        self.hypervisor.reconfig_ctx.assert_called_once()
        self.hypervisor.constrain.assert_called_once_with(**{
            mem: 1000,
            cpu: 1
        })


def mock_docker_runtime_payload(binds=None, ports=None):
    return Mock(spec=DockerRuntimePayload, binds=binds, ports=ports)


class TestRuntime(TestDockerCPUEnv):

    def test_invalid_payload_class(self):
        with self.assertRaises(AssertionError):
            self.env.runtime(object())

    @patch_cpu('Whitelist.is_whitelisted', return_value=True)
    def test_invalid_config_class(self, _):
        with self.assertRaises(AssertionError):
            self.env.runtime(mock_docker_runtime_payload(), config=object())

    @patch_cpu('Whitelist.is_whitelisted', return_value=False)
    def test_image_not_whitelisted(self, is_whitelisted):
        payload = mock_docker_runtime_payload()
        with self.assertRaises(RuntimeError):
            self.env.runtime(payload)
        is_whitelisted.assert_called_once_with(payload.image)

    @patch_cpu('Whitelist.is_whitelisted', return_value=True)
    @patch_cpu('local_client')
    def test_container_config_passed(self, local_client, _):
        local_client.return_value = local_client
        method = '_create_container_config'
        return_value = {'custom_key': 'custom_value'}

        with patch.object(self.env, method, return_value=return_value):
            self.env._create_runtime(Mock(), Mock())

        local_client.create_container_config.assert_called_once_with(
            **return_value)


class TestCreateHostConfig(TestDockerCPUEnv):

    @patch_cpu('hardware.cpus', return_value=[1, 2, 3, 4, 5, 6])
    @patch_cpu('local_client')
    def test_no_shared_dir(self, local_client, _):
        config = DockerCPUConfig(
            work_dirs=[Mock(spec=Path)],
            cpu_count=4,
            memory_mb=2137
        )
        payload = mock_docker_runtime_payload()
        host_config = self.env._create_host_config(config, payload)

        self.hypervisor.create_volumes.assert_not_called()
        local_client().create_host_config.assert_called_once_with(
            cpuset_cpus='1,2,3,4',
            mem_limit='2137m',
            binds=None,
            port_bindings=None,
            privileged=False,
            network_mode=DockerCPUEnvironment.NETWORK_MODE,
            dns=DockerCPUEnvironment.DNS_SERVERS,
            dns_search=DockerCPUEnvironment.DNS_SEARCH_DOMAINS,
            cap_drop=DockerCPUEnvironment.DROPPED_KERNEL_CAPABILITIES
        )
        self.assertEqual(host_config, local_client().create_host_config())

    @patch_cpu('hardware.cpus', return_value=[1, 2, 3, 4, 5, 6])
    @patch_cpu('local_client')
    def test_shared_dir(self, local_client, _):
        config = DockerCPUConfig(
            work_dirs=[Mock(spec=Path)],
            cpu_count=4,
            memory_mb=2137
        )
        target_dir = '/foo'
        docker_bind = Mock(spec=DockerBind, target=target_dir)
        payload = mock_docker_runtime_payload(binds=[docker_bind])
        host_config = self.env._create_host_config(config, payload)

        self.hypervisor.create_volumes.assert_called_once_with([docker_bind])
        local_client().create_host_config.assert_called_once_with(
            cpuset_cpus='1,2,3,4',
            mem_limit='2137m',
            binds=self.hypervisor.create_volumes(),
            port_bindings=None,
            privileged=False,
            network_mode=DockerCPUEnvironment.NETWORK_MODE,
            dns=DockerCPUEnvironment.DNS_SERVERS,
            dns_search=DockerCPUEnvironment.DNS_SEARCH_DOMAINS,
            cap_drop=DockerCPUEnvironment.DROPPED_KERNEL_CAPABILITIES
        )
        self.assertEqual(host_config, local_client().create_host_config())

    @patch_cpu('local_client')
    def test_published_ports(self, local_client):
        config = Mock(spec=DockerCPUConfig, cpu_count=2)
        port = 3333
        payload = mock_docker_runtime_payload(ports=[port])
        host_config = self.env._create_host_config(config, payload)

        local_client().create_host_config.assert_called_once_with(
            cpuset_cpus=ANY,
            mem_limit=ANY,
            binds=ANY,
            port_bindings={
                f'{port}/tcp': {'HostIp': '0.0.0.0', 'HostPort': port},
            },
            privileged=ANY,
            network_mode=ANY,
            dns=ANY,
            dns_search=ANY,
            cap_drop=ANY,
        )
        self.assertEqual(host_config, local_client().create_host_config())


class TestCreateContainerConfig(TestDockerCPUEnv):

    @patch_cpu('local_client')
    @patch_cpu('DockerCPURuntime')
    def test_custom_config(self, runtime, _):
        payload = DockerRuntimePayload(
            image='repo/img',
            tag='1.0',
            command='cmd',
            env={'key': 'val'},
            user='user',
            work_dir='/test',
            binds=[DockerBind(source=Path('/test'), target='/test')],
        )

        with patch.object(self.env, '_create_host_config', return_value={}):
            self.env._create_runtime(self.config, payload)

        container_config = dict(
            image='repo/img:1.0',
            command='cmd',
            volumes=['/test'],
            environment={'key': 'val'},
            ports=None,
            user='user',
            working_dir='/test',
            host_config={},
            stdin_open=True)

        runtime.assert_called_once_with(
            container_config,
            ANY,
            runtime_logger=ANY)
