import unittest
from unittest.mock import patch, Mock

from golem.core.virtualization import is_virtualization_enabled


@patch('golem.core.virtualization.is_windows', side_effect=lambda: False)
class VirtualizationTestUnix(unittest.TestCase):

    @patch('golem.core.virtualization.get_cpu_info')
    def test_vt_enabled(self, cpu_info_mock, *_):
        cpu_info_mock.return_value = get_cpuinfo_output_mock()

        self.assertTrue(is_virtualization_enabled())

    @patch('golem.core.virtualization.get_cpu_info')
    def test_vt_unsupported(self, cpu_info_mock, *_):
        cpu_info_mock.return_value = get_cpuinfo_output_mock(vt_supported=False)

        self.assertFalse(is_virtualization_enabled())


@patch('golem.core.virtualization.is_windows', side_effect=lambda: True)
@patch('locale.getpreferredencoding', side_effect=lambda: 'cp1250')
class VirtualizationTestWindows(unittest.TestCase):

    @patch('subprocess.run')
    def test_vt_enabled(self, run_mock, *_):
        run_mock.return_value = get_sysinfo_output_mock()

        self.assertTrue(is_virtualization_enabled())

    @patch('subprocess.run')
    def test_vt_disabled(self, run_mock, *_):
        run_mock.return_value = get_sysinfo_output_mock(vt_enabled=False)

        self.assertFalse(is_virtualization_enabled())

    @patch('subprocess.run')
    def test_vt_unsupported(self, run_mock, *_):
        run_mock.return_value = get_sysinfo_output_mock(vt_supported=False)

        self.assertFalse(is_virtualization_enabled())

    @patch('subprocess.run')
    def test_vt_fields_missing(self, run_mock, *_):
        run_mock.return_value = get_sysinfo_output_mock(include_vt_fields=False)

        self.assertFalse(is_virtualization_enabled())


def get_cpuinfo_output_mock(vt_supported=True) -> dict:
    cmd_output = {
        'arch': 'X86_64',
        'vendor_id': 'GenuineIntel',
        'flags': [
            'fpe', 'pae', 'msr'
        ]
    }

    if vt_supported:
        cmd_output['flags'].append('vmx')

    return cmd_output


def get_sysinfo_output_mock(
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
