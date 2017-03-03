import os

import psutil
from golem.core.common import is_windows, is_osx

from golem.diag.service import DiagnosticsProvider


class VMDiagnosticsProvider(DiagnosticsProvider):
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.attrs = [
            'connections', 'cpu_percent', 'cpu_times', 'create_time',
            'memory_info', 'memory_percent',
            'nice', 'num_ctx_switches', 'num_threads', 'status',
            'username', 'cwd'
        ]

        if is_windows():
            self.attrs += ['num_handles']
        else:
            self.attrs += ['uids', 'num_fds']

        if not is_osx():
            self.attrs += ['cpu_affinity', 'io_counters']

    def get_diagnostics(self, output_format):
        data = self.process.as_dict(attrs=self.attrs)
        return self._format_diagnostics(data, output_format)
