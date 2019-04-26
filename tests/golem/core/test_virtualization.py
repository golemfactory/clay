from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from golem.core.virtualization import is_virtualization_satisfied,\
    SCRIPTS_PATH


def get_mock_cpuinfo_output(vt_supported=True) -> dict:
    flags = ['fpe', 'pae', 'msr']
    if vt_supported:
        flags.append('vmx')

    return {
        'arch': 'X86_64',
        'vendor_id': 'GenuineIntel',
        'flags': flags
    }


@patch('golem.core.virtualization.is_linux', side_effect=lambda: True)
class VirtualizationTestLinux(TestCase):

    def test_vt_enabled(self, *_):
        self.assertTrue(is_virtualization_satisfied())


@patch('golem.core.virtualization.is_linux', side_effect=lambda: False)
@patch('golem.core.virtualization.is_windows', side_effect=lambda: False)
class VirtualizationTestOsx(TestCase):

    @patch('golem.core.virtualization.get_cpu_info',
           return_value=get_mock_cpuinfo_output())
    def test_vt_enabled(self, *_):
        self.assertTrue(is_virtualization_satisfied())

    @patch('golem.core.virtualization.get_cpu_info',
           return_value=get_mock_cpuinfo_output(vt_supported=False))
    def test_vt_unsupported(self, *_):
        self.assertFalse(is_virtualization_satisfied())


@patch('golem.core.virtualization.is_linux', side_effect=lambda: False)
@patch('golem.core.virtualization.is_windows', side_effect=lambda: True)
class VirtualizationTestWindows(TestCase):

    @patch('golem.core.virtualization.run_powershell',
           return_value='True')
    def test_vt_enabled(self, *_):
        self.assertTrue(is_virtualization_satisfied())

    @patch('golem.core.virtualization.run_powershell',
           return_value='False')
    def test_vt_disabled(self, *_):
        self.assertFalse(is_virtualization_satisfied())

    def test_script_path(self, *_):
        self.assertTrue(Path(SCRIPTS_PATH).exists())
