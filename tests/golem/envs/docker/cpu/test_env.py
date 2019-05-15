import sys
from pathlib import Path
from subprocess import SubprocessError
from unittest.mock import patch as _patch, Mock, MagicMock

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

    @patch_handler('docker_available', return_value=False)
    def test_docker_unavailable(self, *_):
        self.assertFalse(DockerCPUEnvironment.supported().supported)

    @patch_handler('docker_available', return_value=True)
    @patch_env('_check_docker_version', return_value=False)
    def test_wrong_docker_version(self, *_):
        self.assertFalse(DockerCPUEnvironment.supported().supported)

    @patch_handler('docker_available', return_value=True)
    @patch_env('_check_docker_version', return_value=True)
    @patch_env('_get_hypervisor_class', return_value=None)
    def test_no_hypervisor(self, *_):
        self.assertFalse(DockerCPUEnvironment.supported().supported)

    @patch_handler('docker_available', return_value=True)
    @patch_env('_check_docker_version', return_value=True)
    @patch_env('_get_hypervisor_class')
    def test_ok(self, *_):
        self.assertTrue(DockerCPUEnvironment.supported().supported)


class TestCheckDockerVersion(TestCase):

    @patch('logger')
    @patch_handler('run', side_effect=SubprocessError)
    def test_command_error(self, run, logger):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')
        logger.exception.assert_called_once()

    @patch('logger')
    @patch_handler('run', return_value=None)
    def test_no_version(self, run, logger):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')
        logger.error.assert_called_once()

    @patch_handler('run', return_value='(╯°□°)╯︵ ┻━┻')
    def test_invalid_version_string(self, run):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

    @patch_env('SUPPORTED_DOCKER_VERSIONS', ['1.2.1'])
    @patch_handler('run', return_value='Docker version 1.2.3, build abcdef\n')
    def test_unsupported_version(self, run, *_):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

    @patch_env('SUPPORTED_DOCKER_VERSIONS', ['1.2.1', '1.2.3'])
    @patch_handler('run', return_value='Docker version 1.2.3, build abcdef\n')
    def test_supported_version(self, run, *_):
        self.assertTrue(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')


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
        self.env = DockerCPUEnvironment(self.config)

        logger_patch = patch('logger')
        self.logger = logger_patch.start()
        self.addCleanup(logger_patch.stop)


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
        self.hypervisor.setup.side_effect = OSError
        deferred = self.env.prepare()
        self.assertEqual(self.env.status(), EnvStatus.PREPARING)
        deferred = self.assertFailure(deferred, OSError)

        def _check(_):
            self.assertEqual(self.env.status(), EnvStatus.ERROR)
            self.logger.exception.assert_called_once()
        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        deferred = self.env.prepare()
        self.assertEqual(self.env.status(), EnvStatus.PREPARING)

        def _check(_):
            self.assertEqual(self.env.status(), EnvStatus.ENABLED)
        deferred.addCallback(_check)

        return deferred


class TestCleanup(TestDockerCPUEnv):

    def test_disabled_status(self):
        with self.assertRaises(ValueError):
            self.env.cleanup()

    def test_preparing_status(self):
        self.env._status = EnvStatus.PREPARING
        with self.assertRaises(ValueError):
            self.env.cleanup()

    def test_cleaning_up_status(self):
        self.env._status = EnvStatus.CLEANING_UP
        with self.assertRaises(ValueError):
            self.env.cleanup()

    def test_hypervisor_quit_error(self):
        self.env._status = EnvStatus.ENABLED
        self.hypervisor.quit.side_effect = OSError
        deferred = self.env.cleanup()
        self.assertEqual(self.env.status(), EnvStatus.CLEANING_UP)
        deferred = self.assertFailure(deferred, OSError)

        def _check(_):
            self.assertEqual(self.env.status(), EnvStatus.ERROR)
            self.logger.exception.assert_called_once()
        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        self.env._status = EnvStatus.ENABLED
        deferred = self.env.cleanup()
        self.assertEqual(self.env.status(), EnvStatus.CLEANING_UP)

        def _check(_):
            self.assertEqual(self.env.status(), EnvStatus.DISABLED)
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

    def _patch_whitelist(self, return_value):
        # Has to use twisted's patch because standard one doesn't work with
        # Deferreds very well
        whitelist = Mock(is_whitelisted=Mock(return_value=return_value))
        self.patch(sys.modules['golem.envs.docker.cpu'], 'Whitelist', whitelist)

    def test_pull_image_error(self):
        client_mock = MagicMock()
        client_mock.return_value.pull.side_effect = ValueError
        client_patch = patch("local_client", client_mock)
        client_patch.start()
        self.addCleanup(client_patch.stop)

        self.env._status = EnvStatus.ENABLED
        self._patch_whitelist(True)
        prereqs = Mock(spec=DockerPrerequisites)
        deferred = self.env.install_prerequisites(prereqs)
        return self.assertFailure(deferred, ValueError)

    def test_not_whitelisted(self):
        self.env._status = EnvStatus.ENABLED
        self._patch_whitelist(False)
        prereqs = Mock(spec=DockerPrerequisites)
        deferred = self.env.install_prerequisites(prereqs)

        def _check(return_value):
            self.assertFalse(return_value)
        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        self.env._status = EnvStatus.ENABLED
        self._patch_whitelist(True)
        client_patch = patch("local_client")
        client_mock = client_patch.start()
        self.addCleanup(client_patch.stop)

        prereqs = Mock(spec=DockerPrerequisites)
        deferred = self.env.install_prerequisites(prereqs)

        def _check(return_value):
            self.assertTrue(return_value)
            client_mock().pull.assert_called_once_with(
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

    @patch_env('_validate_config')
    @patch_env('_constrain_hypervisor')
    def test_work_dir_unchanged(self, constrain, validate):
        config = DockerCPUConfig(work_dir=self.config.work_dir)
        self.env.update_config(config)

        validate.assert_called_once_with(config)
        constrain.assert_called_once_with(config)
        self.hypervisor.update_work_dir.assert_not_called()

    @patch_env('_validate_config')
    @patch_env('_constrain_hypervisor')
    def test_config_changed(self, constrain, validate):
        config = DockerCPUConfig(
            work_dir=Mock(),
            memory_mb=2137,
            cpu_count=12
        )
        self.env.update_config(config)

        validate.assert_called_once_with(config)
        constrain.assert_called_once_with(config)
        self.hypervisor.update_work_dir.assert_called_once_with(config.work_dir)
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

    def test_constrain_error(self):
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
        self.hypervisor.constrain.side_effect = OSError

        with self.assertRaises(OSError):
            self.env._constrain_hypervisor(config)
        self.assertEqual(self.env.status(), EnvStatus.ERROR)
        self.logger.exception.assert_called_once()

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
