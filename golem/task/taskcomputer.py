import logging
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

import os
import time
import uuid
from threading import Lock

from pydispatch import dispatcher
from twisted.internet.defer import Deferred, TimeoutError

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import deadline_to_timeout
from golem.core.deferred import sync_wait
from golem.core.statskeeper import IntStatsKeeper
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot
from golem.resource.dirmanager import DirManager
from golem.task.timer import ProviderTimer
from golem.vm.vm import PythonProcVM, PythonTestVM

from .taskthread import TaskThread

if TYPE_CHECKING:
    from .taskserver import TaskServer  # noqa pylint:disable=unused-import
    from golem_messages.message.tasks import ComputeTaskDef  # noqa pylint:disable=unused-import


logger = logging.getLogger(__name__)

BENCHMARK_TIMEOUT = 60  # s


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

    def __init__(self, task_server: 'TaskServer', use_docker_manager=True,
                 finished_cb=None) -> None:
        self.task_server = task_server
        # Currently computing TaskThread
        self.counting_thread = None
        # Is task computer currently able to run computation?
        self.runnable = True
        self.listeners = []
        self.last_task_request = time.time()

        self.dir_manager: DirManager = DirManager(
            task_server.get_task_computer_root())
        self.task_request_frequency = None

        self.docker_manager: DockerManager = DockerManager.install()
        if use_docker_manager:
            self.docker_manager.check_environment()

        self.use_docker_manager = use_docker_manager
        run_benchmarks = self.task_server.benchmark_manager.benchmarks_needed()
        deferred = self.change_config(
            task_server.config_desc, in_background=False,
            run_benchmarks=run_benchmarks)
        try:
            sync_wait(deferred, BENCHMARK_TIMEOUT)
        except TimeoutError:
            logger.warning('Benchmark computation timed out')

        self.stats = IntStatsKeeper(CompStats)

        self.assigned_subtask: Optional['ComputeTaskDef'] = None

        self.last_task_timeout_checking = None
        self.support_direct_computation = False
        # Should this node behave as provider and compute tasks?
        self.compute_tasks = task_server.config_desc.accept_tasks \
            and not task_server.config_desc.in_shutdown
        self.finished_cb = finished_cb

    def task_given(self, ctd: 'ComputeTaskDef'):
        if self.assigned_subtask is not None:
            logger.error("Trying to assign a task, when it's already assigned")
            return False

        ProviderTimer.start()

        self.assigned_subtask = ctd
        self.__request_resource(
            ctd['task_id'],
            ctd['subtask_id'],
            ctd['resources'],
        )
        return True

    def has_assigned_task(self) -> bool:
        return bool(self.assigned_subtask)

    def resource_collected(self, res_id):
        subtask = self.assigned_subtask
        if not subtask or subtask['task_id'] != res_id:
            logger.error("Resource collected for a wrong task, %s", res_id)
            return False
        self.last_task_timeout_checking = time.time()
        self.__compute_task(
            subtask['subtask_id'],
            subtask['docker_images'],
            subtask['extra_data'],
            subtask['deadline'])
        return True

    def resource_failure(self, res_id, reason):
        subtask = self.assigned_subtask
        self.assigned_subtask = None
        if not subtask or subtask['task_id'] != res_id:
            logger.error("Resource failure for a wrong task, %s", res_id)
            return
        self.task_server.send_task_failed(
            subtask['subtask_id'],
            subtask['task_id'],
            'Error downloading resources: {}'.format(reason),
        )
        self.__task_finished(subtask)

    def task_computed(self, task_thread: TaskThread) -> None:
        if task_thread.end_time is None:
            task_thread.end_time = time.time()

        work_wall_clock_time = task_thread.end_time - task_thread.start_time
        try:
            subtask = self.assigned_subtask
            assert subtask is not None
            self.assigned_subtask = None
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
            self.__task_finished(subtask)
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
        self.__task_finished(subtask)

    def run(self):
        """ Main loop of task computer """
        if self.counting_thread is not None:
            self.counting_thread.check_timeout()
        elif self.compute_tasks and self.runnable:
            last_request = time.time() - self.last_task_request
            if last_request > self.task_request_frequency:
                self.__request_task()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        if not self.is_computing() or self.assigned_subtask is None:
            return None

        c: TaskThread = self.counting_thread
        tcss = ComputingSubtaskStateSnapshot(
            subtask_id=self.assigned_subtask['subtask_id'],
            progress=c.get_progress(),
            seconds_to_timeout=c.task_timeout,
            running_time_seconds=(time.time() - c.start_time),
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

    def change_config(self, config_desc, in_background=True,
                      run_benchmarks=False):
        self.dir_manager = DirManager(
            self.task_server.get_task_computer_root())
        self.task_request_frequency = config_desc.task_request_interval
        self.compute_tasks = config_desc.accept_tasks \
            and not config_desc.in_shutdown
        return self.change_docker_config(
            config_desc=config_desc,
            run_benchmarks=run_benchmarks,
            work_dir=Path(self.dir_manager.root_path),
            in_background=in_background)

    def config_changed(self):
        for l in self.listeners:
            l.config_changed()

    def change_docker_config(
            self,
            config_desc: ClientConfigDescriptor,
            run_benchmarks: bool,
            work_dir: Path,
            in_background: bool = True
    ) -> Optional[Deferred]:

        dm = self.docker_manager
        assert isinstance(dm, DockerManager)
        dm.build_config(config_desc)

        deferred = Deferred()
        if not dm.hypervisor and run_benchmarks:
            self.task_server.benchmark_manager.run_all_benchmarks(
                deferred.callback, deferred.errback
            )
            return deferred

        if dm.hypervisor and self.use_docker_manager:  # noqa pylint: disable=no-member
            self.lock_config(True)

            def status_callback():
                return self.is_computing()

            def done_callback(config_differs):
                if run_benchmarks or config_differs:
                    self.task_server.benchmark_manager.run_all_benchmarks(
                        deferred.callback, deferred.errback
                    )
                else:
                    deferred.callback('Benchmarks not executed')
                logger.debug("Resuming new task computation")
                self.lock_config(False)
                self.runnable = True

            self.runnable = False
            # PyLint thinks dm is of type DockerConfigManager not DockerManager
            # pylint: disable=no-member
            dm.update_config(
                status_callback=status_callback,
                done_callback=done_callback,
                work_dir=work_dir,
                in_background=in_background)

            return deferred

        return None

    def register_listener(self, listener):
        self.listeners.append(listener)

    def lock_config(self, on=True):
        for l in self.listeners:
            l.lock_config(on)

    def __request_task(self):
        if self.has_assigned_task():
            return

        self.last_task_request = time.time()
        requested_task = self.task_server.request_task()
        if requested_task is not None:
            self.stats.increase_stat('tasks_requested')

    def __request_resource(self, task_id, subtask_id, resources):
        self.task_server.request_resource(task_id, subtask_id, resources)

    def __compute_task(self, subtask_id, docker_images,
                       extra_data, subtask_deadline):
        task_id = self.assigned_subtask['task_id']
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
            subtask = self.assigned_subtask
            self.assigned_subtask = None
            self.task_server.send_task_failed(
                subtask_id,
                subtask['task_id'],
                "Host direct task not supported",
            )

            self.__task_finished(subtask)
            return

        with self.lock:
            self.counting_thread = tt

        self.task_server.task_keeper.task_started(task_id)
        tt.start().addBoth(lambda _: self.task_computed(tt))

    def __task_finished(self, ctd: 'ComputeTaskDef') -> None:

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
