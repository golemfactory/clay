import os

import psutil

from golem.diag.service import DiagnosticsProvider


class VMDiagnosticsProvider(DiagnosticsProvider, object):
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.attrs = [
            'connections', 'cpu_affinity', 'cpu_percent', 'cpu_times', 'create_time',
            'memory_full_info', 'memory_info', 'memory_info_ex', 'memory_percent',
            'nice', 'num_ctx_switches', 'num_fds', 'num_threads', 'status', 'uids',
            'username', 'cwd', 'io_counters', 'nice'
        ]

    def get_diagnostics(self, output_format):
        data = self.process.as_dict(attrs=self.attrs)
        return self._format_diagnostics(data, output_format)
