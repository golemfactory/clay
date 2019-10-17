import asyncio
import hashlib
import logging
import os
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dataclasses import dataclass
from golem_messages import idgenerator
from golem_task_api.dirutils import RequestorDir, RequestorTaskDir
from golem_task_api.enums import VerifyResult
from golem_task_api.client import RequestorAppClient
from peewee import fn, DoesNotExist
from pydispatch import dispatcher

from golem.app_manager import AppManager, AppId
from golem.model import (
    ComputingNode,
    default_now,
    RequestedTask,
    RequestedSubtask,
)
from golem.task import SubtaskId, TaskId
from golem.task.envmanager import EnvironmentManager, EnvId
from golem.task.taskstate import (
    Operation,
    SubtaskOp,
    SubtaskStatus,
    TaskOp,
    TaskStatus,
    TASK_STATUS_ACTIVE,
)
from golem.task.task_api import EnvironmentTaskApiService
from golem.task.timer import ProviderComputeTimers
from golem.task.taskkeeper import compute_subtask_value
from golem.ranking.manager.database_manager import (
    update_provider_efficiency,
    update_provider_efficacy,
)
from golem.task.verification.queue import VerificationQueue

logger = logging.getLogger(__name__)


@dataclass
class CreateTaskParams:
    app_id: str
    name: str
    task_timeout: int
    subtask_timeout: int
    output_directory: Path
    resources: List[Path]
    max_subtasks: int
    max_price_per_hour: int
    concent_enabled: bool


@dataclass
class ComputingNodeDefinition:
    node_id: str
    name: str


@dataclass
class SubtaskDefinition:
    subtask_id: SubtaskId
    resources: List[str]
    params: Dict[str, Any]
    deadline: int


class RequestedTaskManager:

    def __init__(
            self,
            env_manager: EnvironmentManager,
            app_manager: AppManager,
            public_key: bytes,
            root_path: Path,
    ) -> None:
        logger.debug('RequestedTaskManager(public_key=%r, root_path=%r)',
                     public_key, root_path)
        self._root_path = root_path
        self._env_manager = env_manager
        self._app_manager = app_manager
        self._public_key: bytes = public_key
        self._app_clients: Dict[EnvId, RequestorAppClient] = {}
        # Created lazily due to cascading errors in tests
        self._verification_queue: Optional[VerificationQueue] = None

    def _app_dir(self, app_id: AppId) -> RequestorDir:
        app_dir = RequestorDir(self._root_path / app_id)
        app_dir.mkdir(exist_ok=True)
        return app_dir

    def _task_dir(self, task_id: TaskId) -> RequestorTaskDir:
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        return self._app_dir(task.app_id).task_dir(task_id)

    def get_task_inputs_dir(self, task_id: TaskId) -> Path:
        """ Return a path to the directory where task resources should be
            placed. """
        return self._task_dir(task_id).task_inputs_dir

    def get_task_outputs_dir(self, task_id: TaskId) -> Path:
        """ Return a path to the directory where task results should be
            placed. """
        return self._task_dir(task_id).task_outputs_dir

    def get_subtask_inputs_dir(self, task_id: TaskId) -> Path:
        """ Return a path to the directory of the task network resources. """
        return self._task_dir(task_id).subtask_inputs_dir

    def get_subtask_outputs_dir(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId
    ) -> Path:
        """ Return a path to the directory where subtasks outputs should be
            placed. """
        return self._task_dir(task_id).subtask_outputs_dir(subtask_id)

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
            task_id=idgenerator.generate_id(self._public_key),
            app_id=golem_params.app_id,
            name=golem_params.name,
            status=TaskStatus.creating,
            task_timeout=golem_params.task_timeout,
            subtask_timeout=golem_params.subtask_timeout,
            start_time=None,
            max_price_per_hour=golem_params.max_price_per_hour,
            max_subtasks=golem_params.max_subtasks,
            # Concent is explicitly disabled for task_api for now...
            concent_enabled=False,
            # mask = BlobField(null=False, default=masking.Mask().to_bytes()),
            output_directory=golem_params.output_directory,
            app_params=app_params,
        )

        loop = asyncio.get_event_loop()
        loop.call_at(
            loop.time() + golem_params.task_timeout,
            self._check_task_timeout,
            task.task_id,
        )

        logger.debug(
            'create_task(task_id=%r) - prepare directories. app_id=%s',
            task.task_id,
            task.app_id,
        )
        task_dir = self._task_dir(task.task_id)
        task_dir.prepare()
        # Move resources to task_inputs_dir
        logger.debug('create_task(task_id=%r) - copy resources', task.task_id)
        for resource in golem_params.resources:
            shutil.copy2(resource, task_dir.task_inputs_dir)
        logger.info(
            "Created task. id=%s, app=%r",
            task.task_id,
            golem_params.app_id,
        )
        logger.debug('raw_task=%r', task)
        self._notice_task_updated(task, op=TaskOp.CREATED)
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
        # FIXME: Is RTM responsible for managing test tasks?

        app_client = await self._get_app_client(task.app_id)
        logger.debug('init_task(task_id=%r) - creating task', task_id)
        reply = await app_client.create_task(
            task.task_id,
            task.max_subtasks,
            task.app_params,
        )
        task.env_id = reply.env_id
        task.prerequisites = reply.prerequisites
        task.save()
        logger.debug('init_task(task_id=%r) after', task_id)

    def start_task(self, task_id: TaskId) -> None:
        """ Marks an already initialized task as ready for computation. """
        logger.debug('start_task(task_id=%r)', task_id)

        task = RequestedTask.get(RequestedTask.task_id == task_id)

        if not task.status.is_preparing():
            raise RuntimeError(f"Task {task_id} has already been started")

        task.status = TaskStatus.waiting
        task.start_time = default_now()
        task.save()
        self._notice_task_updated(task, op=TaskOp.STARTED)
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
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        return task.status.is_completed()

    async def has_pending_subtasks(self, task_id: TaskId) -> bool:
        """ Return True is there are pending subtasks waiting for
        computation at the given moment. If there are the next call to
        get_next_subtask will return properly defined subtask. It may happen
        that after not having any pending subtasks some will become available
        again, e.g. in case of failed verification a subtask may be marked
        as pending again. """
        logger.debug('has_pending_subtasks(task_id=%r)', task_id)
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        if not task.status.is_active():
            return False
        app_client = await self._get_app_client(task.app_id)
        return await app_client.has_pending_subtasks(task.task_id)

    async def get_next_subtask(
            self,
            task_id: TaskId,
            computing_node: ComputingNodeDefinition
    ) -> Optional[SubtaskDefinition]:
        """ Return a set of data required for subtask computation. """
        logger.debug(
            'get_next_subtask(task_id=%r, computing_node=%r)',
            task_id,
            computing_node
        )
        # Check is my requested task
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        node, _ = ComputingNode.get_or_create(
            node_id=computing_node.node_id,
            defaults={'name': computing_node.name}
        )

        # Check not providing for own task
        if node.node_id == self._public_key:
            raise RuntimeError(f"No subtasks for self. task_id={task_id}")

        # Check should accept provider, raises when waiting on results or banned
        if self._get_unfinished_subtasks_for_node(task_id, node) > 0:
            raise RuntimeError(
                "Provider has unfinished subtasks, no next subtask. "
                f"task_id={task_id}")

        if not await self.has_pending_subtasks(task_id):
            raise RuntimeError(
                f"Task not pending, no next subtask. task_id={task_id}")

        app_client = await self._get_app_client(task.app_id)
        result = await app_client.next_subtask(
            task_id=task.task_id,
            opaque_node_id=hashlib.sha3_256(node.node_id.encode()).hexdigest()  # noqa pylint: disable=no-member
        )

        if result is None:
            logger.info(
                "Application refused to assign subtask to provider node. "
                "task_id=%r, node_id=%r", task_id, node.node_id)
            return None
        subtask_id = result.subtask_id

        subtask = RequestedSubtask.create(
            task=task,
            subtask_id=subtask_id,
            status=SubtaskStatus.starting,
            payload=result.params,
            inputs=list(map(str, result.resources)),
            start_time=default_now(),
            price=task.max_price_per_hour,
            computing_node=node,
        )
        task_deadline = task.deadline
        assert task_deadline is not None, "No deadline, is start_time empty?"
        deadline = min(
            subtask.start_time + timedelta(milliseconds=task.subtask_timeout),
            task_deadline
        )

        self._notice_task_updated(
            task,
            subtask_id=subtask_id,
            op=SubtaskOp.ASSIGNED
        )
        task.status = TaskStatus.computing
        task.save()

        loop = asyncio.get_event_loop()
        loop.call_at(
            loop.time() + task.subtask_timeout,
            self._check_subtask_timeout,
            subtask.task,
            subtask.subtask_id,
        )
        ProviderComputeTimers.start(subtask_id)
        return SubtaskDefinition(
            subtask_id=subtask_id,
            resources=subtask.inputs,
            params=subtask.payload,
            deadline=deadline,
        )

    async def verify(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId
    ) -> VerifyResult:
        if not self._verification_queue:
            self._verification_queue = VerificationQueue(self._verify)
        return await self._verification_queue.put(task_id, subtask_id)

    async def _verify(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId
    ) -> VerifyResult:
        """ Return whether a subtask has been computed correctly. """
        logger.debug('verify(task_id=%r, subtask_id=%r)', task_id, subtask_id)
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        if not task.status.is_active():
            raise RuntimeError(
                f"Task not active, can not verify. task_id={task_id}")
        subtask = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id)
        assert subtask.task == task
        app_client = await self._get_app_client(task.app_id)
        subtask.status = SubtaskStatus.verifying
        subtask.save()
        self._notice_task_updated(
            task,
            subtask_id=subtask_id,
            op=SubtaskOp.VERIFYING
        )
        try:
            result, _ = await app_client.verify(task_id, subtask_id)
        except Exception as e:
            logger.warning(
                "Verification failed. subtask=%s, task=%s, exception=%r",
                subtask_id,
                task_id,
                e
            )
            result, _ = VerifyResult.FAILURE, str(e)

        subtask_op: Optional[SubtaskOp] = None
        if result is VerifyResult.SUCCESS:
            subtask_op = SubtaskOp.FINISHED
            subtask.status = SubtaskStatus.finished
        elif result in (VerifyResult.FAILURE, VerifyResult.INCONCLUSIVE):
            subtask_op = SubtaskOp.FAILED
            subtask.status = SubtaskStatus.failure
        elif result is VerifyResult.AWAITING_DATA:
            subtask_op = None
        else:
            raise NotImplementedError(f"Unexpected verify result: {result}")
        subtask.save()

        if subtask_op:
            self._finish_subtask(subtask, subtask_op)

        if result is VerifyResult.SUCCESS:
            # Check if task completed
            if not await self.has_pending_subtasks(task_id):
                if not self._get_pending_subtasks(task_id):
                    task.status = TaskStatus.finished
                    task.save()
                    self._notice_task_updated(task, op=TaskOp.FINISHED)
                    await self._shutdown_app_client(task.app_id)

        return result

    async def abort_task(self, task_id: TaskId):
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        if not task.status.is_active():
            raise RuntimeError(
                f"Task not active, can not abort. task_id={task_id}")
        task.status = TaskStatus.aborted
        task.save()
        subtasks = self._get_pending_subtasks(task_id)
        for subtask in subtasks:
            subtask.status = SubtaskStatus.cancelled  # type: ignore
            subtask.save()
            self._finish_subtask(subtask, SubtaskOp.ABORTED)

        self._notice_task_updated(task, op=TaskOp.ABORTED)

        await self._shutdown_app_client(task.app_id)

    @staticmethod
    def get_requested_task(task_id: TaskId) -> Optional[RequestedTask]:
        try:
            return RequestedTask.get(RequestedTask.task_id == task_id)
        except RequestedTask.DoesNotExist:
            return None

    @staticmethod
    def get_started_tasks() -> List[RequestedTask]:
        return RequestedTask.select().where(
            RequestedTask.status.in_(TASK_STATUS_ACTIVE),
            RequestedTask.start_time is not None
        ).execute()

    async def restart_task(self, task_id: TaskId) -> None:
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        task.status = TaskStatus.waiting
        task.save()

    async def duplicate_task(self, task_id: TaskId, output_dir: Path) -> TaskId:
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        inputs_dir = self.get_task_inputs_dir(task_id)
        resources = list(map(lambda f: inputs_dir / f, os.listdir(inputs_dir)))
        golem_params = CreateTaskParams(
            app_id=task.app_id,
            name=f'{task.name} copy',
            task_timeout=task.task_timeout,
            subtask_timeout=task.subtask_timeout,
            output_directory=output_dir,
            resources=resources,
            max_subtasks=task.max_subtasks,
            max_price_per_hour=task.max_price_per_hour,
            concent_enabled=task.concent_enabled,
        )
        app_params = task.app_params
        return self.create_task(golem_params, app_params)

    async def discard_subtasks(
            self,
            task_id: TaskId,
            subtask_ids: List[SubtaskId],
    ) -> List[SubtaskId]:
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        app_client = await self._get_app_client(task.app_id)
        for subtask in RequestedSubtask.select().where(
                RequestedSubtask.subtask_id.in_(subtask_ids)):
            assert subtask.task_id == task_id
        discarded_subtask_ids = await app_client.discard_subtasks(
            task_id,
            subtask_ids
        )
        for subtask in RequestedSubtask.select().where(
                RequestedSubtask.subtask_id.in_(discarded_subtask_ids)):
            subtask.status = SubtaskStatus.cancelled
            subtask.save()
        return discarded_subtask_ids

    async def stop(self):
        logger.debug('stop()')
        # Shutdown registered app_clients
        for app_id, app_client in self._app_clients.items():
            logger.info('Shutting down app. app_id=%r', app_id)
            try:
                await app_client.shutdown()
            except Exception:  # pylint: disable=broad-except
                logger.warning("Failed to shutdown app. app_id=%r", app_id)

        self._app_clients.clear()

        logger.debug('stop() - DONE')

    @staticmethod
    def decrease_task_mask(task_id: TaskId, num_bits: int = 1) -> None:
        """ Decrease mask for given task i.e. make it less restrictive """
        logger.debug(
            'decrease_task_mask(task_id=%r, num_bits=%d)',
            task_id,
            num_bits
        )
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        try:
            task.mask.decrease(num_bits)
            task.save()
        except ValueError:
            logger.exception('Wrong number of bits for mask decrease')

    def work_offer_received(self, task_id: TaskId):
        logger.debug('received_work_offer(task_id=%r)', task_id)
        try:
            task = RequestedTask.get(RequestedTask.task_id == task_id)
            self._notice_task_updated(task, op=TaskOp.WORK_OFFER_RECEIVED)
        except DoesNotExist:
            raise RuntimeError(
                f'Can not accept work offer, not my task. task_id={task_id}'
            )

    async def work_offer_canceled(self, task_id: TaskId, subtask_id: SubtaskId):
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id
        )
        assert subtask.task == task
        await self.discard_subtasks(task_id, [subtask_id])
        self._notice_task_updated(
            task,
            subtask_id=subtask_id,
            op=SubtaskOp.FAILED
        )

    def task_result_incoming(self, task_id: TaskId, subtask_id: SubtaskId):
        subtask = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id
        )
        if subtask.status != SubtaskStatus.starting:
            raise RuntimeError(
                "Can not receive results for subtask, expected "
                f"status 'starting' found '{subtask.status}'. "
                f"subtask_id={subtask_id}"
            )
        subtask.status = SubtaskStatus.downloading
        subtask.save()

        self._notice_task_updated(
            subtask.task_id,
            subtask_id=subtask.subtask_id,
            op=SubtaskOp.RESULT_DOWNLOADING
        )

    @staticmethod
    def get_node_id_for_subtask(
            task_id: TaskId,
            subtask_id: SubtaskId,
    ) -> Optional[str]:
        try:
            subtask = RequestedSubtask.get(
                RequestedSubtask.task == task_id,
                RequestedSubtask.subtask_id == subtask_id
            )
            return subtask.computing_node.node_id
        except DoesNotExist:
            return None

    async def _get_app_client(
            self,
            app_id: str,
    ) -> RequestorAppClient:
        if app_id not in self._app_clients:
            logger.info('Creating app_client for app_id=%r', app_id)
            service = self._get_task_api_service(app_id)
            logger.info('Got service for app=%r, service=%r', app_id, service)
            self._app_clients[app_id] = await RequestorAppClient.create(service)
            logger.info(
                'app_client created for app_id=%r, clients=%r',
                app_id, self._app_clients[app_id])
        return self._app_clients[app_id]

    def _get_task_api_service(
            self,
            app_id: str,
    ) -> EnvironmentTaskApiService:
        # FIXME: Stolen from
        # golem/task/taskcomputer.py:_create_client_and_compute()
        logger.info(
            'Creating task_api service for app=%r',
            app_id
        )
        if not self._app_manager.enabled(app_id):
            raise RuntimeError(
                f"Error connecting to app, app not enabled. app={app_id}")
        app = self._app_manager.app(app_id)
        env_id = app.requestor_env
        if not self._env_manager.enabled(env_id):
            raise RuntimeError(
                "Error connecting to app, environment not enabled."
                f" env={env_id}, app={app_id}")
        env = self._env_manager.environment(env_id)
        payload_builder = self._env_manager.payload_builder(env_id)
        prereq = env.parse_prerequisites(app.requestor_prereq)
        shared_dir = self._app_dir(app_id)

        return EnvironmentTaskApiService(
            env=env,
            payload_builder=payload_builder,
            prereq=prereq,
            shared_dir=shared_dir
        )

    def _check_task_timeout(self, task_id: TaskId) -> None:
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        if task.status.is_active():
            logger.info("Task timed out. task_id=%r", task_id)
            task.status = TaskStatus.timeout
            task.save()
            self._notice_task_updated(task, op=TaskOp.TIMEOUT)

    def _check_subtask_timeout(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId
    ) -> None:
        subtask = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id
        )
        if subtask.status.is_active():
            logger.info(
                "Subtask timed out. task_id=%r, subtask_id=%r",
                subtask.task,
                subtask.subtask_id
            )
            # TODO: Add SubtaskStatus.timeout?
            subtask.status = SubtaskStatus.failure
            subtask.save()
            self._finish_subtask(subtask, SubtaskOp.TIMEOUT)

    @staticmethod
    def _get_unfinished_subtasks_for_node(
            task_id: TaskId,
            computing_node: ComputingNode
    ) -> int:
        unfinished_subtask_count = RequestedSubtask.select(
            fn.Count(RequestedSubtask.subtask_id)
        ).where(
            RequestedSubtask.computing_node == computing_node,
            RequestedSubtask.task_id == task_id,
            RequestedSubtask.status != SubtaskStatus.finished,
        ).scalar()
        logger.debug('unfinished subtasks: %r', unfinished_subtask_count)
        return unfinished_subtask_count

    @staticmethod
    def _get_pending_subtasks(task_id: TaskId) -> List[RequestedSubtask]:
        return RequestedSubtask.select().where(
            RequestedSubtask.task_id == task_id,
            # FIXME: duplicate list with SubtaskStatus.is_active()
            RequestedSubtask.status.in_([
                SubtaskStatus.starting,
                SubtaskStatus.downloading,
                SubtaskStatus.verifying,
            ])
        )

    async def _shutdown_app_client(self, app_id) -> None:
        # Check if app completed all tasks
        unfinished_tasks = RequestedTask.select(
            fn.Count(RequestedTask.task_id)
        ).where(
            RequestedTask.app_id == app_id,
            RequestedTask.status.in_(TASK_STATUS_ACTIVE)
        ).scalar()
        logger.debug('unfinished tasks: %r', unfinished_tasks)
        if unfinished_tasks == 0:
            await self._app_clients[app_id].shutdown()
            del self._app_clients[app_id]

    @staticmethod
    def _notice_task_updated(
            db_task: RequestedTask,
            subtask_id: Optional[str] = None,
            op: Optional[Operation] = None,
    ):
        logger.debug(
            "_notice_task_updated(task_id=%s, subtask_id=%s, op=%s)",
            db_task.task_id, subtask_id, op,
        )

        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id=db_task.task_id,
            # FIXME: Fake the old task_state or update monitor for new values
            task_status=db_task.status,
            subtask_id=subtask_id,
            op=op,
        )

    def _finish_subtask(self, subtask: RequestedSubtask, op: SubtaskOp):
        logger.debug('_finish_subtask(subtask=%r, op=%r)', subtask, op)
        subtask_id = subtask.subtask_id
        ProviderComputeTimers.finish(subtask_id)
        self._notice_task_updated(subtask.task, subtask_id=subtask_id, op=op)
        node_id = subtask.computing_node.node_id
        subtask_timeout = subtask.task.subtask_timeout
        raw_time = ProviderComputeTimers.time(subtask_id)
        if raw_time is None:
            logger.warning(
                'Empty compute timer, can not update monitor and LocalRank'
            )
            return
        comp_time = int(round(raw_time))
        comp_price = compute_subtask_value(
            subtask.task.max_price_per_hour,
            comp_time
        )
        update_provider_efficacy(node_id, op)
        if subtask_timeout is not None:
            update_provider_efficiency(node_id, subtask_timeout, comp_time)
            dispatcher.send(
                signal='golem.subtask',
                event='finished',
                timed_out=(op == SubtaskOp.TIMEOUT),
                subtask_count=subtask.task.max_subtasks,
                subtask_timeout=subtask_timeout,
                subtask_price=comp_price,
                subtask_computation_time=comp_time,
            )
        ProviderComputeTimers.remove(subtask_id)
