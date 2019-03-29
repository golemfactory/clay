import tempfile
from subprocess import SubprocessError
from unittest.mock import patch as _patch, Mock

from twisted.trial.unittest import TestCase

from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.envs import EnvStatus
from golem.envs.docker.cpu import DockerCPUEnvironment, DockerCPUConfig


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

    @patch_handler('run', side_effect=SubprocessError)
    def test_command_error(self, run):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

    @patch_handler('run', return_value=None)
    def test_no_version(self, run):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

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
            work_dir=tempfile.gettempdir(),
            memory_mb=2137,
            cpu_count=12
        )

        def _instance(get_config_fn):
            self.assertDictEqual(get_config_fn(), {
                CONSTRAINT_KEYS['mem']: config.memory_mb,
                CONSTRAINT_KEYS['cpu']: config.cpu_count
            })
        get_hypervisor.return_value.instance = _instance

        DockerCPUEnvironment(config)


class TestDockerCPUEnv(TestCase):

    def setUp(self):
        self.hypervisor = Mock(spec=Hypervisor)
        with patch_env('_get_hypervisor_class') as get_hypervisor, \
                patch_env('_validate_config'):
            get_hypervisor.return_value.instance.return_value = self.hypervisor
            self.env = DockerCPUEnvironment(Mock(spec=DockerCPUConfig))


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
            self.assertEqual(self.env.status(), EnvStatus.DISABLED)
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
            self.assertEqual(self.env.status(), EnvStatus.ENABLED)
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
