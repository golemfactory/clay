import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List

from dataclasses import dataclass, asdict
from golem_task_api.client import RequestorAppClient
from peewee import fn
from twisted.internet.defer import Deferred, succeed

from apps.core.task.coretask import CoreTask
from golem.core.deferred import deferred_from_future
from golem.model import (
    ComputingNode,
    default_now,
    RequestedTask,
    RequestedSubtask,
)
from golem.resource.dirmanager import DirManager
from golem.task.envmanager import EnvironmentManager, EnvId
from golem.task.taskstate import TaskStatus, SubtaskStatus
from golem.task.task_api import EnvironmentTaskApiService

logger = logging.getLogger(__name__)

TaskId = str
SubtaskId = str


@dataclass
class CreateTaskParams:
    app_id: str
    name: str
    environment: str
    task_timeout: int
    subtask_timeout: int
    output_directory: Path
    resources: List[Path]
    max_subtasks: int
    max_price_per_hour: int
    concent_enabled: bool


@dataclass
class SubtaskDefinition:
    subtask_id: SubtaskId
    resources: List[str]
    params: Dict[str, Any]
    deadline: int


class RequestedTaskManager:
    def __init__(self, env_manager: EnvironmentManager, public_key, root_path):
        logger.debug('RequestedTaskManager(public_key=%r, root_path=%r)',
                     public_key, root_path)
        self._dir_manager = DirManager(root_path)
        self._env_manager = env_manager
        self._public_key: bytes = public_key
        self._app_clients: Dict[EnvId, RequestorAppClient] = {}

    def create_task(
            self,
            golem_params: CreateTaskParams,
            app_params: Dict[str, Any],
    ) -> TaskId:
        """ Creates an entry in the storage about the new task and assigns
        the task_id to it. The task then has to be initialized and started. """
        logger.debug('create_task(golem_params=%r, app_params=%r)',
                     golem_params, app_params)

        task = RequestedTask.create(
            task_id=CoreTask.create_task_id(self._public_key),
            app_id=golem_params.app_id,
            name=golem_params.name,
            status=TaskStatus.creating,
            environment=golem_params.environment,
            # prerequisites='{}',
            task_timeout=golem_params.task_timeout,
            subtask_timeout=golem_params.subtask_timeout,
            start_time=default_now(),
            max_price_per_hour=golem_params.max_price_per_hour,
            max_subtasks=golem_params.max_subtasks,
            # concent_enabled = BooleanField(null=False, default=False),
            # mask = BlobField(null=False, default=masking.Mask().to_bytes()),
            output_directory=golem_params.output_directory,
            # FIXME: Where to move resources?
            resources=golem_params.resources,
            # FIXME: add app_params?
            app_params=app_params,
        )

        logger.info(
            "Creating task. id=%s, app=%r, env=%r",
            task.task_id,
            golem_params.app_id,
            golem_params.environment,
        )
        logger.debug('raw_task=%r', task)
        return task.task_id

    async def init_task(self, task_id: TaskId) -> None:
        """ Initialize the task by calling create_task on the Task API.
        The application performs validation of the params which may result in
        an error marking the task as failed. """
        logger.debug('init_task(task_id=%r)', task_id)

        task = RequestedTask.get(RequestedTask.task_id == task_id)

        if task.status != TaskStatus.creating:
            raise RuntimeError(f"Task {task_id} has already been initialized")

        # FIXME: Blender creates preview files here

        self._dir_manager.clear_temporary(task_id)
        work_dir = self._dir_manager.get_task_temporary_dir(task_id)

        # FIXME: Is RTM responsible for managing test tasks?

        task_params = CreateTaskParams(
            app_id=task.app_id,
            name=task.name,
            environment=task.environment,
            task_timeout=task.task_timeout,
            subtask_timeout=task.subtask_timeout,
            output_directory=task.output_directory,
            resources=task.resources,
            # FIXME: This is a separate argument now, delete here?
            max_subtasks=task.max_subtasks,
            max_price_per_hour=task.max_price_per_hour,
            concent_enabled=task.concent_enabled,
        )
        app_client = await self._get_app_client(task.environment)
        logger.debug('init_task(task_id=%r) before creating task', task_id)
        await app_client.create_task(
            task.task_id,
            task.max_subtasks,
            asdict(task_params),
        )
        logger.debug('init_task(task_id=%r) after', task_id)

    def start_task(self, task_id: TaskId) -> None:
        """ Marks an already initialized task as ready for computation. """
        logger.debug('start_task(task_id=%r)', task_id)

        task = RequestedTask.get(RequestedTask.task_id == task_id)

        if not task.status.is_preparing():
            raise RuntimeError(f"Task {task_id} has already been started")

        task.status = TaskStatus.waiting
        task.save()
        # FIXME: add self.notice_task_updated(task_id, op=TaskOp.STARTED)
        logger.info("Task %s started", task_id)

    @staticmethod
    def task_exists(task_id: TaskId) -> bool:
        """ Return whether task of a given task_id exists. """
        logger.debug('task_exists(task_id=%r)', task_id)
        result = RequestedTask.select(RequestedTask.task_id) \
            .where(RequestedTask.task_id == task_id).exists()
        return result

    @staticmethod
    def is_task_finished(task_id: TaskId) -> bool:
        """ Return True if there is no more computation needed for this
        task because the task has finished, e.g. completed successfully, timed
        out, aborted, etc. """
        logger.debug('is_task_finished(task_id=%r)', task_id)
        task = RequestedTask.get(task_id)
        return task.status.is_completed()

    def get_task_network_resources_dir(self, task_id: TaskId) -> Path:
        """ Return a path to the directory of the task network resources. """
        return Path(self._dir_manager.get_task_resource_dir(task_id))

    def get_subtasks_outputs_dir(self, task_id: TaskId) -> Path:
        """ Return a path to the directory where subtasks outputs should be
        placed. """
        return Path(self._dir_manager.get_task_output_dir(task_id))

    async def has_pending_subtasks(self, task_id: TaskId) -> bool:
        """ Return True is there are pending subtasks waiting for
        computation at the given moment. If there are the next call to
        get_next_subtask will return properly defined subtask. It may happen
        that after not having any pending subtasks some will become available
        again, e.g. in case of failed verification a subtask may be marked
        as pending again. """
        logger.debug('has_pending_subtasks(task_id=%r)', task_id)
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        app_client = await self._get_app_client(task.app_id)
        return await app_client.has_pending_subtasks(task.task_id)

    async def get_next_subtask(
            self,
            task_id: TaskId,
            computing_node: ComputingNode
    ) -> SubtaskDefinition:
        """ Return a set of data required for subtask computation. """
        logger.debug(
            'get_next_subtask(task_id=%r, computing_node=%r)',
            task_id,
            computing_node
        )
        task = RequestedTask.get(RequestedTask.task_id == task_id)

        if not task.status.is_active():
            raise RuntimeError(
                f"Task not active, can not get_next_subtask. task_id={task_id}")
        app_client = await self._get_app_client(task.environment)
        result = await app_client.next_subtask(task.task_id)
        subtask = RequestedSubtask.create(
            task=task,
            subtask_id=result.subtask_id,
            status=SubtaskStatus.starting,
            # payload='{}',
            # inputs='[]',
            start_time=default_now(),
            price=task.max_price_per_hour,
            computing_node=computing_node,
        )
        return subtask

    async def verify(self, task_id: TaskId, subtask_id: SubtaskId) -> bool:
        """ Return whether a subtask has been computed corectly. """
        logger.debug('verify(task_id=%r, subtask_id=%r)', task_id, subtask_id)
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        if not task.status.is_active():
            raise RuntimeError(
                f"Task not active, can not verify. task_id={task_id}")
        subtask = RequestedSubtask.get(
            RequestedSubtask.subtask_id == subtask_id)
        # FIXME, check if subtask_id belongs to task
        assert subtask.task == task
        app_client = await self._get_app_client(task.app_id)
        subtask.status = SubtaskStatus.verifying
        subtask.save()
        result = await app_client.verify(task.task_id, subtask_id)
        if result:
            subtask.status = SubtaskStatus.finished
            finished_subtasks = RequestedSubtask.select(
                fn.Count(RequestedSubtask.subtask_id)
            ).where(
                RequestedSubtask.task == task
                and RequestedSubtask.status == SubtaskStatus.finished
            )
            if finished_subtasks >= task.max_subtasks:
                task.status = TaskStatus.finished
                task.save()
        else:
            subtask.status = SubtaskStatus.failure
        subtask.save()
        return result

    def quit(self) -> Deferred:
        # FIXME: make async not Deferred?
        logger.debug('quit() clients=%r', self._app_clients)
        if not self._app_clients:
            logger.debug('No clients to clean up')
            return succeed(None)
        shutdown_futures = [
            app.shutdown() for app in self._app_clients.values()
        ]
        logger.debug('quit() futures=%r', shutdown_futures)
        # FIXME: error when running in another thread.
        # this fixes it, but is it the right way?
        try:
            asyncio.get_event_loop()
        except Exception:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(asyncio.wait(shutdown_futures))
        deferred = deferred_from_future(future)
        logger.debug('quit() deferred=%r', deferred)
        return deferred

    async def _get_app_client(self, env_id: EnvId) -> RequestorAppClient:
        if env_id not in self._app_clients:
            logger.info('Creating app_client for env_id=%r', env_id)
            service = self._get_task_api_service(env_id)
            logger.info('Got service for env=%r, service=%r', env_id, service)
            self._app_clients[env_id] = await RequestorAppClient.create(service)
            logger.info(
                'app_client created for env_id=%r, clients=%r',
                env_id, self._app_clients[env_id])
        return self._app_clients[env_id]

    def _get_task_api_service(self, env_id: EnvId) -> EnvironmentTaskApiService:
        # FIXME: Stolen from golem/task/taskcomputer.py:_get_task_api_service()
        logger.info('Creating task_api service for env=%r', env_id)
        if not self._env_manager.enabled(env_id):
            raise RuntimeError(
                f"Error connecting to app: {env_id}. environment not enabled")
        env = self._env_manager.environment(env_id)
        payload_builder = self._env_manager.payload_builder(env_id)
        prereq = env.parse_prerequisites({"image": "blenderapp", "tag": "latest"})
        shared_dir = self._dir_manager.root_path

        return EnvironmentTaskApiService(
            env=env,
            payload_builder=payload_builder,
            prereq=prereq,
            shared_dir=shared_dir
        )
