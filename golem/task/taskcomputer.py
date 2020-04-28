# flake8: noqa

import asyncio
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Callable, Any, List, Set

import os
import time
import uuid
from threading import Lock

from dataclasses import dataclass
from golem_messages.message.tasks import TaskFailure
from golem_task_api import ProviderAppClient, constants as task_api_constants
from golem_task_api.envs import DOCKER_CPU_ENV_ID, DOCKER_GPU_ENV_ID
from pydispatch import dispatcher
from twisted.internet import defer

from golem.core.common import deadline_to_timeout
from golem.core.deferred import deferred_from_future
from golem.core.statskeeper import IntStatsKeeper
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.envs.docker.cpu import DockerCPUConfig
from golem.envs.docker.gpu import DockerGPUConfig
from golem.hardware import scale_memory, MemSize
from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot
from golem.resource.dirmanager import DirManager
from golem.task.task_api import EnvironmentTaskApiService
from golem.task.timer import ProviderTimer
from golem.vm.vm import PythonProcVM, PythonTestVM

from .taskthread import TaskThread, BudgetExceededException, TimeoutException

if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from golem_messages.message.tasks import ComputeTaskDef, TaskHeader

    from golem.clientconfigdescriptor import ClientConfigDescriptor
    from golem.envs import EnvId
    from golem.task.envmanager import EnvironmentManager

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
            env_manager: 'EnvironmentManager',
            use_docker_manager: bool = True,
            finished_cb: Callable[[], Any] = lambda: None
    ) -> None:
        self.stats = IntStatsKeeper(CompStats)
        self._task_server = task_server
        self._finished_cb = finished_cb
        self._old_computer = TaskComputer(
            task_server=task_server,
            stats_keeper=self.stats,
            use_docker_manager=use_docker_manager,
            finished_cb=finished_cb
        )
        self._new_computer = NewTaskComputer(
            env_manager=env_manager,
            work_dir=Path(task_server.get_task_computer_root()),
            stats_keeper=self.stats
        )

        self.runnable = True
        self._listeners = []  # type: ignore

    @property
    def free_cores(self) -> int:
        if self._new_computer.has_assigned_task():
            return 0
        return self._old_computer.free_cores

    @property
    def dir_manager(self) -> DirManager:
        # FIXME: This shouldn't be part of the public interface probably
        return self._old_computer.dir_manager

    @property
    def compute_tasks(self):
        # Should this node behave as provider and compute tasks?
        config = self._task_server.config_desc
        return config.accept_tasks and not config.in_shutdown

    def task_given(
            self,
            ctd: 'ComputeTaskDef',
            cpu_time_limit: Optional[int] = None
    ) -> None:
        assert not self._new_computer.has_assigned_task()
        assert self._old_computer.can_take_work() or \
            self._old_computer.is_disabled()

        task_id = ctd['task_id']
        task_header = self._task_server.task_keeper.task_headers[task_id]
        if task_header.environment_prerequisites is not None:
            self._new_computer.task_given(task_header, ctd)
        else:
            self._old_computer.task_given(ctd, cpu_time_limit)

    def has_assigned_task(self) -> bool:
        return self._new_computer.has_assigned_task() \
            or self._old_computer.has_assigned_task()

    @property
    def assigned_task_ids(self) -> Set[str]:
        if self._new_computer.has_assigned_task():
            task_id = self._new_computer.assigned_task_id
            if task_id is not None:
                return {task_id}
            return set()
        return self._old_computer.assigned_task_ids

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

    def get_subtask_inputs_dir(self) -> Path:
        if not self._new_computer.has_assigned_task():
            raise ValueError(
                'Task resources directory only available when a task-api task '
                'is assigned')
        return self._new_computer.get_subtask_inputs_dir()

    def compatible_tasks(self, candidate_tasks: Set[str]) -> Set[str]:
        """finds compatible tasks subset"""
        assert not self._new_computer.has_assigned_task()
        return self._old_computer.compatible_tasks(candidate_tasks)

    def start_computation(
            self,
            res_task_id: str,
            res_subtask_id: Optional[str] = None
    ) -> bool:
        if self._new_computer.has_assigned_task():
            task_id = self._new_computer.assigned_task_id
            subtask_id = self._new_computer.assigned_subtask_id
            if task_id != res_task_id:
                logger.error(
                    "Resource collected for a wrong task, %s", res_task_id)
                return False
            computation = self._new_computer.compute()
            self._task_server.task_keeper.task_started(task_id)
            # Fire and forget because it resolves when computation ends
            self._handle_computation_results(task_id, subtask_id, computation)
            return True
        elif self._old_computer.has_assigned_task():
            return self._old_computer.start_computation(
                res_task_id, res_subtask_id)
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
            # Output file is None if computation was cancelled
            if output_file is not None:
                self._task_server.send_results(
                    subtask_id=subtask_id,
                    task_id=task_id,
                    task_api_result=output_file,
                )
            else:
                self._task_server.send_task_failed(
                    subtask_id=subtask_id,
                    task_id=task_id,
                    err_msg="Subtask cancelled",
                    decrease_trust=False
                )
        except Exception as e:  # pylint: disable=broad-except
            self._task_server.send_task_failed(
                subtask_id=subtask_id,
                task_id=task_id,
                err_msg=str(e)
            )
        finally:
            self._task_server.task_keeper.task_ended(task_id)
            self._finished_cb()

    def task_interrupted(self, task_id: str) -> None:
        if self._new_computer.has_assigned_task():
            self._new_computer.task_interrupted()
        elif self._old_computer.has_assigned_task():
            self._old_computer.task_interrupted(task_id)
        else:
            raise RuntimeError('task_interrupted: No task assigned.')

    def can_take_work(self) -> bool:
        if self._old_computer.has_assigned_task():
            return self._old_computer.can_take_work()
        return not self._new_computer.has_assigned_task()

    def check_timeout(self) -> None:
        # No active timeout checking is needed for the new computer
        if self._old_computer.has_assigned_task():
            self._old_computer.check_timeout()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        if self._old_computer.has_assigned_task():
            return self._old_computer.get_progress()
        if self._new_computer.has_assigned_task():
            return self._new_computer.get_progress()
        return None

    def get_environment(self) -> 'Optional[EnvId]':
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
            config_desc: 'ClientConfigDescriptor',
            in_background: bool = True
    ) -> defer.Deferred:
        self._new_computer.change_config(
            config_desc=config_desc)
        return (yield self._old_computer.change_config(
            config_desc=config_desc,
            in_background=in_background))

    def quit(self) -> None:
        self._new_computer.quit()
        self._old_computer.quit()


class NewTaskComputer:
    # pylint: disable=too-many-instance-attributes

    @dataclass
    class AssignedTask:
        task_id: str
        subtask_id: str
        subtask_params: dict
        env_id: 'EnvId'
        prereq_dict: dict
        performance: float
        subtask_timeout: int
        deadline: int

    def __init__(
            self,
            env_manager: 'EnvironmentManager',
            work_dir: Path,
            stats_keeper: Optional[IntStatsKeeper] = None
    ) -> None:
        self._env_manager = env_manager
        self._work_dir = work_dir
        self._stats_keeper = stats_keeper or IntStatsKeeper(CompStats)
        self._assigned_task: Optional[NewTaskComputer.AssignedTask] = None
        self._computation: Optional[defer.Deferred] = None
        self._app_client: Optional[ProviderAppClient] = None
        self._start_time: Optional[float] = None

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

    def get_subtask_inputs_dir(self) -> Path:
        return self._get_task_dir() / task_api_constants.SUBTASK_INPUTS_DIR

    def _is_computing(self) -> bool:
        return self._computation is not None

    def task_given(
            self,
            task_header: 'TaskHeader',
            compute_task_def: 'ComputeTaskDef'
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
        self.get_subtask_inputs_dir().mkdir(parents=True, exist_ok=True)

    def compute(self) -> defer.Deferred:
        assigned_task = self._assigned_task
        assert assigned_task is not None

        self._start_time = time.time()

        compute_future = asyncio.ensure_future(
            self._create_client_and_compute())
        self._computation = deferred_from_future(compute_future)

        # For some reason GRPC future won't get cancelled if timeout is set to
        # zero (or less) seconds so it has to be at least one second.
        timeout = max(1, int(deadline_to_timeout(assigned_task.deadline)))
        from twisted.internet import reactor
        self._computation.addTimeout(timeout, reactor)
        return self._wait_until_computation_ends()

    async def _create_client_and_compute(self) -> Path:
        assigned_task = self._assigned_task
        assert assigned_task is not None

        env_id = assigned_task.env_id
        prereq_dict = assigned_task.prereq_dict

        env = self._env_manager.environment(env_id)
        payload_builder = self._env_manager.payload_builder(env_id)
        prereq = env.parse_prerequisites(prereq_dict)
        shared_dir = self._get_task_dir()

        task_api_service = EnvironmentTaskApiService(
            env=env,
            payload_builder=payload_builder,
            prereq=prereq,
            shared_dir=shared_dir
        )

        self._app_client = await ProviderAppClient.create(task_api_service)
        return await self._app_client.compute(
            task_id=assigned_task.task_id,
            subtask_id=assigned_task.subtask_id,
            subtask_params=assigned_task.subtask_params
        )

    @defer.inlineCallbacks
    def _wait_until_computation_ends(self) -> defer.Deferred:
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
            raise RuntimeError('Task computation timed out')
        except Exception:
            logger.exception(
                'Task computation failed. task_id=%r subtask_id=%r',
                assigned_task.task_id,
                assigned_task.subtask_id
            )
            self._stats_keeper.increase_stat('tasks_with_errors')
            raise
        finally:
            ProviderTimer.finish()
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
            self._computation = None
            self._assigned_task = None
            self._start_time = None
            app_client = self._app_client
            self._app_client = None
            if not success and app_client is not None:
                shutdown_future = asyncio.ensure_future(app_client.shutdown())
                yield deferred_from_future(shutdown_future)

    def _get_task_dir(self) -> Path:
        assert self._assigned_task is not None
        env_id = self._assigned_task.env_id
        task_id = self._assigned_task.task_id
        return self._work_dir / env_id / task_id

    def task_interrupted(self) -> None:
        if self.has_assigned_task() and self._computation:
            self._computation.cancel()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        if not self._is_computing():
            return None
        assert self._assigned_task is not None
        assert self._start_time is not None
        return ComputingSubtaskStateSnapshot(
            subtask_id=self._assigned_task.subtask_id,
            progress=0,
            seconds_to_timeout=deadline_to_timeout(
                self._assigned_task.deadline),
            running_time_seconds=time.time() - self._start_time,
        )

    def get_current_computing_env(self) -> 'Optional[EnvId]':
        if self._assigned_task is None:
            return None
        return self._assigned_task.env_id

    def change_config(
            self,
            config_desc: 'ClientConfigDescriptor',
    ) -> None:
        config_dict = dict(
            work_dirs=[self._work_dir],
            cpu_count=config_desc.num_cores,
            memory_mb=scale_memory(
                config_desc.max_memory_size,
                unit=MemSize.kibi,
                to_unit=MemSize.mebi
            )
        )

        # FIXME: Decide how to properly configure environments
        if self._env_manager.enabled(DOCKER_CPU_ENV_ID):
            docker_cpu = self._env_manager.environment(DOCKER_CPU_ENV_ID)
            docker_cpu.update_config(DockerCPUConfig(**config_dict))

        if self._env_manager.enabled(DOCKER_GPU_ENV_ID):
            docker_gpu = self._env_manager.environment(DOCKER_GPU_ENV_ID)
            # TODO: GPU options in config_dict
            docker_gpu.update_config(DockerGPUConfig(**config_dict))

    def quit(self):
        if self.has_assigned_task():
            self.task_interrupted()


@dataclass
class TaskComputation:
    """Represents single computation in TaskComputer.  There could be only one
    non-single core computation or multiple single-core computations.
    """
    task_computer: 'TaskComputer'
    assigned_subtask: 'ComputeTaskDef'
    counting_thread: Optional[TaskThread] = None
    single_core: bool = False
    cpu_limit: Optional[int] = None

    @property
    def assigned_subtask_id(self) -> str:
        return self.assigned_subtask.get('subtask_id')

    @property
    def assigned_task_id(self) -> str:
        return self.assigned_subtask.get('task_id')

    @property
    def computing(self) -> bool:
        return self.counting_thread is not None

    def check_timeout(self):
        if self.counting_thread is not None:
            self.counting_thread.check_timeout()

    def task_interrupted(self) -> None:
        assert self.assigned_subtask is not None
        self._task_finished()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        out_file_basename = ''
        counting_thread = self.counting_thread
        if counting_thread is None:
            return None
        try:
            out_file_basename = counting_thread.extra_data.get(  # type: ignore
                'crops')[0].get('outfilebasename')
        except (IndexError, KeyError):
            pass
        except TypeError:
            return None

        task_state = ComputingSubtaskStateSnapshot(
            subtask_id=self.assigned_subtask['subtask_id'],
            progress=counting_thread.get_progress(),
            seconds_to_timeout=counting_thread.task_timeout,
            running_time_seconds=(time.time() - counting_thread.start_time),
            outfilebasename=out_file_basename,
            **counting_thread.extra_data,
        )
        return task_state

    def task_computed(self, task_thread: TaskThread) -> None:
        if task_thread.end_time is None:
            task_thread.end_time = time.time()

        task_server = self.task_computer.task_server
        stats = self.task_computer.stats
        work_wall_clock_time = task_thread.end_time - task_thread.start_time
        try:
            subtask = self.assigned_subtask
            assert subtask is not None
            subtask_id = subtask['subtask_id']
            task_id = subtask['task_id']
            task_header = task_server.task_keeper.task_headers[task_id]
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
            reason = TaskFailure.DEFAULT_REASON
            # pylint: disable=unidiomatic-typecheck
            if type(task_thread.error) is TimeoutException:
                stats.increase_stat('tasks_with_timeout')
                reason = TaskFailure.REASON.TimeExceeded
            elif type(task_thread.error) is BudgetExceededException:
                reason = TaskFailure.REASON.BudgetExceeded
            else:
                stats.increase_stat('tasks_with_errors')

            task_server.send_task_failed(
                subtask_id, subtask['task_id'], task_thread.error_msg,
                reason)

        elif task_thread.result and 'data' in task_thread.result:

            logger.info("Task %r computed, work_wall_clock_time %s",
                        subtask_id,
                        str(work_wall_clock_time))
            stats.increase_stat('computed_tasks')

            assert isinstance(task_thread.result, dict)
            try:
                task_server.send_results(
                    subtask_id=subtask_id,
                    task_id=subtask['task_id'],
                    result=task_thread.result['data'],
                    stats=task_thread.stats,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Error sending the results: %r", exc)
            else:
                was_success = True

        else:
            stats.increase_stat('tasks_with_errors')
            task_server.send_task_failed(
                subtask_id,
                subtask['task_id'],
                "Wrong result format",
            )

        dispatcher.send(
            signal='golem.monitor', event='computation_time_spent',
            success=was_success, value=work_time_to_be_paid)
        self._task_finished()

    def _task_finished(self) -> None:
        return self.task_computer.task_finished(self)

    def start_computation(self) -> None:  # pylint: disable=too-many-locals
        subtask = self.assigned_subtask
        assert subtask is not None

        task_id = subtask['task_id']
        subtask_id = subtask['subtask_id']
        docker_images = subtask['docker_images']
        extra_data = subtask['extra_data']
        subtask_deadline = subtask['deadline']

        task_server = self.task_computer.task_server
        task_header = task_server.task_keeper.task_headers.get(task_id)

        if not task_header:
            logger.warning("Subtask '%s' of task '%s' cannot be computed: "
                           "task header has been unexpectedly removed",
                           subtask_id, task_id)
            return

        deadline = min(task_header.deadline, subtask_deadline)
        task_timeout = deadline_to_timeout(deadline)

        unique_str = str(uuid.uuid4())

        logger.info(
            "Starting computation of subtask %r (task: %r, deadline: "
            "%r, docker images: %r, cpu limit: %r)", subtask_id,
            task_id, deadline, docker_images, self.cpu_limit)

        tc = self.task_computer

        with tc.dir_lock:
            resource_dir = tc.dir_manager.get_task_resource_dir(task_id)
            temp_dir = os.path.join(
                tc.dir_manager.get_task_temporary_dir(task_id), unique_str)
            # self.dir_manager.clear_temporary(task_id)

            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

        if docker_images:
            docker_images = [DockerImage(**did) for did in docker_images]
            dir_mapping = DockerTaskThread.generate_dir_mapping(
                resource_dir, temp_dir)
            tt: TaskThread = DockerTaskThread(
                docker_images,
                extra_data,
                dir_mapping,
                task_timeout,
                self.cpu_limit
            )
        elif tc.support_direct_computation:
            tt = PyTaskThread(extra_data, resource_dir, temp_dir,
                              task_timeout)
        else:
            logger.error("Cannot run PyTaskThread in this version")
            task_server.send_task_failed(
                subtask_id,
                self.assigned_subtask['task_id'],
                "Host direct task not supported",
            )

            self._task_finished()
            return

        with tc.lock:
            self.counting_thread = tt

        tc.task_server.task_keeper.task_started(task_id)
        tt.start().addBoth(lambda _: self.task_computed(tt))


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
        self.dir_manager: DirManager = DirManager(
            task_server.get_task_computer_root())

        self.docker_manager: DockerManager = DockerManager.install()
        if use_docker_manager:
            self.docker_manager.check_environment()  # pylint: disable=no-member
        self.use_docker_manager = use_docker_manager

        self.stats = stats_keeper or IntStatsKeeper(CompStats)

        self.assigned_subtasks: List[TaskComputation] = []

        self.support_direct_computation = False
        self.max_num_cores: int = 1
        self.finished_cb = finished_cb

    def _is_single_core_task(self, task_id: str) -> bool:
        task_header = self.task_server.task_keeper.task_headers.get(task_id)
        if task_header is None:
            return False
        return self.task_server.is_task_single_core(task_header)

    def task_given(
            self,
            ctd: 'ComputeTaskDef',
            cpu_time_limit: Optional[int] = None
    ) -> None:
        task_id = ctd.get('task_id')
        single_core = self._is_single_core_task(task_id)
        if not self.assigned_subtasks:
            ProviderTimer.start()

        self.assigned_subtasks.append(
            TaskComputation(
                task_computer=self,
                assigned_subtask=ctd,
                single_core=single_core,
                cpu_limit=cpu_time_limit))

    def has_assigned_task(self) -> bool:
        logger.debug(
            "Has assigned task? assigned_subtasks=%r", self. assigned_subtasks)

        return bool(self.assigned_subtasks)

    @property
    def assigned_task_id(self) -> Optional[str]:
        if not self.assigned_subtasks:
            return None
        return self.assigned_subtasks[0].assigned_task_id

    @property
    def assigned_task_ids(self) -> Set[str]:
        return {c.assigned_task_id for c in self.assigned_subtasks}

    @property
    def assigned_subtask_id(self) -> Optional[str]:
        if not self.assigned_subtasks:
            return None
        return self.assigned_subtasks[0].assigned_subtask_id

    def task_interrupted(
            self,
            task_id: str,
            subtask_id: Optional[str] = None
    ) -> None:
        assert bool(self.assigned_subtasks)
        for computation in self.assigned_subtasks.copy():
            if (subtask_id is None
                    or computation.assigned_subtask_id == subtask_id) \
                    and task_id == computation.assigned_task_id:
                computation.task_interrupted()

    def check_timeout(self):
        for computation in self.assigned_subtasks:
            computation.check_timeout()

    def get_progress(self) -> Optional[ComputingSubtaskStateSnapshot]:
        for computation in self.assigned_subtasks:
            r = computation.get_progress()
            if r is not None:
                return r
        return None

    def _is_computing(self) -> bool:
        with self.lock:
            return any([c for c in self.assigned_subtasks if c.computing])

    def can_take_work(self) -> bool:
        with self.lock:
            if any([
                    computation for computation in self.assigned_subtasks
                    if not computation.single_core
            ]):
                return False
            return len(self.assigned_subtasks) < self.max_num_cores

    def is_disabled(self):
        return self.max_num_cores < 1

    @property
    def free_cores(self) -> int:
        with self.lock:
            if any([
                    computation for computation in self.assigned_subtasks
                    if not computation.single_core
            ]):
                return 0
            n = len(self.assigned_subtasks)
            return self.max_num_cores - n if n < self.max_num_cores else 0

    def get_environment(self):
        task_header_keeper = self.task_server.task_keeper

        task_id = self.assigned_task_id
        if not task_id:
            return None

        task_header = task_header_keeper.task_headers.get(task_id)
        if not task_header:
            return None

        return task_header.environment

    @defer.inlineCallbacks
    def change_config(
            self,
            config_desc: 'ClientConfigDescriptor',
            in_background: bool = True
    ) -> defer.Deferred:

        self.dir_manager = DirManager(self.task_server.get_task_computer_root())

        dm = self.docker_manager
        assert isinstance(dm, DockerManager)
        dm.build_config(config_desc)
        work_dirs = [Path(self.dir_manager.root_path)]
        self.max_num_cores = config_desc.num_cores

        if dm.hypervisor and self.use_docker_manager:  # noqa pylint: disable=no-member
            deferred = defer.Deferred()
            # PyLint thinks dm is of type DockerConfigManager not DockerManager
            # pylint: disable=no-member
            dm.update_config(
                status_callback=self._is_computing,
                done_callback=deferred.callback,
                work_dirs=work_dirs,
                in_background=in_background)
            return (yield deferred)

        return False

    def start_computation(
            self,
            task_id: str,
            subtask_id: Optional[str]
    ) -> bool:
        started = False
        for computation in self.assigned_subtasks:
            if computation.assigned_task_id == task_id and (
                    subtask_id is None or
                    computation.assigned_subtask_id == subtask_id):
                if not computation.computing:
                    started = True
                    computation.start_computation()
                else:
                    logger.warning(
                        "computation already started " +
                        "(task_id=%s, substask_id=%s)", task_id, subtask_id)
        return started

    def task_finished(self, computation: TaskComputation) -> None:
        assert computation in self.assigned_subtasks
        ctd = computation.assigned_subtask
        assert ctd is not None
        self.assigned_subtasks.remove(computation)
        if not self.assigned_subtasks:
            ProviderTimer.finish()
        dispatcher.send(
            signal='golem.taskcomputer',
            event='subtask_finished',
            subtask_id=ctd['subtask_id'],
            min_performance=ctd['performance'],
        )
        with self.lock:
            task_id = ctd['task_id']
            if not [
                    c for c in self.assigned_subtasks
                    if c.assigned_task_id == task_id
            ]:
                self.task_server.task_keeper.task_ended(task_id)

        if self.finished_cb:
            self.finished_cb()

    def compatible_tasks(self, candidate_tasks: Set[str]) -> Set[str]:
        """Finds subset of candidate tasks that can be executed with current
        running tasks.

        :param candidate_tasks:
        :return:
        """
        if not self.assigned_subtasks:
            return candidate_tasks
        tasks = candidate_tasks
        for c in self.assigned_subtasks:
            if not c.single_core:
                return set()
            tasks = tasks - {c.assigned_task_id}
        return {
            task_id for task_id in candidate_tasks
            if self._is_single_core_task(task_id)
        }

    def quit(self):
        for computation in self.assigned_subtasks:
            if computation.counting_thread is not None:
                computation.counting_thread.end_comp()


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
