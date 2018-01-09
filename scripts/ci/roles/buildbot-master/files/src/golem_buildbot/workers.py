from buildbot.plugins import worker

from .settings import local_settings

workers = [
    worker.Worker('macOS', local_settings['worker_pass']),
    worker.Worker('linux', local_settings['worker_pass']),
    worker.Worker('windows_server_2016', local_settings['worker_pass']),
]
