from pathlib import Path
import unittest
from unittest.mock import patch

from golem.core.virtualization import is_virtualization_enabled, WIN_SCRIPT_PATH


def get_mock_cpuinfo_output(vt_supported=True) -> dict:
    flags = ['fpe', 'pae', 'msr']
    if vt_supported:
        flags.append('vmx')

    return {
        'arch': 'X86_64',
        'vendor_id': 'GenuineIntel',
        'flags': flags
    }


@patch('golem.core.virtualization.is_windows', side_effect=lambda: False)
class VirtualizationTestUnix(unittest.TestCase):

    @patch('golem.core.virtualization.get_cpu_info',
           return_value=get_mock_cpuinfo_output())
    def test_vt_enabled(self, *_):
        self.assertTrue(is_virtualization_enabled())

    @patch('golem.core.virtualization.get_cpu_info',
           return_value=get_mock_cpuinfo_output(vt_supported=False))
    def test_vt_unsupported(self, *_):
        self.assertFalse(is_virtualization_enabled())


@patch('golem.core.virtualization.is_windows', side_effect=lambda: True)
class VirtualizationTestWindows(unittest.TestCase):

    @patch('golem.core.virtualization.run_powershell',
           return_value='True')
    def test_vt_enabled(self, *_):
        self.assertTrue(is_virtualization_enabled())

    @patch('golem.core.virtualization.run_powershell',
           return_value='False')
    def test_vt_disabled(self, *_):
        self.assertFalse(is_virtualization_enabled())

    def test_script_path(self, *_):
        self.assertTrue(Path(WIN_SCRIPT_PATH).exists())
