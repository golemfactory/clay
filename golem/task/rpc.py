"""Task related module with procedures exposed by RPC"""

import copy
import functools
import logging
import os.path
import re
import typing
import warnings

from ethereum.utils import denoms
from golem_messages import helpers as msg_helpers
from twisted.internet import defer

from apps.core.task import coretask
from apps.rendering.task import framerenderingtask
from golem.core import golem_async
from golem.core import common
from golem.core import deferred as golem_deferred
from golem.core import simpleserializer
from golem.ethereum import exceptions as eth_exceptions
from golem.resource import resource
from golem.rpc import utils as rpc_utils
from golem.task import masking
from golem.task import taskbase
from golem.task import taskstate
from golem.task import tasktester


logger = logging.getLogger(__name__)
TASK_NAME_RE = re.compile(r"(\w|[\-\. ])+$")


def safe_run(errback):
    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
            except Exception as e:  # pylint: disable=broad-except
                logger.debug('Full traceback', exc_info=e)
                return errback(e, *args, **kwargs)
            return result
        return curry
    return wrapped


class CreateTaskError(Exception):
    pass


def _validate_task_dict(client, task_dict) -> None:
    name = ""
    if 'name' in task_dict:
        task_dict['name'] = task_dict['name'].strip()
        name = task_dict['name']
    if len(name) < 4 or len(name) > 24:
        raise ValueError(
            "Length of task name cannot be less "
            "than 4 or more than 24 characters.")
    if not TASK_NAME_RE.match(name):
        raise ValueError(
            "Task name can only contain letters, numbers, "
            "spaces, underline, dash or dot.")
    if 'id' in task_dict:
        logger.warning("discarding the UUID from the preset")
        del task_dict['id']

    subtasks_count = task_dict.get('subtasks_count', 0)
    options = task_dict.get('options', {})
    optimize_total = bool(options.get('optimize_total', False))
    if subtasks_count and not optimize_total:
        computed_subtasks = framerenderingtask.calculate_subtasks_count(
            subtasks_count=subtasks_count,
            optimize_total=False,
            use_frames=options.get('frame_count', 1) > 1,
            frames=[None]*options.get('frame_count', 1),
        )
        if computed_subtasks != subtasks_count:
            raise ValueError(
                "Subtasks count {:d} is invalid."
                " Maybe use {:d} instead?".format(
                    subtasks_count,
                    computed_subtasks,
                )
            )

    if task_dict['concent_enabled'] and \
            not client.concent_service.enabled:
        raise CreateTaskError(
            "Cannot create task with concent enabled when "
            "concent service is disabled")


def prepare_and_validate_task_dict(client, task_dict):
    # Set default value for concent_enabled
    task_dict.setdefault(
        'concent_enabled',
        client.concent_service.enabled,
    )
    # TODO #3474
    if 'subtasks' in task_dict:
        logger.warning(
            "Using soon to be deprecated data format for input JSON."
            " Change `subtasks` to `subtasks_count`",
        )
        task_dict['subtasks_count'] = task_dict.pop('subtasks')
    _validate_task_dict(client, task_dict)


@golem_async.deferred_run()
def _run_test_task(client, task_dict):

    def on_success(result, estimated_memory, time_spent, **kwargs):
        logger.info('Test task succes "%r"', task_dict)
        client.task_tester = None
        client.task_test_result = {
            "status": taskstate.TaskTestStatus.success,
            "result": result,
            "estimated_memory": estimated_memory,
            "time_spent": time_spent,
            "more": kwargs,
        }

    def on_error(*args, **kwargs):
        logger.warning('Test task error "%r": %r', task_dict, args)
        client.task_tester = None
        client.task_test_result = {
            "status": taskstate.TaskTestStatus.error,
            "error": args,
            "more": kwargs,
        }

    dictionary = simpleserializer.DictSerializer.load(task_dict)
    task = client.task_server.task_manager.create_task(
        dictionary=dictionary, minimal=True
    )

    client.task_test_result = {
        "status": taskstate.TaskTestStatus.started,
        "error": None,
    }
    client.task_tester = tasktester.TaskTester(
        task,
        client.datadir,
        on_success,
        on_error,
    )
    client.task_tester.run()


@golem_async.deferred_run()
def _restart_subtasks(
        client,
        old_task_id,
        task_dict,
        subtask_ids_to_copy,
        force,
):
    @defer.inlineCallbacks
    @safe_run(
        lambda e: logger.error(
            'Restarting subtasks_failed. task_dict=%r, subtask_ids_to_copy=%r',
            task_dict,
            subtask_ids_to_copy,
        ),
    )
    def deferred():
        new_task = yield enqueue_new_task(
            client=client,
            task=client.task_manager.create_task(task_dict),
            force=force,
        )

        client.task_manager.copy_results(
            old_task_id=old_task_id,
            new_task_id=new_task.header.task_id,
            subtask_ids_to_copy=subtask_ids_to_copy
        )
    # Function passed to twisted.threads.deferToThread can't itself
    # return a deferred, that's why I defined inner deferred function
    # and use sync_wait below.
    golem_deferred.sync_wait(deferred())


@defer.inlineCallbacks
def _ensure_task_deposit(client, task, force):
    if not client.concent_service.enabled:
        return

    task_id = task.header.task_id
    min_amount, opt_amount = msg_helpers.requestor_deposit_amount(
        task.price,
    )
    logger.info(
        "Ensuring deposit. min=%.8f optimal=%.8f task_id=%r",
        min_amount / denoms.ether,
        opt_amount / denoms.ether,
        task_id,
    )
    # This is a bandaid solution for unlocking funds when task creation
    # fails. This case is most common but, the better way it to always
    # unlock them when the task fails regardless of the reason.
    try:
        yield client.transaction_system.concent_deposit(
            required=min_amount,
            expected=opt_amount,
            force=force,
        )
    except eth_exceptions.EthereumError:
        client.funds_locker.remove_task(task_id)
        raise


@defer.inlineCallbacks
def _create_task_package(client, task):
    files = resource.get_resources_for_task(
        resource_header=None,
        resource_type=resource.ResourceType.HASHES,
        tmp_dir=getattr(task, 'tmp_dir', None),
        resources=task.get_resources(),
    )

    packager_result = yield client.resource_server.create_resource_package(
        files,
        task.header.task_id,
    )
    return packager_result


def _get_mask_for_task(client, task: coretask.CoreTask) -> masking.Mask:
    desired_num_workers = max(
        task.get_total_tasks() * client.config_desc.initial_mask_size_factor,
        client.config_desc.min_num_workers_for_mask,
    )

    if client.p2pservice is None:
        raise RuntimeError('P2PService not ready')
    if client.task_server is None:
        raise RuntimeError('TaskServer not ready')

    network_size = client.p2pservice.get_estimated_network_size()
    min_perf = client.task_server.get_min_performance_for_task(task)
    perf_rank = client.p2pservice.get_performance_percentile_rank(
        min_perf, task.header.environment)
    potential_num_workers = int(network_size * (1 - perf_rank))

    mask = masking.Mask.get_mask_for_task(
        desired_num_workers=desired_num_workers,
        potential_num_workers=potential_num_workers
    )
    logger.info(
        f'Task {task.header.task_id} '
        f'initial mask size: {mask.num_bits} '
        f'expected number of providers: {desired_num_workers} '
        f'potential number of providers: {potential_num_workers}'
    )

    return mask


@defer.inlineCallbacks
def _inform_subsystems(client, task, packager_result):
    task_id = task.header.task_id
    package_path, package_sha1 = packager_result
    task.header.resource_size = os.path.getsize(package_path)

    if client.config_desc.net_masking_enabled:
        task.header.mask = _get_mask_for_task(
            client=client,
            task=task,
        )
    else:
        task.header.mask = masking.Mask()

    estimated_fee = client.transaction_system.eth_for_batch_payment(
        task.get_total_tasks())
    client.task_manager.add_new_task(task, estimated_fee=estimated_fee)

    client_options = client.task_server.get_share_options(task_id, None)
    client_options.timeout = common.deadline_to_timeout(
        task.header.deadline,
    )

    resource_server_result = yield client.resource_server.add_task(
        package_path,
        package_sha1,
        task_id,
        task.header.resource_size,
        client_options=client_options,
    )
    return resource_server_result


@golem_async.deferred_run()
def _start_task(client, task, resource_server_result):
    resource_manager_result, package_path,\
        package_hash, package_size = resource_server_result

    task_state = client.task_manager.tasks_states[task.header.task_id]
    task_state.package_path = package_path
    task_state.package_hash = package_hash
    task_state.package_size = package_size
    task_state.resource_hash = resource_manager_result[0]
    logger.debug(
        "Setting task state - package_path: %s, package_hash: %s, "
        "package_size: %s, resource_hash: %s",
        task_state.package_path, task_state.package_hash,
        task_state.package_size, task_state.resource_hash
    )

    client.task_manager.start_task(task.header.task_id)


@defer.inlineCallbacks
def enqueue_new_task(client, task, force=False) \
            -> typing.Generator[defer.Deferred, typing.Any, taskbase.Task]:
    """Feed a fresh Task to all golem subsystems"""
    if client.config_desc.in_shutdown:
        raise CreateTaskError(
            'Can not enqueue task: shutdown is in progress, '
            'toggle shutdown mode off to create a new tasks.')
    if client.task_server is None:
        raise CreateTaskError("Golem is not ready")

    task_id = task.header.task_id
    client.funds_locker.lock_funds(
        task_id,
        task.subtask_price,
        task.get_total_tasks(),
        task.header.deadline,
    )
    logger.info('Enqueue new task %r', task)

    yield _ensure_task_deposit(
        client=client,
        task=task,
        force=force,
    )

    logger.info(
        "Deposit confirmed. Creating resource package. task_id=%r",
        task_id,
    )

    packager_result = yield _create_task_package(
        client=client,
        task=task,
    )

    logger.info(
        "Resource package created. Informing subsystems. task_id=%r",
        task_id,
    )

    resource_server_result = yield _inform_subsystems(
        client=client,
        task=task,
        packager_result=packager_result,
    )

    logger.info("Task created. Starting... task_id=%r", task_id)

    yield _start_task(
        client=client,
        task=task,
        resource_server_result=resource_server_result,
    )

    logger.info("Task enqueued. task_id=%r", task_id)
    return task


def _create_task_error(e, _self, task_dict, **kwargs):
    logger.error("Cannot create task %r: %s", task_dict, e)
    return None, str(e)


def _restart_task_error(e, _self, task_id, **kwargs):
    logger.error("Cannot restart task %r: %s", task_id, e)
    return None, str(e)


def _test_task_error(e, self, task_dict, **kwargs):
    logger.error("Test task error: %s", e)
    logger.debug("Test task details. task_dict=%s", task_dict)
    self.client.task_test_result = {
        "status": taskstate.TaskTestStatus.error,
        "error": str(e),
    }
    return False


class ClientProvider:
    """Provides task related remote procedures that require Client"""

    # Add only methods that are exposed via RPC
    def __init__(self, client):
        self.client = client

    @property
    def task_manager(self):
        return self.client.task_server.task_manager

    @rpc_utils.expose('comp.task.create')
    @safe_run(_create_task_error)
    def create_task(self, task_dict, force=False) \
            -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
        """
        - force: if True will ignore warnings
        :return: (task_id, None) on success; (task_id or None, error_message)
                 on failure
        """

        # FIXME: Statement only for old DummyTask compatibility #2467
        task: taskbase.Task
        if isinstance(task_dict, taskbase.Task):
            warnings.warn(
                "create_task() called with {got_type}"
                " instead of dict #2467".format(
                    got_type=type(task_dict),
                ),
                DeprecationWarning,
                stacklevel=2,
            )
            task = task_dict
        else:
            prepare_and_validate_task_dict(self.client, task_dict)

            task = self.task_manager.create_task(task_dict)

        task_id = task.header.task_id

        deferred = enqueue_new_task(self.client, task, force=force)
        # We want to return quickly from create_task without waiting for
        # deferred completion.
        deferred.addErrback(  # pylint: disable=no-member
            lambda failure: _create_task_error(
                e=failure.value,
                _self=self,
                task_dict=task_dict,
                force=force
            ),
        )
        return task_id, None

    @rpc_utils.expose('comp.task.restart')
    @safe_run(_restart_task_error)
    def restart_task(self, task_id: str, force: bool = False) \
            -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
        """
        :return: (new_task_id, None) on success; (None, error_message)
                 on failure
        """
        logger.info('Restarting task. task_id=%r', task_id)

        # Task state is changed to restarted and stays this way until it's
        # deleted from task manager.
        try:
            self.task_manager.assert_task_can_be_restarted(task_id)
        except self.task_manager.AlreadyRestartedError:
            return None, "Task already restarted: '{}'".format(task_id)

        # Create new task that is a copy of the definition of the old one.
        # It has a new deadline and a new task id.
        try:
            task_dict = copy.deepcopy(
                self.task_manager.get_task_definition_dict(
                    self.task_manager.tasks[task_id],
                ),
            )
        except KeyError:
            return None, "Task not found: '{}'".format(task_id)

        task_dict.pop('id', None)
        prepare_and_validate_task_dict(self.client, task_dict)
        new_task = self.task_manager.create_task(task_dict)
        enqueue_new_task(  # pylint: disable=no-member
            client=self.client,
            task=new_task,
            force=force,
        ).addErrback(
            lambda failure: _restart_task_error(
                e=failure.value,
                _self=self,
                task_id=task_id,
            ),
        )
        self.task_manager.put_task_in_restarted_state(task_id)
        return new_task.header.task_id, None

    @rpc_utils.expose('comp.task.restart_subtasks')
    @safe_run(
        lambda e, _self, task_id, subtask_ids: logger.error(
            'Task restart failed. e=%s, task_id=%s subtask_ids=%s',
            e,
            task_id,
            subtask_ids,
        ),
    )
    def restart_subtasks_from_task(
            self,
            task_id: str,
            subtask_ids: typing.Iterable[str],
            force: bool = False,
    ):

        try:
            self.task_manager.put_task_in_restarted_state(
                task_id,
                clear_tmp=False,
            )
            old_task = self.task_manager.tasks[task_id]
            finished_subtask_ids = set(
                sub_id for sub_id, sub in old_task.subtasks_given.items()
                if sub['status'] == taskstate.SubtaskStatus.finished
            )
            subtask_ids_to_copy = finished_subtask_ids - set(subtask_ids)
        except self.task_manager.AlreadyRestartedError:
            logger.error('Task already restarted: %r', task_id)
            return
        except KeyError:
            logger.error('Task not found: %r', task_id)
            return

        task_dict = copy.deepcopy(
            self.task_manager.get_task_definition_dict(old_task),
        )
        del task_dict['id']
        logger.debug('Restarting task. task_dict=%s', task_dict)
        prepare_and_validate_task_dict(self.client, task_dict)
        _restart_subtasks(
            client=self.client,
            subtask_ids_to_copy=subtask_ids_to_copy,
            old_task_id=task_id,
            task_dict=task_dict,
            force=force,
        )
        # Don't wait for deferred

    @rpc_utils.expose('comp.tasks.check')
    @safe_run(_test_task_error)
    def run_test_task(self, task_dict) -> bool:
        logger.info('Running test task "%r" ...', task_dict)
        if self.client.task_tester is not None:
            self.client.task_test_result = {
                "status": taskstate.TaskTestStatus.error,
                "error": "Another test is running",
            }
            return False

        self.client.task_test_result = None
        prepare_and_validate_task_dict(self.client, task_dict)
        _run_test_task(
            client=self.client,
            task_dict=task_dict,
        )
        # Don't wait for _deferred
        return True
