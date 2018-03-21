import os

import psutil
from golem.core.common import is_windows, is_osx

from golem.diag.service import DiagnosticsProvider


# pylint: disable=too-few-public-methods
class VMDiagnosticsProvider(DiagnosticsProvider):
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.process_attrs = [
            'connections', 'cpu_percent', 'cpu_times', 'create_time',
            'memory_info', 'memory_percent',
            'nice', 'num_ctx_switches', 'num_threads', 'status',
            'username', 'cwd'
        ]

        if is_windows():
            self.process_attrs += ['num_handles']
        else:
            self.process_attrs += ['uids', 'num_fds']

        if not is_osx():
            self.process_attrs += ['cpu_affinity', 'io_counters']

    def get_diagnostics(self, output_format):
        data = self.process.as_dict(attrs=self.process_attrs)
        data['hardware_num_cores'] = psutil.cpu_count()
        # In KiB, to be consistent with max_memory_size (settings)
        data['hardware_memory_size'] = psutil.virtual_memory().total // 1024
        return self._format_diagnostics(data, output_format)
