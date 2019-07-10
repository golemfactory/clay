import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

import os
import time
import uuid
from threading import Lock

from pydispatch import dispatcher
from twisted.internet.defer import Deferred, TimeoutError, inlineCallbacks

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import deadline_to_timeout
from golem.core.deferred import sync_wait
from golem.core.statskeeper import IntStatsKeeper
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.envs.docker.cpu import DockerCPUConfig, DockerCPUEnvironment
from golem.hardware import scale_memory, MemSize
from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot
from golem.resource.dirmanager import DirManager
from golem.task.timer import ProviderTimer
from golem.vm.vm import PythonProcVM, PythonTestVM

from .taskthread import TaskThread

if TYPE_CHECKING:
    from .taskserver import TaskServer  # noqa pylint:disable=unused-import
    from golem_messages.message.tasks import ComputeTaskDef  # noqa pylint:disable=unused-import


logger = logging.getLogger(__name__)


class CompStats(object):
    def __init__(self):
        self.computed_tasks = 0
        self.tasks_with_timeout = 0
        self.tasks_with_errors = 0
        self.tasks_requested = 0


class TaskComputer(object):
    """ TaskComputer is responsible for task computations that take
    place in Golem application. Tasks are started
    in separate threads.
    """

    lock = Lock()
    dir_lock = Lock()

    def __init__(
            self,
            task_server: 'TaskServer',
            docker_cpu_env: DockerCPUEnvironment,
            use_docker_manager=True,
            finished_cb=None
    ) -> None:
        self.task_server = task_server
        # Currently computing TaskThread
        self.counting_thread = None
        # Is task computer currently able to run computation?
        self.runnable = True
        self.listeners = []

        self.dir_manager: DirManager = DirManager(
            task_server.get_task_computer_root())

        self.docker_manager: DockerManager = DockerManager.install()
        if use_docker_manager:
            self.docker_manager.check_environment()  # pylint: disable=no-member
        self.use_docker_manager = use_docker_manager

        self.docker_cpu_env = docker_cpu_env
        sync_wait(self.docker_cpu_env.prepare())

        self.stats = IntStatsKeeper(CompStats)

        # So apparently it is perfectly fine for mypy to assign None to a
        # non-optional variable. And if I tried Optional['ComputeTaskDef']
        # then I would get "Optional[Any] is not indexable" error.
        # Get your sh*t together, mypy!
        self.assigned_subtask: 'ComputeTaskDef' = None

        self.support_direct_computation = False
        # Should this node behave as provider and compute tasks?
        self.compute_tasks = task_server.config_desc.accept_tasks \
            and not task_server.config_desc.in_shutdown
        self.finished_cb = finished_cb

    def task_given(self, ctd: 'ComputeTaskDef') -> None:
        assert self.assigned_subtask is None
        self.assigned_subtask = ctd
        ProviderTimer.start()

    def has_assigned_task(self) -> bool:
        return bool(self.assigned_subtask)

    @property
    def assigned_task_id(self) -> Optional[str]:
        if self.assigned_subtask is None:
            return None
        return self.assigned_subtask.get('task_id')

    def task_interrupted(self) -> None:
        assert self.assigned_subtask is not None
        self._task_finished()

    def task_computed(self, task_thread: TaskThread) -> None:
        if task_thread.end_time is None:
            task_thread.end_time = time.time()

        work_wall_clock_time = task_thread.end_time - task_thread.start_time
        try:
            subtask = self.assigned_subtask
            assert subtask is not None
            subtask_id = subtask['subtask_id']
            task_id = subtask['task_id']
            task_header = self.task_server.task_keeper.task_headers[task_id]
            # get paid for max working time,
            # thus task withholding won't make profit
            work_time_to_be_paid = task_header.subtask_timeout

        except (KeyError, AssertionError):
            logger.error("Task header not found in task keeper. "
                         "task_id=%r, subtask_id=%r",
                         task_id, subtask_id)
            self._task_finished()
            return

        was_success = False

        if task_thread.error or task_thread.error_msg:

            if "Task timed out" in task_thread.error_msg:
                self.stats.increase_stat('tasks_with_timeout')
            else:
                self.stats.increase_stat('tasks_with_errors')
                self.task_server.send_task_failed(
                    subtask_id,
                    subtask['task_id'],
                    task_thread.error_msg,
                )

        elif task_thread.result and 'data' in task_thread.result:

            logger.info("Task %r computed, work_wall_clock_time %s",
                        subtask_id,
                        str(work_wall_clock_time))
            self.stats.increase_stat('computed_tasks')

            try:
                self.task_server.send_results(
                    subtask_id,
                    subtask['task_id'],
                    task_thread.result,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Error sending the results: %r", exc)
            else:
                was_success = True

        else:
            self.stats.increase_stat('tasks_with_errors')
            self.task_server.send_task_failed(
                subtask_id,
                subtask['task_id'],
                "Wrong result format",
            )

        dispatcher.send(signal='golem.monitor', event='computation_time_spent',
                        success=was_success, value=work_time_to_be_paid)
        self._task_finished()

    def check_timeout(self):
        if self.counting_thread is not None:
            self.counting_thread.check_timeout()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        if not self.is_computing() or self.assigned_subtask is None:
            return None

        c: TaskThread = self.counting_thread
        try:
            outfilebasename = c.extra_data.get(  # type: ignore
                'crops'
            )[0].get(
                'outfilebasename'
            )
        except (IndexError, KeyError):
            outfilebasename = ''
        except TypeError:
            return None

        tcss = ComputingSubtaskStateSnapshot(
            subtask_id=self.assigned_subtask['subtask_id'],
            progress=c.get_progress(),
            seconds_to_timeout=c.task_timeout,
            running_time_seconds=(time.time() - c.start_time),
            outfilebasename=outfilebasename,
            **c.extra_data,
        )
        return tcss

    def is_computing(self) -> bool:
        with self.lock:
            return self.counting_thread is not None

    def get_host_state(self):
        if self.is_computing():
            return "Computing"
        return "Idle"

    def get_environment(self):
        task_header_keeper = self.task_server.task_keeper

        if not self.assigned_subtask:
            return None

        task_id = self.assigned_subtask['task_id']
        task_header = task_header_keeper.task_headers.get(task_id)
        if not task_header:
            return None

        return task_header.environment

    def config_changed(self):
        for l in self.listeners:
            l.config_changed()

    @inlineCallbacks
    def change_config(
            self,
            config_desc: ClientConfigDescriptor,
            in_background: bool = True
    ) -> Deferred:

        self.dir_manager = DirManager(
            self.task_server.get_task_computer_root())
        self.compute_tasks = config_desc.accept_tasks \
            and not config_desc.in_shutdown

        dm = self.docker_manager
        assert isinstance(dm, DockerManager)
        dm.build_config(config_desc)
        work_dirs = [Path(self.dir_manager.root_path)]

        yield self.docker_cpu_env.clean_up()
        self.docker_cpu_env.update_config(DockerCPUConfig(
            work_dirs=work_dirs,
            cpu_count=config_desc.num_cores,
            memory_mb=scale_memory(
                config_desc.max_memory_size,
                unit=MemSize.kibi,
                to_unit=MemSize.mebi
            )
        ))
        yield self.docker_cpu_env.prepare()

        if dm.hypervisor and self.use_docker_manager:  # noqa pylint: disable=no-member
            deferred = Deferred()
            # PyLint thinks dm is of type DockerConfigManager not DockerManager
            # pylint: disable=no-member
            dm.update_config(
                status_callback=self.is_computing,
                done_callback=deferred.callback,
                work_dirs=work_dirs,
                in_background=in_background
            )
            return (yield deferred)

        return False

    def register_listener(self, listener):
        self.listeners.append(listener)

    def lock_config(self, on: bool = True) -> None:
        self.runnable = not on
        for l in self.listeners:
            l.lock_config(on)

    def start_computation(self) -> None:  # pylint: disable=too-many-locals
        subtask = self.assigned_subtask
        assert subtask is not None

        task_id = subtask['task_id']
        subtask_id = subtask['subtask_id']
        docker_images = subtask['docker_images']
        extra_data = subtask['extra_data']
        subtask_deadline = subtask['deadline']

        task_header = self.task_server.task_keeper.task_headers.get(task_id)

        if not task_header:
            logger.warning("Subtask '%s' of task '%s' cannot be computed: "
                           "task header has been unexpectedly removed",
                           subtask_id, task_id)
            return

        deadline = min(task_header.deadline, subtask_deadline)
        task_timeout = deadline_to_timeout(deadline)

        unique_str = str(uuid.uuid4())

        logger.info("Starting computation of subtask %r (task: %r, deadline: "
                    "%r, docker images: %r)", subtask_id, task_id, deadline,
                    docker_images)

        with self.dir_lock:
            resource_dir = self.dir_manager.get_task_resource_dir(task_id)
            temp_dir = os.path.join(
                self.dir_manager.get_task_temporary_dir(task_id), unique_str)
            # self.dir_manager.clear_temporary(task_id)

            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

        if docker_images:
            docker_images = [DockerImage(**did) for did in docker_images]
            dir_mapping = DockerTaskThread.generate_dir_mapping(resource_dir,
                                                                temp_dir)
            tt = DockerTaskThread(docker_images, extra_data,
                                  dir_mapping, task_timeout)
        elif self.support_direct_computation:
            tt = PyTaskThread(extra_data, resource_dir, temp_dir,
                              task_timeout)
        else:
            logger.error("Cannot run PyTaskThread in this version")
            self.task_server.send_task_failed(
                subtask_id,
                self.assigned_subtask['task_id'],
                "Host direct task not supported",
            )

            self._task_finished()
            return

        with self.lock:
            self.counting_thread = tt

        self.task_server.task_keeper.task_started(task_id)
        tt.start().addBoth(lambda _: self.task_computed(tt))

    def _task_finished(self) -> None:
        ctd = self.assigned_subtask
        assert ctd is not None
        self.assigned_subtask = None

        ProviderTimer.finish()
        dispatcher.send(
            signal='golem.taskcomputer',
            event='subtask_finished',
            subtask_id=ctd['subtask_id'],
            min_performance=ctd['performance'],
        )

        with self.lock:
            self.counting_thread = None
        self.task_server.task_keeper.task_ended(ctd['task_id'])
        if self.finished_cb:
            self.finished_cb()

    def quit(self):
        if self.counting_thread is not None:
            self.counting_thread.end_comp()


class PyTaskThread(TaskThread):
    # pylint: disable=too-many-arguments
    def __init__(self, extra_data, res_path, tmp_path, timeout):
        super(PyTaskThread, self).__init__(
            extra_data, res_path, tmp_path, timeout)
        self.vm = PythonProcVM()


class PyTestTaskThread(PyTaskThread):
    # pylint: disable=too-many-arguments
    def __init__(self, extra_data, res_path, tmp_path, timeout):
        super(PyTestTaskThread, self).__init__(
            extra_data, res_path, tmp_path, timeout)
        self.vm = PythonTestVM()
