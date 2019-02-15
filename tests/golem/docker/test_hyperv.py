import tempfile
import subprocess

from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch, ANY, call

from os_win.constants import HOST_SHUTDOWN_ACTION_SAVE, \
    HOST_SHUTDOWN_ACTION_SHUTDOWN, HYPERV_VM_STATE_SUSPENDED, \
    HYPERV_VM_STATE_ENABLED, HYPERV_VM_STATE_DISABLED
from os_win.exceptions import OSWinException

from golem.docker.config import DOCKER_VM_NAME, MIN_CONSTRAINTS, CONSTRAINT_KEYS
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

    @patch(PATCH_BASE + '.HyperVHypervisor._check_system_drive_space')
    @patch(PATCH_BASE + '.HyperVHypervisor._get_vswitch_name',
           return_value='Default Switch')
    def test_parse_create_params_default(self, *_):
        args = self.hyperv._parse_create_params()
        self._assert_param(args, '--driver', 'hyperv')
        self._assert_param(
            args, '--hyperv-boot2docker-url', HyperVHypervisor.BOOT2DOCKER_URL)
        self._assert_param(
            args, '--hyperv-virtual-switch', 'Default Switch')

    @patch(PATCH_BASE + '.HyperVHypervisor._check_system_drive_space')
    @patch(PATCH_BASE + '.HyperVHypervisor._get_vswitch_name')
    @patch(PATCH_BASE + '.HyperVHypervisor._memory_cap', lambda _, x: x)
    def test_parse_create_params_constraints(self, *_):
        args = self.hyperv._parse_create_params(cpu=4, mem=4096)
        self._assert_param(args, '--hyperv-cpu-count', '4')
        # self._assert_param(args, '--hyperv-memory', '4096')
        # TODO: Restore when we have a better estimation of available RAM
        self._assert_param(args, '--hyperv-memory',
                           str(MIN_CONSTRAINTS[CONSTRAINT_KEYS['mem']]))

    @patch(PATCH_BASE + '.HyperVHypervisor._check_system_drive_space')
    @patch(PATCH_BASE + '.HyperVHypervisor._get_vswitch_name')
    @patch(PATCH_BASE + '.HyperVHypervisor._memory_cap', return_value=2048)
    @patch(PATCH_BASE + '.logger')
    def test_parse_create_params_constraints_memory_cap(self, logger, *_):
        args = self.hyperv._parse_create_params(cpu=4, mem=4096)
        self._assert_param(args, '--hyperv-cpu-count', '4')
        # self._assert_param(args, '--hyperv-memory', '2048')
        # logger.warning.assert_called_once()
        # TODO: Restore when we have a better estimation of available RAM
        self._assert_param(args, '--hyperv-memory',
                           str(MIN_CONSTRAINTS[CONSTRAINT_KEYS['mem']]))

    @patch(PATCH_BASE + '.HyperVHypervisor._get_vswitch_name')
    @patch(PATCH_BASE + '.HyperVHypervisor._memory_cap', lambda _, x: x)
    @patch(PATCH_BASE + '.psutil')
    @patch(PATCH_BASE + '.logger')
    def test_parse_create_params_not_enough_disk_space(self, logger, psutil, _):
        psutil.disk_usage().free = 2048 * 1024 * 1024
        args = self.hyperv._parse_create_params(cpu=4, mem=4096)
        self._assert_param(args, '--hyperv-cpu-count', '4')
        self._assert_param(args, '--hyperv-memory',
                           str(MIN_CONSTRAINTS[CONSTRAINT_KEYS['mem']]))
        # logger.warning.assert_called_once()
        # TODO: Restore when we have a better estimation of available RAM

    @patch(PATCH_BASE + '.HyperVHypervisor._check_system_drive_space')
    @patch(PATCH_BASE + '.subprocess.run',
           side_effect=subprocess.CalledProcessError(1, 'foo'))
    def test_parse_create_params_error(self, *_):
        with self.assertRaises(RuntimeError):
            self.hyperv._parse_create_params()

    @patch(PATCH_BASE + '.HyperVHypervisor._check_system_drive_space')
    @patch(PATCH_BASE + '.logger')
    def test_constrain_error(self, logger, _):
        with patch.object(self.hyperv._vm_utils, 'update_vm') as update_vm:
            update_vm.side_effect = OSWinException
            self.hyperv.constrain(cpu_count=2, memory_size=4096)
            logger.exception.assert_called_once()

    @patch(PATCH_BASE + '.HyperVHypervisor._check_system_drive_space')
    def test_constrain_ok(self, _):
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

    @patch(PATCH_BASE + '.psutil')
    def test_constrain_host_shutdown_action_save(self, psutil):
        psutil.disk_usage().free = 2048 * 1024 * 1024
        with patch.object(self.hyperv._vm_utils, 'update_vm') as update_vm:
            self.hyperv.constrain(cpu_count=1, memory_size=1024)

            update_vm.assert_called_once()
            self.assertEqual(
                update_vm.call_args[1].get('host_shutdown_action'),
                HOST_SHUTDOWN_ACTION_SAVE
            )

    @patch(PATCH_BASE + '.psutil')
    @patch(PATCH_BASE + '.logger')
    def test_constrain_host_shutdown_action_shutdown(self, logger, psutil):
        psutil.disk_usage().free = 1024 * 1024 * 1024
        with patch.object(self.hyperv._vm_utils, 'update_vm') as update_vm:
            self.hyperv.constrain(cpu_count=1, memory_size=2048)

            update_vm.assert_called_once()
            self.assertEqual(
                update_vm.call_args[1].get('host_shutdown_action'),
                HOST_SHUTDOWN_ACTION_SHUTDOWN
            )
            logger.warning.assert_called_once()

    @patch(PATCH_BASE + '.logger')
    def test_constraints_error(self, logger):
        with patch.object(self.hyperv._vm_utils, 'get_vm_summary_info') \
                as get_info:
            get_info.side_effect = OSWinException
            constraints = self.hyperv.constraints()
            self.assertEqual(constraints, {})
            logger.exception.assert_called_once()

    @patch(PATCH_BASE + '.VMUtils.get_vm_memory_info')
    @patch(PATCH_BASE + '.VMUtils.get_vm_summary_info')
    def test_constraints_ok(self, get_info, get_memory):
        # GIVEN
        get_info.return_value = {
            'NumberOfProcessors': 1,
        }
        mem_settings = dict()
        mem_settings['Reservation'] = 2048
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

        with patch.object(self.hyperv, '_get_hostname_for_sharing') as get_ip, \
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

    # Not using patch.dict() because mypy can't understand it
    # See https://github.com/python/mypy/issues/5118 for reference
    @patch(PATCH_BASE + '.os.environ', {'COMPUTERNAME': 'foo'})
    def test_get_hostname_for_sharing_ok(self):
        hostname = self.hyperv._get_hostname_for_sharing()
        self.assertEqual(hostname, 'foo')

    @patch(PATCH_BASE + '.os.environ', {})
    def test_get_hostname_for_sharing_error(self):
        with self.assertRaises(RuntimeError):
            self.hyperv._get_hostname_for_sharing()

    @patch(PATCH_BASE + '.os.environ', {'COMPUTERNAME': 'foo'})
    @patch(PATCH_BASE + '.logger')
    @patch('golem.docker.commands.docker.DockerCommandHandler._command')
    def test_check_smb_port_ok(self, command, logger):
        command.return_value = 'Port check OK'
        with patch.object(self.hyperv, 'SMB_PORT', "123"):
            self.hyperv._check_smb_port()

        command.assert_called_once_with(
            ['docker-machine', '--native-ssh', 'ssh'],
            None,
            [self.hyperv._vm_name, ANY],
            False
        )
        self.assertIn("foo 123", command.call_args[0][2][1])
        logger.error.assert_not_called()

    @patch(PATCH_BASE + '.os.environ', {'COMPUTERNAME': 'foo'})
    @patch(PATCH_BASE + '.logger')
    @patch('golem.docker.commands.docker.DockerCommandHandler._command')
    def test_check_smb_port_debug(self, command, logger):
        command.return_value = \
            'DEBUG: blah blah blah\n'\
            'DEBUG: running SSH command\n'\
            'Port check OK\n'\
            'DEBUG: blah blah blah\n'
        self.hyperv._check_smb_port()

        command.assert_called_once()
        logger.error.assert_not_called()

    @patch(PATCH_BASE + '.os.environ', {'COMPUTERNAME': 'foo'})
    @patch(PATCH_BASE + '.logger')
    @patch('golem.docker.commands.docker.DockerCommandHandler._command')
    def test_check_smb_port_error(self, command, logger):
        command.return_value = 'Error'
        self.hyperv._check_smb_port()
        command.assert_called_once()
        logger.error.assert_called_once()

    def test_restore_vm_ok(self):
        with patch.object(self.hyperv, '_check_memory') as check_memory, \
                patch.object(self.hyperv, '_vm_utils') as vm_utils:
            vm_utils.get_vm_state.return_value = HYPERV_VM_STATE_SUSPENDED
            check_memory.return_value = True

            self.hyperv.restore_vm('test')

            check_memory.assert_called_once()
            vm_utils.set_vm_state.assert_called_once_with(
                'test',
                HYPERV_VM_STATE_ENABLED
            )

    def test_restore_vm_not_suspended(self):
        with patch.object(self.hyperv, '_vm_utils') as vm_utils, \
                patch.object(self.hyperv, 'start_vm') as start_vm:
            vm_utils.get_vm_state.return_value = HYPERV_VM_STATE_DISABLED

            self.hyperv.restore_vm('test')

            vm_utils.set_vm_state.assert_not_called()
            start_vm.assert_called_once_with('test')

    def test_restore_vm_no_memory(self):
        with patch.object(self.hyperv, '_check_memory') as check_memory, \
                patch.object(self.hyperv, '_vm_utils') as vm_utils, \
                patch.object(self.hyperv, 'start_vm') as start_vm:
            vm_utils.get_vm_state.return_value = HYPERV_VM_STATE_SUSPENDED
            check_memory.return_value = False

            self.hyperv.restore_vm('test')

            check_memory.assert_called_once()
            vm_utils.set_vm_state.assert_called_once_with(
                'test',
                HYPERV_VM_STATE_DISABLED
            )
            start_vm.assert_called_once_with('test')

    def test_restore_vm_error(self):
        def _fail_to_start(_vm_name, state):
            if state == HYPERV_VM_STATE_ENABLED:
                raise OSWinException

        with patch.object(self.hyperv, '_check_memory') as check_memory, \
                patch.object(self.hyperv, '_vm_utils') as vm_utils, \
                patch.object(self.hyperv, 'start_vm') as start_vm, \
                patch(self.PATCH_BASE + '.logger') as logger:
            vm_utils.get_vm_state.return_value = HYPERV_VM_STATE_SUSPENDED
            vm_utils.set_vm_state.side_effect = _fail_to_start
            check_memory.return_value = True

            self.hyperv.restore_vm('test')

            check_memory.assert_called_once()
            self.assertEqual(vm_utils.set_vm_state.call_count, 2)
            vm_utils.set_vm_state.assert_has_calls((
                call('test', HYPERV_VM_STATE_ENABLED),
                call('test', HYPERV_VM_STATE_DISABLED)
            ))
            start_vm.assert_called_once_with('test')
            logger.exception.assert_called_once()
