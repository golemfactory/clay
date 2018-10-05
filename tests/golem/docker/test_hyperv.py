import tempfile
import subprocess

from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from os_win.exceptions import OSWinException

from golem.docker.config import DOCKER_VM_NAME
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.task_thread import DockerBind


class TestHyperVHypervisor(TestCase):

    PATCH_BASE = 'golem.docker.hypervisor.hyperv'

    def setUp(self):
        self.get_config = Mock()
        self.hyperv = HyperVHypervisor(get_config_fn=self.get_config)

    def _assert_param(self, args, name, value):
        """ Check if given pair (name, value) is a subsequence of args list """
        for x, y in zip(args, args[1:]):
            if (x, y) == (name, value):
                return
        self.fail(f'Parameter {name} = {value} not found in {args}')

    @patch(PATCH_BASE + '.HyperVHypervisor._create_vnet_switch')
    def test_parse_create_params_default(self, _):
        args = self.hyperv._parse_create_params()
        self._assert_param(args, '--driver', 'hyperv')
        self._assert_param(
            args, '--hyperv-boot2docker-url', HyperVHypervisor.BOOT2DOCKER_URL)
        self._assert_param(
            args, '--hyperv-virtual-switch', HyperVHypervisor.VIRTUAL_SWITCH)

    @patch(PATCH_BASE + '.HyperVHypervisor._create_vnet_switch')
    def test_parse_create_params_constraints(self, _):
        args = self.hyperv._parse_create_params(cpu=4, mem=4096)
        self._assert_param(args, '--hyperv-cpu-count', '4')
        self._assert_param(args, '--hyperv-memory', '4096')

    @patch(PATCH_BASE + '.subprocess.run')
    def test_parse_create_vnet_switch(self, mock_run):
        self.hyperv._create_vnet_switch()
        mock_run.assert_called_with(
            [
                'powershell.exe',
                '-ExecutionPolicy', 'RemoteSigned',
                '-File', self.hyperv.SETUP_SWITCH_PATH,
                '-Interface', self.hyperv.VIRTUAL_SWITCH,
            ],
            timeout=20,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @patch(PATCH_BASE + '.subprocess.run',
           side_effect=subprocess.CalledProcessError(1, 'a', stderr=b''))
    def test_parse_create_vnet_switch_fail(self, _):
        with self.assertRaises(RuntimeError):
            self.hyperv._create_vnet_switch()

    @patch(PATCH_BASE + '.logger')
    def test_constrain_error(self, logger):
        with patch.object(self.hyperv._vm_utils, 'update_vm') as update_vm:
            update_vm.side_effect = OSWinException
            self.hyperv.constrain(cpu_count=2, memory_size=4096)
            logger.exception.assert_called_once()

    def test_constrain_ok(self):
        with patch.object(self.hyperv._vm_utils, 'update_vm') as update_vm:
            self.hyperv.constrain(cpu_count=2, memory_size=4096)

            update_vm.assert_called_once()
            self.assertDictContainsSubset(
                {
                    'vm_name': DOCKER_VM_NAME,
                    'vcpus_num': 2,
                    'memory_mb': 4096
                },
                update_vm.call_args[1]
            )

    @patch(PATCH_BASE + '.logger')
    def test_constraints_error(self, logger):
        with patch.object(self.hyperv._vm_utils, 'get_vm_summary_info') \
                as get_info:
            get_info.side_effect = OSWinException
            constraints = self.hyperv.constraints()
            self.assertEqual(constraints, {})
            logger.exception.assert_called_once()

    @patch(PATCH_BASE + '.VMUtilsWithMem.get_vm_memory')
    @patch(PATCH_BASE + '.VMUtilsWithMem.get_vm_summary_info')
    def test_constraints_ok(self, get_info, get_memory):
        # GIVEN
        get_info.return_value = {
            'NumberOfProcessors': 1,
        }
        mem_settings = Mock()
        mem_settings.Limit = 2048
        get_memory.return_value = mem_settings

        #  WHEN
        constraints = self.hyperv.constraints()

        #THEN
        get_info.assert_called_once_with(DOCKER_VM_NAME)
        get_memory.assert_called_once_with(DOCKER_VM_NAME)
        self.assertDictEqual(constraints, {
            'cpu_count': 1,
            'memory_size': 2048
        })

    @patch(PATCH_BASE + '.smbshare')
    def test_update_work_dir(self, smbshare):
        path = Mock()
        self.hyperv.update_work_dir(path)
        smbshare.create_share.assert_called_once_with(
            HyperVHypervisor.DOCKER_USER, path)

    def test_create_volumes(self):
        tmp_dir = Path(tempfile.gettempdir())
        binds = (
            DockerBind(tmp_dir / 'share1', '/test/work', 'rw'),
            DockerBind(tmp_dir / 'share2', '/test/res', 'ro'),
        )

        def _create_volume(my_ip, shared_dir):
            return f'{my_ip}/{shared_dir.name}'

        with patch.object(self.hyperv, '_get_ip_for_sharing') as get_ip, \
                patch.object(self.hyperv, '_create_volume', _create_volume):
            get_ip.return_value = '127.0.0.1'
            volumes = self.hyperv.create_volumes(binds)
            self.assertDictEqual(volumes, {
                '127.0.0.1/share1': {
                    'bind': '/test/work',
                    'mode': 'rw'
                },
                '127.0.0.1/share2': {
                    'bind': '/test/res',
                    'mode': 'ro'
                },
            })

    def test_create_volume_wrong_dir(self):
        tmp_dir = Path(tempfile.gettempdir())
        self.hyperv._work_dir = tmp_dir / 'work_dir'

        with self.assertRaises(ValueError):
            self.hyperv._create_volume('127.0.0.1', tmp_dir / 'shared_dir')

    @patch(PATCH_BASE + '.local_client')
    @patch(PATCH_BASE + '.smbshare')
    def test_create_volume_ok(self, smbshare, local_client):
        tmp_dir = Path(tempfile.gettempdir())
        work_dir = self.hyperv._work_dir = tmp_dir / 'work_dir'
        shared_dir = work_dir / 'task1' / 'res'
        smbshare.get_share_name.return_value = 'SHARE_NAME'

        volume_name = self.hyperv._create_volume('127.0.0.1', shared_dir)

        self.assertEqual(volume_name, '127.0.0.1/SHARE_NAME/task1/res')
        local_client().create_volume.assert_called_once_with(
            name='127.0.0.1/SHARE_NAME/task1/res',
            driver=HyperVHypervisor.VOLUME_DRIVER,
            driver_opts={
                'username': HyperVHypervisor.DOCKER_USER,
                'password': HyperVHypervisor.DOCKER_PASSWORD
            }
        )
