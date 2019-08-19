import asyncio
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Callable, Any

import os
import time
import uuid
from threading import Lock

from dataclasses import dataclass
from golem_messages.message.tasks import ComputeTaskDef, TaskHeader
from golem_task_api import ProviderAppClient, constants as task_api_constants
from pydispatch import dispatcher
from twisted.internet import defer

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import deadline_to_timeout
from golem.core.deferred import sync_wait, deferred_from_future
from golem.core.statskeeper import IntStatsKeeper
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.envs import EnvId, EnvStatus
from golem.envs.docker.cpu import DockerCPUConfig, DockerCPUEnvironment
from golem.envs.docker.gpu import DockerGPUConfig, DockerGPUEnvironment
from golem.hardware import scale_memory, MemSize
from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot
from golem.resource.dirmanager import DirManager
from golem.task.task_api import EnvironmentTaskApiService
from golem.task.envmanager import EnvironmentManager
from golem.task.timer import ProviderTimer
from golem.vm.vm import PythonProcVM, PythonTestVM

from .taskthread import TaskThread

if TYPE_CHECKING:
    from .taskserver import TaskServer  # noqa pylint:disable=unused-import


logger = logging.getLogger(__name__)


class CompStats(object):
    def __init__(self):
        self.computed_tasks = 0
        self.tasks_with_timeout = 0
        self.tasks_with_errors = 0
        self.tasks_requested = 0


class TaskComputerAdapter:
    """ This class hides old and new task computer under a single interface. """

    def __init__(
            self,
            task_server: 'TaskServer',
            env_manager: EnvironmentManager,
            use_docker_manager: bool = True,
            finished_cb: Callable[[], Any] = lambda: None
    ) -> None:
        self.stats = IntStatsKeeper(CompStats)
        self._task_server = task_server
        self._old_computer = TaskComputer(
            task_server=task_server,
            stats_keeper=self.stats,
            use_docker_manager=use_docker_manager,
            finished_cb=finished_cb
        )
        self._new_computer = NewTaskComputer(
            env_manager=env_manager,
            work_dir=task_server.get_task_computer_root(),
            task_finished_callback=finished_cb,
            stats_keeper=self.stats
        )
        sync_wait(self._new_computer.prepare())

        # Should this node behave as provider and compute tasks?
        self.compute_tasks = task_server.config_desc.accept_tasks \
            and not task_server.config_desc.in_shutdown
        self.runnable = True
        self._listeners = []  # type: ignore

    @property
    def dir_manager(self) -> DirManager:
        # FIXME: This shouldn't be part of the public interface probably
        return self._old_computer.dir_manager

    def task_given(self, ctd: ComputeTaskDef) -> None:
        assert not self._new_computer.has_assigned_task()
        assert not self._old_computer.has_assigned_task()

        task_id = ctd['task_id']
        task_header = self._task_server.task_keeper.task_headers[task_id]
        if task_header.environment_prerequisites is not None:
            self._new_computer.task_given(task_header, ctd)
        else:
            self._old_computer.task_given(ctd)

    def has_assigned_task(self) -> bool:
        return self._new_computer.has_assigned_task() \
            or self._old_computer.has_assigned_task()

    @property
    def assigned_task_id(self) -> Optional[str]:
        return self._new_computer.assigned_task_id \
            or self._old_computer.assigned_task_id

    @property
    def assigned_subtask_id(self) -> Optional[str]:
        return self._new_computer.assigned_subtask_id \
            or self._old_computer.assigned_subtask_id

    @property
    def support_direct_computation(self) -> bool:
        return self._old_computer.support_direct_computation

    @support_direct_computation.setter
    def support_direct_computation(self, value: bool) -> None:
        self._old_computer.support_direct_computation = value

    def get_task_resources_dir(self) -> Path:
        if not self._new_computer.has_assigned_task():
            raise ValueError(
                'Task resources directory only available when a task-api task '
                'is assigned')
        return self._new_computer.get_task_resources_dir()

    def start_computation(self) -> None:
        if self._new_computer.has_assigned_task():
            task_id = self.assigned_task_id
            subtask_id = self.assigned_subtask_id
            computation = self._new_computer.compute()
            # Fire and forget because it resolves when computation ends
            self._handle_computation_results(task_id, subtask_id, computation)
        elif self._old_computer.has_assigned_task():
            self._old_computer.start_computation()
        else:
            raise RuntimeError('start_computation: No task assigned.')

    # FIXME: Move this code to TaskServer when old TaskComputer is removed
    @defer.inlineCallbacks
    def _handle_computation_results(
            self,
            task_id: str,
            subtask_id: str,
            computation: defer.Deferred
    ) -> defer.Deferred:
        try:
            output_file = yield computation
            self._task_server.send_results(
                subtask_id=subtask_id,
                task_id=task_id,
                task_api_result=output_file,
            )
        except Exception as e:  # pylint: disable=broad-except
            self._task_server.send_task_failed(
                subtask_id=subtask_id,
                task_id=task_id,
                err_msg=str(e)
            )

    def task_interrupted(self) -> None:
        if self._new_computer.has_assigned_task():
            self._new_computer.task_interrupted()
        elif self._old_computer.has_assigned_task():
            self._old_computer.task_interrupted()
        else:
            raise RuntimeError('task_interrupted: No task assigned.')

    def check_timeout(self) -> None:
        # No active timeout checking is needed for the new computer
        if self._old_computer.has_assigned_task():
            self._old_computer.check_timeout()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        if self._old_computer.has_assigned_task():
            return self._old_computer.get_progress()
        return None

    def get_environment(self) -> Optional[EnvId]:
        if self._new_computer.has_assigned_task():
            return self._new_computer.get_current_computing_env()
        if self._old_computer.has_assigned_task():
            return self._old_computer.get_environment()
        return None

    def register_listener(self, listener):
        self._listeners.append(listener)

    def lock_config(self, on: bool = True) -> None:
        self.runnable = not on
        for l in self._listeners:
            l.lock_config(on)

    @defer.inlineCallbacks
    def change_config(
            self,
            config_desc: ClientConfigDescriptor,
            in_background: bool = True
    ) -> defer.Deferred:
        self.compute_tasks = config_desc.accept_tasks \
            and not config_desc.in_shutdown
        work_dir = Path(self._task_server.get_task_computer_root())
        yield self._new_computer.change_config(
            config_desc=config_desc,
            work_dir=work_dir)
        return (yield self._old_computer.change_config(
            config_desc=config_desc,
            in_background=in_background))

    def quit(self) -> None:
        sync_wait(self._new_computer.clean_up())
        self._old_computer.quit()


class NewTaskComputer:
    # pylint: disable=too-many-instance-attributes

    @dataclass
    class AssignedTask:
        task_id: str
        subtask_id: str
        subtask_params: dict
        env_id: EnvId
        prereq_dict: dict
        performance: float
        subtask_timeout: int
        deadline: int

    def __init__(
            self,
            env_manager: EnvironmentManager,
            work_dir: Path,
            task_finished_callback: Callable[[], Any],
            stats_keeper: Optional[IntStatsKeeper] = None
    ) -> None:
        self._env_manager = env_manager
        self._work_dir = work_dir
        self._task_finished_callback = task_finished_callback
        self._stats_keeper = stats_keeper or IntStatsKeeper(CompStats)
        self._assigned_task: Optional[NewTaskComputer.AssignedTask] = None
        self._computation: Optional[defer.Deferred] = None

    @defer.inlineCallbacks
    def prepare(self) -> defer.Deferred:
        # FIXME: Decide when and how to prepare environments
        docker_cpu = self._env_manager.environment(DockerCPUEnvironment.ENV_ID)
        yield docker_cpu.prepare()

        if not self._env_manager.enabled(DockerGPUEnvironment.ENV_ID):
            return

        docker_gpu = self._env_manager.environment(DockerGPUEnvironment.ENV_ID)
        yield docker_gpu.prepare()

    @defer.inlineCallbacks
    def clean_up(self) -> defer.Deferred:
        # FIXME: Decide when and how to clean up environments
        docker_cpu = self._env_manager.environment(DockerCPUEnvironment.ENV_ID)
        if docker_cpu.status() is not EnvStatus.DISABLED:
            yield docker_cpu.clean_up()

        if not self._env_manager.enabled(DockerGPUEnvironment.ENV_ID):
            return

        docker_gpu = self._env_manager.environment(DockerGPUEnvironment.ENV_ID)
        if docker_gpu.status() is not EnvStatus.DISABLED:
            yield docker_gpu.clean_up()

    def has_assigned_task(self) -> bool:
        return self._assigned_task is not None

    @property
    def assigned_task_id(self) -> Optional[str]:
        if self._assigned_task is None:
            return None
        return self._assigned_task.task_id

    @property
    def assigned_subtask_id(self) -> Optional[str]:
        if self._assigned_task is None:
            return None
        return self._assigned_task.subtask_id

    def get_task_resources_dir(self) -> Path:
        return self._get_task_dir() / task_api_constants.NETWORK_RESOURCES_DIR

    def _is_computing(self) -> bool:
        return self._computation is not None

    def task_given(
            self,
            task_header: TaskHeader,
            compute_task_def: ComputeTaskDef
    ) -> None:
        assert not self.has_assigned_task()
        self._assigned_task = self.AssignedTask(
            task_id=task_header.task_id,
            subtask_id=compute_task_def['subtask_id'],
            subtask_params=compute_task_def['extra_data'],
            env_id=task_header.environment,
            prereq_dict=task_header.environment_prerequisites,
            performance=compute_task_def['performance'],
            subtask_timeout=task_header.subtask_timeout,
            deadline=min(task_header.deadline, compute_task_def['deadline'])
        )
        ProviderTimer.start()

    def compute(self) -> defer.Deferred:
        assigned_task = self._assigned_task
        assert assigned_task is not None

        task_api_service = self._get_task_api_service()
        app_client = ProviderAppClient(service=task_api_service)
        compute_future = asyncio.ensure_future(app_client.compute(
            task_id=assigned_task.task_id,
            subtask_id=assigned_task.subtask_id,
            subtask_params=assigned_task.subtask_params
        ))

        self._computation = deferred_from_future(compute_future)

        from twisted.internet import reactor
        timeout = int(deadline_to_timeout(assigned_task.deadline))
        self._computation.addTimeout(timeout, reactor)
        return self._wait_until_computation_ends(app_client)

    @defer.inlineCallbacks
    def _wait_until_computation_ends(
            self,
            app_client: ProviderAppClient
    ) -> defer.Deferred:
        assigned_task = self._assigned_task
        assert assigned_task is not None
        task_dir = self._get_task_dir()

        success = False
        try:
            output_file = yield self._computation
            logger.info(
                'Task computation succeeded. task_id=%r subtask_id=%r',
                assigned_task.task_id,
                assigned_task.subtask_id
            )
            success = True
            self._stats_keeper.increase_stat('computed_tasks')
            return task_dir / output_file  # Return *absolute* result path
        except defer.CancelledError:
            logger.warning(
                'Task computation interrupted. task_id=%r subtask_id=%r',
                assigned_task.task_id,
                assigned_task.subtask_id
            )
        except defer.TimeoutError:
            logger.error(
                'Task computation timed out. task_id=%r subtask_id=%r',
                assigned_task.task_id,
                assigned_task.subtask_id
            )
            self._stats_keeper.increase_stat('tasks_with_timeout')
        except Exception:
            logger.exception(
                'Task computation failed. task_id=%r subtask_id=%r',
                assigned_task.task_id,
                assigned_task.subtask_id
            )
            self._stats_keeper.increase_stat('tasks_with_errors')
            raise
        finally:
            dispatcher.send(
                signal='golem.monitor',
                event='computation_time_spent',
                success=success,
                value=assigned_task.subtask_timeout  # Time to be paid
            )
            dispatcher.send(
                signal='golem.taskcomputer',
                event='subtask_finished',
                subtask_id=assigned_task.subtask_id,
                min_performance=assigned_task.performance,
            )
            ProviderTimer.finish()
            self._computation = None
            self._assigned_task = None
            self._task_finished_callback()
            if not success:
                # Cleanup can throw errors, do this last
                yield app_client.shutdown()

    def _get_task_dir(self) -> Path:
        assert self._assigned_task is not None
        env_id = self._assigned_task.env_id
        task_id = self._assigned_task.task_id
        return self._work_dir / env_id / task_id

    def _get_task_api_service(self) -> EnvironmentTaskApiService:
        assert self._assigned_task is not None
        env_id = self._assigned_task.env_id
        prereq_dict = self._assigned_task.prereq_dict

        env = self._env_manager.environment(env_id)
        payload_builder = self._env_manager.payload_builder(env_id)
        prereq = env.parse_prerequisites(prereq_dict)
        shared_dir = self._get_task_dir()

        return EnvironmentTaskApiService(
            env=env,
            payload_builder=payload_builder,
            prereq=prereq,
            shared_dir=shared_dir
        )

    def task_interrupted(self) -> None:
        assert self.has_assigned_task()
        assert self._computation is not None
        self._computation.cancel()

    def get_current_computing_env(self) -> Optional[EnvId]:
        if self._assigned_task is None:
            return None
        return self._assigned_task.env_id

    @defer.inlineCallbacks
    def change_config(
            self,
            config_desc: ClientConfigDescriptor,
            work_dir: Path
    ) -> defer.Deferred:
        assert not self._is_computing()
        self._work_dir = work_dir

        config_dict = dict(
            work_dirs=[work_dir],
            cpu_count=config_desc.num_cores,
            memory_mb=scale_memory(
                config_desc.max_memory_size,
                unit=MemSize.kibi,
                to_unit=MemSize.mebi
            )
        )

        # FIXME: Decide how to properly configure environments
        docker_cpu = self._env_manager.environment(DockerCPUEnvironment.ENV_ID)
        yield docker_cpu.clean_up()
        docker_cpu.update_config(DockerCPUConfig(**config_dict))
        yield docker_cpu.prepare()

        if not self._env_manager.enabled(DockerGPUEnvironment.ENV_ID):
            return

        docker_gpu = self._env_manager.environment(DockerGPUEnvironment.ENV_ID)
        yield docker_gpu.clean_up()
        docker_gpu.update_config(DockerGPUConfig(**config_dict))
        yield docker_gpu.prepare()


class TaskComputer:  # pylint: disable=too-many-instance-attributes
    """ TaskComputer is responsible for task computations that take
    place in Golem application. Tasks are started in separate threads. """

    lock = Lock()
    dir_lock = Lock()

    def __init__(
            self,
            task_server: 'TaskServer',
            stats_keeper: Optional[IntStatsKeeper] = None,
            use_docker_manager=True,
            finished_cb=None
    ) -> None:
        self.task_server = task_server
        # Currently computing TaskThread
        self.counting_thread = None

        self.dir_manager: DirManager = DirManager(
            task_server.get_task_computer_root())

        self.docker_manager: DockerManager = DockerManager.install()
        if use_docker_manager:
            self.docker_manager.check_environment()  # pylint: disable=no-member
        self.use_docker_manager = use_docker_manager

        self.stats = stats_keeper or IntStatsKeeper(CompStats)

        # So apparently it is perfectly fine for mypy to assign None to a
        # non-optional variable. And if I tried Optional['ComputeTaskDef']
        # then I would get "Optional[Any] is not indexable" error.
        # Get your sh*t together, mypy!
        self.assigned_subtask: ComputeTaskDef = None

        self.support_direct_computation = False
        self.finished_cb = finished_cb

    def task_given(self, ctd: ComputeTaskDef) -> None:
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

    @property
    def assigned_subtask_id(self) -> Optional[str]:
        if self.assigned_subtask is None:
            return None
        return self.assigned_subtask.get('subtask_id')

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

            assert isinstance(task_thread.result, dict)
            try:
                self.task_server.send_results(
                    subtask_id,
                    subtask['task_id'],
                    task_thread.result['data'],
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
        if not self._is_computing() or self.assigned_subtask is None:
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

    def _is_computing(self) -> bool:
        with self.lock:
            return self.counting_thread is not None

    def get_environment(self):
        task_header_keeper = self.task_server.task_keeper

        if not self.assigned_subtask:
            return None

        task_id = self.assigned_subtask['task_id']
        task_header = task_header_keeper.task_headers.get(task_id)
        if not task_header:
            return None

        return task_header.environment

    @defer.inlineCallbacks
    def change_config(
            self,
            config_desc: ClientConfigDescriptor,
            in_background: bool = True
    ) -> defer.Deferred:

        self.dir_manager = DirManager(
            self.task_server.get_task_computer_root())

        dm = self.docker_manager
        assert isinstance(dm, DockerManager)
        dm.build_config(config_desc)
        work_dirs = [Path(self.dir_manager.root_path)]

        if dm.hypervisor and self.use_docker_manager:  # noqa pylint: disable=no-member
            deferred = defer.Deferred()
            # PyLint thinks dm is of type DockerConfigManager not DockerManager
            # pylint: disable=no-member
            dm.update_config(
                status_callback=self._is_computing,
                done_callback=deferred.callback,
                work_dirs=work_dirs,
                in_background=in_background
            )
            return (yield deferred)

        return False

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
