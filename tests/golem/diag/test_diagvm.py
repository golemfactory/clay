import json
from unittest import TestCase
import psutil

from golem.diag.service import DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider


class TestVMDiagnosticProvider(TestCase):

    def test_format_outputs(self):
        provider = VMDiagnosticsProvider()
        diag = provider.get_diagnostics(DiagnosticsOutputFormat.string)
        json.dumps(diag)
        diag = provider.get_diagnostics(DiagnosticsOutputFormat.json)
        json.dumps(diag)
        diag = provider.get_diagnostics(DiagnosticsOutputFormat.data)
        json.dumps(diag)

        with(self.assertRaises(ValueError)):
            provider.get_diagnostics("UNKNOWN FORMAT")

    def test_diagnostics_contain_hardware_info(self):
        provider = VMDiagnosticsProvider()
        diag = provider.get_diagnostics(DiagnosticsOutputFormat.data)
        self.assertIn('hardware_memory_size', diag)
        self.assertIn('hardware_num_cores', diag)
        self.assertAlmostEqual(
            diag['hardware_memory_size'],
            psutil.virtual_memory().total // 1024,
            delta=1
        )
        self.assertEqual(diag['hardware_num_cores'], psutil.cpu_count())
