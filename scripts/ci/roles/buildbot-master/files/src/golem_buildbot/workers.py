from buildbot.plugins import worker

from .settings import local_settings

workers = [
    worker.Worker('control_01', local_settings['worker_pass']),
    worker.Worker('control_02', local_settings['worker_pass']),
    worker.Worker('control_03', local_settings['worker_pass']),
    worker.Worker('control_04', local_settings['worker_pass']),
    worker.Worker('macOS', local_settings['worker_pass'], max_builds=1),
    worker.Worker('linux_01', local_settings['worker_pass'], max_builds=1),
    worker.Worker('linux_02', local_settings['worker_pass'], max_builds=1),
    worker.Worker('windows_server_2016', local_settings['worker_pass'],
                  max_builds=1),
]
