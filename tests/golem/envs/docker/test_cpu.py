from subprocess import SubprocessError
from unittest import TestCase
from unittest.mock import patch as _patch

from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.envs.docker.cpu import DockerCPUEnvironment


def patch(name: str, *args, **kwargs):
    return _patch(f'golem.envs.docker.cpu.{name}', *args, **kwargs)


class TestSupported(TestCase):

    @patch('DockerCommandHandler.docker_available', return_value=False)
    def test_docker_unavailable(self, *_):
        self.assertFalse(DockerCPUEnvironment.supported().supported)

    @patch('DockerCommandHandler.docker_available', return_value=True)
    @patch('DockerCPUEnvironment._check_docker_version', return_value=False)
    def test_wrong_docker_version(self, *_):
        self.assertFalse(DockerCPUEnvironment.supported().supported)

    @patch('DockerCommandHandler.docker_available', return_value=True)
    @patch('DockerCPUEnvironment._check_docker_version', return_value=True)
    @patch('DockerCPUEnvironment._get_hypervisor_class', return_value=None)
    def test_no_hypervisor(self, *_):
        self.assertFalse(DockerCPUEnvironment.supported().supported)

    @patch('DockerCommandHandler.docker_available', return_value=True)
    @patch('DockerCPUEnvironment._check_docker_version', return_value=True)
    @patch('DockerCPUEnvironment._get_hypervisor_class')
    def test_ok(self, *_):
        self.assertTrue(DockerCPUEnvironment.supported().supported)


class TestCheckDockerVersion(TestCase):

    @patch('DockerCommandHandler.run', side_effect=SubprocessError)
    def test_command_error(self, run):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

    @patch('DockerCommandHandler.run', return_value=None)
    def test_no_version(self, run):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

    @patch('DockerCommandHandler.run', return_value='(╯°□°)╯︵ ┻━┻')
    def test_invalid_version_string(self, run):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

    @patch('DockerCPUEnvironment.SUPPORTED_DOCKER_VERSIONS', ['1.2.1'])
    @patch('DockerCommandHandler.run',
           return_value='Docker version 1.2.3, build abcdef\n')
    def test_unsupported_version(self, run, *_):
        self.assertFalse(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')

    @patch('DockerCPUEnvironment.SUPPORTED_DOCKER_VERSIONS', ['1.2.1', '1.2.3'])
    @patch('DockerCommandHandler.run',
           return_value='Docker version 1.2.3, build abcdef\n')
    def test_supported_version(self, run, *_):
        self.assertTrue(DockerCPUEnvironment._check_docker_version())
        run.assert_called_with('version')


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
