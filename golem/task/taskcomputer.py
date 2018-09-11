import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

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
from golem.resource.resourcesmanager import ResourcesManager
from golem.vm.vm import PythonProcVM, PythonTestVM

from .taskthread import TaskThread

if TYPE_CHECKING:
    from .taskserver import TaskServer  # noqa pylint:disable=unused-import


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
        # Id of the task that we're currently waiting for  for
        self.waiting_for_task: Optional[str] = None
        # Id of the task that we're currently computing
        self.counting_task = None
        # TaskThread
        self.counting_thread = None
        self.task_requested = False
        # Is task computer currently able to run computation?
        self.runnable = True
        self.listeners = []
        self.last_task_request = time.time()

        # when we should stop waiting for the task
        self.waiting_deadline = None

        self.dir_manager = None
        self.resource_manager: Optional[ResourcesManager] = None
        self.task_request_frequency = None
        # Is there a time limit after which we don't wait for task timeout
        # anymore
        self.use_waiting_deadline = False
        self.waiting_for_task_session_timeout = None

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

        self.assigned_subtasks = {}
        self.task_to_subtask_mapping = {}
        self.max_assigned_tasks = 1

        self.delta = None
        self.last_task_timeout_checking = None
        self.support_direct_computation = False
        # Should this node behave as provider and compute tasks?
        self.compute_tasks = task_server.config_desc.accept_tasks \
            and not task_server.config_desc.in_shutdown
        self.finished_cb = finished_cb

    def task_given(self, ctd):
        if ctd['subtask_id'] in self.assigned_subtasks:
            return False
        self.wait(ttl=deadline_to_timeout(ctd['deadline']))
        self.assigned_subtasks[ctd['subtask_id']] = ctd
        self.task_to_subtask_mapping[ctd['task_id']] = ctd['subtask_id']
        self.__request_resource(
            ctd['task_id'],
            ctd['subtask_id']
        )
        return True

    def resource_given(self, task_id):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                subtask = self.assigned_subtasks[subtask_id]

                with self.lock:
                    if self.counting_thread is not None:
                        logger.error(
                            "Got resource for task: %r"
                            "But I'm busy with another one. Ignoring.",
                            task_id)
                        return  # busy
                    self.__compute_task(
                        subtask_id,
                        subtask['docker_images'],
                        subtask['src_code'],
                        subtask['extra_data'],
                        subtask['short_description'],
                        subtask['deadline'])
                    self.waiting_for_task = None
                return True
            else:
                return False

    def task_resource_collected(self, task_id, unpack_delta=True):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                subtask = self.assigned_subtasks[subtask_id]
                if unpack_delta:
                    rs_dir = self.dir_manager.get_task_resource_dir(task_id)
                    self.task_server.unpack_delta(rs_dir, self.delta, task_id)
                self.delta = None
                self.last_task_timeout_checking = time.time()
                self.__compute_task(
                    subtask_id,
                    subtask['docker_images'],
                    subtask['src_code'],
                    subtask['extra_data'],
                    subtask['short_description'],
                    subtask['deadline'])
                return True
            return False

    def task_resource_failure(self, task_id, reason):
        if task_id not in self.task_to_subtask_mapping:
            return
        subtask_id = self.task_to_subtask_mapping.pop(task_id)
        if subtask_id in self.assigned_subtasks:
            subtask = self.assigned_subtasks.pop(subtask_id)
            self.task_server.send_task_failed(
                subtask_id,
                subtask['task_id'],
                'Error downloading resources: {}'.format(reason),
            )
        self.session_closed()

    def wait_for_resources(self, task_id, delta):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                self.delta = delta

    def task_request_rejected(self, task_id, reason):
        logger.info("Task %r request rejected: %r", task_id, reason)

    def resource_request_rejected(self, subtask_id, reason):
        logger.info("Task %r resource request rejected: %r",
                    subtask_id, reason)
        self.assigned_subtasks.pop(subtask_id, None)
        self.reset()

    def task_computed(self, task_thread: TaskThread) -> None:
        self.reset()

        if task_thread.end_time is None:
            task_thread.end_time = time.time()

        with self.lock:
            if self.counting_thread is task_thread:
                self.counting_thread = None

        work_wall_clock_time = task_thread.end_time - task_thread.start_time
        subtask_id = task_thread.subtask_id
        try:
            subtask = self.assigned_subtasks.pop(subtask_id)  # ComputeTaskDef
            # get paid for max working time,
            # thus task withholding won't make profit
            task_header = \
                self.task_server.task_keeper.task_headers[subtask['task_id']]
            work_time_to_be_paid = task_header.subtask_timeout

        except KeyError:
            logger.error("No subtask with id %r", subtask_id)
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

        elif task_thread.result \
                and 'data' in task_thread.result \
                and 'result_type' in task_thread.result:

            logger.info("Task %r computed, work_wall_clock_time %s",
                        subtask_id,
                        str(work_wall_clock_time))
            self.stats.increase_stat('computed_tasks')
            self.task_server.send_results(
                subtask_id,
                subtask['task_id'],
                task_thread.result,
            )
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

        self.counting_task = None
        if self.finished_cb:
            self.finished_cb()

    def run(self):
        """ Main loop of task computer """
        if self.counting_task:
            if self.counting_thread is not None:
                self.counting_thread.check_timeout()
        elif self.compute_tasks and self.runnable:
            if not self.waiting_for_task:
                last_request = time.time() - self.last_task_request
                if last_request > self.task_request_frequency \
                        and self.counting_thread is None:
                    self.__request_task()
            elif self.use_waiting_deadline:
                if self.waiting_deadline < time.time():
                    self.reset()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        if self.counting_thread is None:
            return None

        c: TaskThread = self.counting_thread
        tcss = ComputingSubtaskStateSnapshot(
            subtask_id=c.get_subtask_id(),
            progress=c.get_progress(),
            seconds_to_timeout=c.task_timeout,
            running_time_seconds=(time.time() - c.start_time),
            **c.extra_data,
        )
        return tcss

    def get_host_state(self):
        if self.counting_task is not None:
            return "Computing"
        return "Idle"

    def change_config(self, config_desc, in_background=True,
                      run_benchmarks=False):
        self.dir_manager = DirManager(self.task_server.get_task_computer_root())
        self.resource_manager = ResourcesManager(self.dir_manager, self)
        self.task_request_frequency = config_desc.task_request_interval
        self.waiting_for_task_session_timeout = \
            config_desc.waiting_for_task_session_timeout
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
    ) -> Deferred:
        dm = self.docker_manager
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
                return self.counting_task

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
            dm.update_config(
                status_callback=status_callback,
                done_callback=done_callback,
                work_dir=work_dir,
                in_background=in_background)

            return deferred

    def register_listener(self, listener):
        self.listeners.append(listener)

    def lock_config(self, on=True):
        for l in self.listeners:
            l.lock_config(on)

    def session_timeout(self):
        self.session_closed()

    def session_closed(self):
        if self.counting_task is None:
            self.reset()

    def wait(self, wait=True, ttl=None):
        self.use_waiting_deadline = wait
        if ttl is None:
            ttl = self.waiting_for_task_session_timeout

        self.waiting_deadline = time.time() + ttl

    def reset(self, counting_task=None):
        self.counting_task = counting_task
        self.use_waiting_deadline = False
        self.task_requested = False
        self.waiting_for_task = None
        self.waiting_deadline = None

    def __request_task(self):
        with self.lock:
            perform_request = not self.waiting_for_task and \
                              (self.counting_task is None)

        if not perform_request:
            return

        now = time.time()
        self.wait()
        self.last_task_request = now
        self.waiting_for_task = self.task_server.request_task()
        if self.waiting_for_task is not None:
            self.stats.increase_stat('tasks_requested')

    def __request_resource(self, task_id, subtask_id):
        self.wait(False)
        if not self.task_server.request_resource(task_id, subtask_id):
            self.reset()

    def __compute_task(self, subtask_id, docker_images,
                       src_code, extra_data, short_desc, subtask_deadline):
        task_id = self.assigned_subtasks[subtask_id]['task_id']
        task_header = self.task_server.task_keeper.task_headers.get(task_id)

        if not task_header:
            logger.warning("Subtask '%s' of task '%s' cannot be computed: "
                           "task header has been unexpectedly removed",
                           subtask_id, task_id)
            return self.session_closed()

        deadline = min(task_header.deadline, subtask_deadline)
        task_timeout = deadline_to_timeout(deadline)

        unique_str = str(uuid.uuid4())

        logger.info("Starting computation of subtask %r (task: %r, deadline: "
                    "%r, docker images: %r)", subtask_id, task_id, deadline,
                    docker_images)

        self.reset(counting_task=task_id)

        with self.dir_lock:
            resource_dir = self.resource_manager.get_resource_dir(task_id)
            temp_dir = os.path.join(
                self.resource_manager.get_temporary_dir(task_id), unique_str)
            # self.dir_manager.clear_temporary(task_id)

            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

        if docker_images:
            docker_images = [DockerImage(**did) for did in docker_images]
            dir_mapping = DockerTaskThread.generate_dir_mapping(resource_dir,
                                                                temp_dir)
            tt = DockerTaskThread(subtask_id, docker_images,
                                  src_code, extra_data, short_desc,
                                  dir_mapping, task_timeout)
        elif self.support_direct_computation:
            tt = PyTaskThread(subtask_id, src_code,
                              extra_data, short_desc, resource_dir, temp_dir,
                              task_timeout)
        else:
            logger.error("Cannot run PyTaskThread in this version")
            subtask = self.assigned_subtasks.pop(subtask_id)
            self.task_server.send_task_failed(
                subtask_id,
                subtask['task_id'],
                "Host direct task not supported",
            )
            self.counting_task = None
            if self.finished_cb:
                self.finished_cb()

            return

        self.counting_thread = tt
        tt.start().addBoth(lambda _: self.task_computed(tt))

    def quit(self):
        if self.counting_thread is not None:
            self.counting_thread.end_comp()


class AssignedSubTask(object):
    def __init__(self, src_code, extra_data, short_desc, owner_address,
                 owner_port):
        self.src_code = src_code
        self.extra_data = extra_data
        self.short_desc = short_desc
        self.owner_address = owner_address
        self.owner_port = owner_port


class PyTaskThread(TaskThread):
    # pylint: disable=too-many-arguments
    def __init__(self, subtask_id, src_code,
                 extra_data, short_desc, res_path, tmp_path, timeout):
        super(PyTaskThread, self).__init__(
            subtask_id, src_code, extra_data,
            short_desc, res_path, tmp_path, timeout)
        self.vm = PythonProcVM()


class PyTestTaskThread(PyTaskThread):
    # pylint: disable=too-many-arguments
    def __init__(self, subtask_id, src_code,
                 extra_data, short_desc, res_path, tmp_path, timeout):
        super(PyTestTaskThread, self).__init__(
            subtask_id, src_code, extra_data,
            short_desc, res_path, tmp_path, timeout)
        self.vm = PythonTestVM()
