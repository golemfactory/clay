from logging import Logger
from pathlib import Path
from subprocess import SubprocessError
from unittest.mock import patch as _patch, Mock, MagicMock, ANY

from twisted.trial.unittest import TestCase

from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.docker.task_thread import DockerBind
from golem.envs import EnvStatus
from golem.envs.docker import DockerPrerequisites, DockerPayload
from golem.envs.docker.cpu import DockerCPUEnvironment, DockerCPUConfig

cpu = CONSTRAINT_KEYS['cpu']
mem = CONSTRAINT_KEYS['mem']


def patch(name: str, *args, **kwargs):
    return _patch(f'golem.envs.docker.cpu.{name}', *args, **kwargs)


def patch_handler(name: str, *args, **kwargs):
    return patch(f'DockerCommandHandler.{name}', *args, **kwargs)


def patch_env(name: str, *args, **kwargs):
    return patch(f'DockerCPUEnvironment.{name}', *args, **kwargs)


# pylint: disable=too-many-arguments
def patch_hypervisors(linux=False, windows=False, mac_os=False, hyperv=False,
                      vbox=False, docker_for_mac=False, xhyve=False):
    def _wrapper(func):
        return_values = {
            'is_linux': linux,
            'is_windows': windows,
            'is_osx': mac_os,
            'HyperVHypervisor.is_available': hyperv,
            'VirtualBoxHypervisor.is_available': vbox,
            'DockerForMac.is_available': docker_for_mac,
            'XhyveHypervisor.is_available': xhyve
        }
        for k, v in return_values.items():
            func = patch(k, return_value=v)(func)
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

    @patch_hypervisors(mac_os=True, xhyve=True)
    def test_macos_only_xhyve(self, *_):
        self.assertEqual(
            DockerCPUEnvironment._get_hypervisor_class(), XhyveHypervisor)

    @patch_hypervisors(mac_os=True, docker_for_mac=True, xhyve=True)
    def test_macos_docker_for_mac_and_xhyve(self, *_):
        self.assertEqual(
            DockerCPUEnvironment._get_hypervisor_class(), DockerForMac)


class TestInit(TestCase):

    @patch_env('_validate_config', side_effect=ValueError)
    def test_invalid_config(self, *_):
        with self.assertRaises(ValueError):
            DockerCPUEnvironment(Mock(spec=DockerCPUConfig))

    @patch_env('_validate_config')
    @patch_env('_get_hypervisor_class', return_value=None)
    def test_no_hypervisor(self, *_):
        with self.assertRaises(EnvironmentError):
            DockerCPUEnvironment(Mock(spec=DockerCPUConfig))

    @patch_env('_validate_config')
    @patch_env('_get_hypervisor_class')
    def test_ok(self, get_hypervisor, *_):
        config = DockerCPUConfig(
            work_dir=Mock(spec=Path),
            memory_mb=2137,
            cpu_count=12
        )

        def _instance(get_config_fn):
            self.assertDictEqual(get_config_fn(), {
                mem: config.memory_mb,
                cpu: config.cpu_count
            })
        get_hypervisor.return_value.instance = _instance

        DockerCPUEnvironment(config)


class TestDockerCPUEnv(TestCase):

    @patch_env('_validate_config')
    @patch_env('_get_hypervisor_class')
    def setUp(self, get_hypervisor, _):  # pylint: disable=arguments-differ
        self.hypervisor = Mock(spec=Hypervisor)
        self.config = DockerCPUConfig(work_dir=Mock())
        get_hypervisor.return_value.instance.return_value = self.hypervisor
        self.logger = Mock(spec=Logger)
        with patch('logger', self.logger):
            self.env = DockerCPUEnvironment(self.config)

    def _patch_async(self, name, *args, **kwargs):
        patcher = patch(name, *args, **kwargs)
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


class TestMetadata(TestCase):

    def test_metadata(self):
        metadata = DockerCPUEnvironment.metadata()
        self.assertEqual(metadata.id, DockerCPUEnvironment.ENV_ID)
        self.assertEqual(
            metadata.description, DockerCPUEnvironment.ENV_DESCRIPTION)


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

    def test_enabled_status(self):
        self.env._status = EnvStatus.ENABLED
        with self.assertRaises(ValueError):
            self.env.update_config(Mock(spec=DockerCPUConfig))

    @patch_env('_validate_config', side_effect=ValueError)
    def test_invalid_config(self, validate):
        config = Mock(spec=DockerCPUConfig)
        with self.assertRaises(ValueError):
            self.env.update_config(config)

        validate.assert_called_once_with(config)

    @patch_env('_update_work_dir')
    @patch_env('_config_updated')
    @patch_env('_validate_config')
    @patch_env('_constrain_hypervisor')
    def test_work_dir_unchanged(
            self, constrain, validate, config_updated, update_work_dir):
        config = DockerCPUConfig(work_dir=self.config.work_dir)
        self.env.update_config(config)

        validate.assert_called_once_with(config)
        constrain.assert_called_once_with(config)
        update_work_dir.assert_not_called()
        config_updated.assert_called_once_with(config)

    @patch_env('_update_work_dir')
    @patch_env('_config_updated')
    @patch_env('_validate_config')
    @patch_env('_constrain_hypervisor')
    def test_config_changed(
            self, constrain, validate, config_updated, update_work_dir):
        config = DockerCPUConfig(
            work_dir=Mock(),
            memory_mb=2137,
            cpu_count=12
        )
        self.env.update_config(config)

        validate.assert_called_once_with(config)
        constrain.assert_called_once_with(config)
        update_work_dir.assert_called_once_with(config.work_dir)
        config_updated.assert_called_once_with(config)
        self.assertEqual(self.env.config(), config)


class TestValidateConfig(TestCase):

    @staticmethod
    def _get_config(work_dir_exists=True, **kwargs):
        work_dir = Mock(spec=Path)
        work_dir.is_dir.return_value = work_dir_exists
        return DockerCPUConfig(work_dir=work_dir, **kwargs)

    def test_invalid_work_dir(self):
        config = self._get_config(work_dir_exists=False)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    def test_too_low_memory(self):
        config = self._get_config(memory_mb=0)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    def test_too_few_memory(self):
        config = self._get_config(cpu_count=0)
        with self.assertRaises(ValueError):
            DockerCPUEnvironment._validate_config(config)

    def test_valid_config(self):
        config = self._get_config()
        DockerCPUEnvironment._validate_config(config)


class TestUpdateWorkDir(TestDockerCPUEnv):

    @patch_env('_error_occurred')
    def test_hypervisor_error(self, error_occurred):
        work_dir = Mock(spec=Path)
        error = OSError("test")
        self.hypervisor.update_work_dir.side_effect = error

        with self.assertRaises(OSError):
            self.env._update_work_dir(work_dir)
        error_occurred.assert_called_once_with(error, ANY)

    def test_ok(self):
        work_dir = Mock(spec=Path)
        self.env._update_work_dir(work_dir)
        self.hypervisor.update_work_dir.assert_called_once_with(work_dir)


class TestConstrainHypervisor(TestDockerCPUEnv):

    def test_config_unchanged(self):
        config = DockerCPUConfig(work_dir=Mock())
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
            work_dir=Mock(),
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
            work_dir=Mock(),
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


class TestRuntime(TestDockerCPUEnv):

    def test_invalid_payload_class(self):
        with self.assertRaises(AssertionError):
            self.env.runtime(object())

    @patch('Whitelist.is_whitelisted', return_value=True)
    def test_invalid_config_class(self, _):
        with self.assertRaises(AssertionError):
            self.env.runtime(Mock(spec=DockerPayload), config=object())

    @patch('Whitelist.is_whitelisted', return_value=False)
    def test_image_not_whitelisted(self, is_whitelisted):
        payload = Mock(spec=DockerPayload)
        with self.assertRaises(RuntimeError):
            self.env.runtime(payload)
        is_whitelisted.assert_called_once_with(payload.image)

    @patch('Whitelist.is_whitelisted', return_value=True)
    @patch('DockerCPURuntime')
    @patch_env('_create_host_config')
    def test_default_config(self, create_host_config, runtime_mock, _):
        payload = Mock(spec=DockerPayload)
        runtime = self.env.runtime(payload)

        create_host_config.assert_called_once_with(self.config, None)
        runtime_mock.assert_called_once_with(
            payload, create_host_config(), None)
        self.assertEqual(runtime, runtime_mock())

    @patch('Whitelist.is_whitelisted', return_value=True)
    @patch('DockerCPURuntime')
    @patch_env('_create_host_config')
    def test_custom_config(self, create_host_config, runtime_mock, _):
        payload = Mock(spec=DockerPayload)
        config = Mock(spec=DockerCPUConfig)
        runtime = self.env.runtime(payload, config=config)

        create_host_config.assert_called_once_with(config, None)
        runtime_mock.assert_called_once_with(
            payload, create_host_config(), None)
        self.assertEqual(runtime, runtime_mock())

    @patch('Whitelist.is_whitelisted', return_value=True)
    @patch('DockerCPURuntime')
    @patch_env('_create_host_config')
    def test_shared_dir(self, create_host_config, runtime_mock, _):
        payload = Mock(spec=DockerPayload)
        shared_dir = Mock(spec=Path)
        runtime = self.env.runtime(payload, shared_dir=shared_dir)

        create_host_config.assert_called_once_with(self.config, shared_dir)
        runtime_mock.assert_called_once_with(
            payload,
            create_host_config(),
            [DockerCPUEnvironment.SHARED_DIR_PATH])
        self.assertEqual(runtime, runtime_mock())


class TestCreateHostConfig(TestDockerCPUEnv):

    @patch('hardware.cpus', return_value=[1, 2, 3, 4, 5, 6])
    @patch('local_client')
    def test_no_shared_dir(self, local_client, _):
        config = DockerCPUConfig(
            work_dir=Mock(spec=Path),
            cpu_count=4,
            memory_mb=2137
        )
        host_config = self.env._create_host_config(config, None)

        self.hypervisor.create_volumes.assert_not_called()
        local_client().create_host_config.assert_called_once_with(
            cpuset_cpus='1,2,3,4',
            mem_limit='2137m',
            binds=None,
            privileged=False,
            network_mode=DockerCPUEnvironment.NETWORK_MODE,
            dns=DockerCPUEnvironment.DNS_SERVERS,
            dns_search=DockerCPUEnvironment.DNS_SEARCH_DOMAINS,
            cap_drop=DockerCPUEnvironment.DROPPED_KERNEL_CAPABILITIES
        )
        self.assertEqual(host_config, local_client().create_host_config())

    @patch('hardware.cpus', return_value=[1, 2, 3, 4, 5, 6])
    @patch('local_client')
    def test_shared_dir(self, local_client, _):
        config = DockerCPUConfig(
            work_dir=Mock(spec=Path),
            cpu_count=4,
            memory_mb=2137
        )
        shared_dir = Mock(spec=Path)
        host_config = self.env._create_host_config(config, shared_dir)

        self.hypervisor.create_volumes.assert_called_once_with([DockerBind(
            source=shared_dir,
            target=DockerCPUEnvironment.SHARED_DIR_PATH,
            mode='rw'
        )])
        local_client().create_host_config.assert_called_once_with(
            cpuset_cpus='1,2,3,4',
            mem_limit='2137m',
            binds=self.hypervisor.create_volumes(),
            privileged=False,
            network_mode=DockerCPUEnvironment.NETWORK_MODE,
            dns=DockerCPUEnvironment.DNS_SERVERS,
            dns_search=DockerCPUEnvironment.DNS_SEARCH_DOMAINS,
            cap_drop=DockerCPUEnvironment.DROPPED_KERNEL_CAPABILITIES
        )
        self.assertEqual(host_config, local_client().create_host_config())
