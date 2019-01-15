import unittest
from unittest.mock import patch, Mock

from golem.core.virtualization import is_virtualization_enabled


def get_mock_cpuinfo_output(vt_supported=True) -> dict:
    flags = ['fpe', 'pae', 'msr']
    if vt_supported:
        flags.append('vmx')

    return {
        'arch': 'X86_64',
        'vendor_id': 'GenuineIntel',
        'flags': flags
    }


def get_mock_sysinfo_output(
        include_vt_fields=True,
        vt_supported=True,
        vt_enabled=True
) -> Mock:
    vt_fields = f"""
    VM Monitor Mode Extensions: {'Yes' if vt_supported else 'No'}
    Virtualization Enabled In Firmware: {'Yes' if vt_enabled else 'No'}
    Second Level Address Translation: Yes
    Data Execution Prevention Available: Yes
    """

    cmd_output = Mock()
    cmd_output.stdout = f"""
    Host Name: golem-test
    OS Name: Microsoft Windows 10 
    Total Physical Memory: 66˙666 MB
    Hyper-V Requirements: {vt_fields if include_vt_fields else ''}
    """.encode(encoding='cp1250')

    return cmd_output


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
@patch('locale.getpreferredencoding', side_effect=lambda: 'cp1250')
class VirtualizationTestWindows(unittest.TestCase):

    @patch('subprocess.run', return_value=get_mock_sysinfo_output())
    def test_vt_enabled(self, *_):
        self.assertTrue(is_virtualization_enabled())

    @patch('subprocess.run',
           return_value=get_mock_sysinfo_output(vt_enabled=False))
    def test_vt_disabled(self, *_):
        self.assertFalse(is_virtualization_enabled())

    @patch('subprocess.run',
           return_value=get_mock_sysinfo_output(vt_supported=False))
    def test_vt_unsupported(self, *_):
        self.assertFalse(is_virtualization_enabled())

    @patch('subprocess.run',
           return_value=get_mock_sysinfo_output(include_vt_fields=False))
    def test_vt_fields_missing(self, *_):
        self.assertFalse(is_virtualization_enabled())
