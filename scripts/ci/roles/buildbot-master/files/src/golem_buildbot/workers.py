from buildbot.plugins import worker

from .settings import local_settings

control_workers = [
    "control_01",
    "control_02",
    "control_03",
    "control_04",
    "control_05",
    "control_06",
    "control_07",
    "control_08",
]

macos_workers = [
    "macos_01",
    "macos_02",
]

linux_workers = [
    "linux_01",
    "linux_02",
    "linux_03",
    "linux_04",
]

windows_workers = [
    "windows_01",
    "windows_02",
]


workers = []

for raw_worker in control_workers:
    workers.append(worker.Worker(raw_worker, local_settings['worker_pass']))

for raw_worker in macos_workers:
    workers.append(worker.Worker(raw_worker, local_settings['worker_pass'],
                                 max_builds=1))

for raw_worker in linux_workers:
    workers.append(worker.Worker(raw_worker, local_settings['worker_pass'],
                                 max_builds=1))

for raw_worker in windows_workers:
    workers.append(worker.Worker(raw_worker, local_settings['worker_pass'],
                                 max_builds=1))
