import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from os_win.exceptions import OSWinException

from golem.docker.config import DOCKER_VM_NAME
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.job import DockerJob


class TestHyperVHypervisor(TestCase):

    def setUp(self):
        self.get_config = Mock()
        self.hyperv = HyperVHypervisor(get_config_fn=self.get_config)

    def _assert_param(self, args, name, value):
        """ Check if given pair (name, value) is a subsequence of args list """
        for x, y in zip(args, args[1:]):
            if (x, y) == (name, value):
                return
        self.fail(f'Parameter {name} = {value} not found in {args}')

    def test_parse_create_params_default(self):
        args = self.hyperv._parse_create_params()
        self._assert_param(args, '--driver', 'hyperv')
        self._assert_param(
            args, '--hyperv-boot2docker-url', HyperVHypervisor.BOOT2DOCKER_URL)
        self._assert_param(
            args, '--hyperv-virtual-switch', HyperVHypervisor.VIRTUAL_SWITCH)

    def test_parse_create_params_constraints(self):
        args = self.hyperv._parse_create_params(cpu=4, mem=4096)
        self._assert_param(args, '--hyperv-cpu-count', '4')
        self._assert_param(args, '--hyperv-memory', '4096')

    @patch('golem.docker.hypervisor.hyperv.logger')
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

    @patch('golem.docker.hypervisor.hyperv.logger')
    def test_constraints_error(self, logger):
        with patch.object(self.hyperv._vm_utils, 'get_vm_summary_info') \
                as get_info:
            get_info.side_effect = OSWinException
            constraints = self.hyperv.constraints()
            self.assertEqual(constraints, {})
            logger.exception.assert_called_once()

    @patch('golem.docker.hypervisor.hyperv.VMUtilsWithMem.get_vm_memory')
    @patch('golem.docker.hypervisor.hyperv.VMUtilsWithMem.get_vm_summary_info')
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

    @patch('golem.docker.hypervisor.hyperv.smbshare')
    def test_update_work_dir(self, smbshare):
        path = Mock()
        self.hyperv.update_work_dir(path)
        smbshare.create_share.assert_called_once_with(
            HyperVHypervisor.DOCKER_USER, path)

    def test_create_volumes(self):
        tmp_dir = Path(tempfile.gettempdir())
        dir_mapping = Mock(
            work=(tmp_dir / 'work'),
            resources=(tmp_dir / 'res'),
            output=(tmp_dir / 'out')
        )

        def _create_volume(my_ip, shared_dir):
            return f'{my_ip}/{shared_dir.name}'

        with patch.object(self.hyperv, '_get_ip_for_sharing') as get_ip, \
                patch.object(self.hyperv, '_create_volume', _create_volume):
            get_ip.return_value = '127.0.0.1'
            volumes = self.hyperv.create_volumes(dir_mapping)
            self.assertDictEqual(volumes, {
                '127.0.0.1/work': {
                    'bind': DockerJob.WORK_DIR,
                    'mode': 'rw'
                },
                '127.0.0.1/res': {
                    'bind': DockerJob.RESOURCES_DIR,
                    'mode': 'rw'
                },
                '127.0.0.1/out': {
                    'bind': DockerJob.OUTPUT_DIR,
                    'mode': 'rw'
                }
            })

    def test_create_volume_wrong_dir(self):
        tmp_dir = Path(tempfile.gettempdir())
        self.hyperv._work_dir = tmp_dir / 'work_dir'

        with self.assertRaises(ValueError):
            self.hyperv._create_volume('127.0.0.1', tmp_dir / 'shared_dir')

    @patch('golem.docker.hypervisor.hyperv.local_client')
    @patch('golem.docker.hypervisor.hyperv.smbshare')
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
