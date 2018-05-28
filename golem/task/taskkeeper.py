import logging
import pathlib
import pickle
import time
import typing

import random
from collections import Counter

from golem_messages import message, helpers
from golem_messages.constants import MTD
from semantic_version import Version

import golem
from golem.core import common
from golem.core.async import AsyncRequest, async_run
from golem.core.idgenerator import check_id_seed
from golem.core.variables import NUM_OF_RES_TRANSFERS_NEEDED_FOR_VER
from golem.environments.environment import SupportStatus, UnsupportReason
from golem.utils import decode_hex
from .taskbase import TaskHeader

logger = logging.getLogger('golem.task.taskkeeper')


def compute_subtask_value(price: int, computation_time: int):
    """
    Don't use math.ceil (this is general advice, not specific to the case here)
    >>> math.ceil(10 ** 18 / 6)
    166666666666666656
    >>> (10 ** 18 + 5) // 6
    166666666666666667
    """
    return (price * computation_time + 3599) // 3600


def comp_task_info_keeping_timeout(subtask_timeout: int, resource_size: int,
                                   num_of_res_transfers_needed: int =
                                   NUM_OF_RES_TRANSFERS_NEEDED_FOR_VER):
    verification_timeout = subtask_timeout
    resource_timeout = helpers.maximum_download_time(resource_size).seconds
    resource_timeout *= num_of_res_transfers_needed
    return common.timeout_to_deadline(subtask_timeout + verification_timeout
                                      + resource_timeout)


class WrongOwnerException(Exception):
    pass


class CompTaskInfo:
    def __init__(self, header: TaskHeader, price: int):
        self.header = header
        self._price, self.subtask_price = 0, 0  # lints and typing
        self.price = price
        self.requests = 1
        self.subtasks = {}
        # TODO Add concent communication timeout. Issue #2406
        self.keeping_deadline = comp_task_info_keeping_timeout(
            self.header.subtask_timeout, self.header.resource_size)

    @property
    def price(self) -> int:
        return self._price

    @price.setter
    def price(self, value: int):
        self._price = value
        # subtask_price is total amount that will be payed
        # for subtask of this task
        self.subtask_price = compute_subtask_value(
            value,
            self.header.subtask_timeout,
        )

    def __repr__(self):
        return "<CompTaskInfo(%r, %r) reqs: %r>" % (
            self.header,
            self.price,
            self.requests
        )

    def check_deadline(self, deadline: float) -> bool:
        """
        Checks if subtask deadline defined in newly received ComputeTaskDef
        is properly set, ie. it's set to future date, but not much further than
        it was declared in subtask timeout.
        :param float deadline: subtask deadline
        :return bool:
        """
        now_ = common.get_timestamp_utc()
        expected_deadline = now_ + self.header.subtask_timeout
        if now_ < deadline < expected_deadline + MTD.seconds:
            return True
        logger.debug('check_deadline failed: (now: %r, deadline: %r, '
                     'timeout: %r)', now_, deadline,
                     self.header.subtask_timeout)
        return False


class CompSubtaskInfo:
    def __init__(self, subtask_id):
        self.subtask_id = subtask_id


def log_key_error(*args, **_):
    if isinstance(args[1], message.ComputeTaskDef):
        task_id = args[1]['task_id']
    else:
        task_id = args[1]
    logger.warning("This is not my task {}".format(task_id))
    return None


class CompTaskKeeper:
    """Keeps information about subtasks that should be computed by this node.
    """

    handle_key_error = common.HandleKeyError(log_key_error)

    def __init__(self, tasks_path: pathlib.Path, persist=True):
        """ Create new instance of compuatational task's definition's keeper

        tasks_path: to tasks directory
        """
        # information about tasks that this node wants to compute
        self.active_tasks: typing.Dict[str, CompTaskInfo] = {}
        # maps subtasks id to tasks id
        self.subtask_to_task: typing.Dict[str, str] = {}
        if not tasks_path.is_dir():
            tasks_path.mkdir()
        self.dump_path = tasks_path / "comp_task_keeper.pickle"
        self.persist = persist
        self.restore()

    def dump(self):
        if not self.persist:
            return
        async_run(AsyncRequest(self._dump_tasks))

    def _dump_tasks(self):
        logger.debug('COMPTASK DUMP: %s', self.dump_path)
        with self.dump_path.open('wb') as f:
            dump_data = self.active_tasks, self.subtask_to_task
            pickle.dump(dump_data, f)

    def restore(self):
        if not self.persist:
            return
        logger.debug('COMPTASK RESTORE: %s', self.dump_path)
        if not self.dump_path.exists():
            logger.debug('No previous comptask dump found.')
            return
        with self.dump_path.open('rb') as f:
            try:
                active_tasks, subtask_to_task = pickle.load(f)
            except (pickle.UnpicklingError, EOFError, AttributeError, KeyError):
                logger.exception(
                    'Problem restoring dumpfile: %s',
                    self.dump_path
                )
                return
        self.active_tasks.update(active_tasks)
        self.subtask_to_task.update(subtask_to_task)

    def add_request(self, theader: TaskHeader, price: int):
        # price is task_header.max_price
        logger.debug('CT.add_request()')
        if price < 0:
            raise ValueError("Price should be greater or equal zero")
        task_id = theader.task_id
        if task_id in self.active_tasks:
            self.active_tasks[task_id].requests += 1
        else:
            self.active_tasks[task_id] = CompTaskInfo(theader, price)
        self.dump()

    @handle_key_error
    def get_task_env(self, task_id):
        return self.active_tasks[task_id].header.environment

    @handle_key_error
    def get_task_header(self, task_id):
        return self.active_tasks[task_id].header

    @handle_key_error
    def receive_subtask(self, task_to_compute: message.TaskToCompute):
        comp_task_def = task_to_compute.compute_task_def
        logger.debug('CT.receive_subtask()')
        if not self.check_comp_task_def(comp_task_def):
            return False
        comp_task_info: CompTaskInfo = self.active_tasks[
            task_to_compute.task_id
        ]
        if task_to_compute.price != comp_task_info.subtask_price:
            logger.info(
                "Can't accept subtask %r for %r."
                " %r<TTC.price> != %r<CTI.subtask_price>",
                task_to_compute.subtask_id,
                task_to_compute.task_id,
                task_to_compute.price,
                comp_task_info.subtask_price,
            )
            return False
        comp_task_info.requests -= 1
        comp_task_info.subtasks[task_to_compute.subtask_id] = comp_task_def
        self.subtask_to_task[task_to_compute.subtask_id] =\
            task_to_compute.task_id
        self.dump()
        return True

    def check_comp_task_def(self, comp_task_def):
        task = self.active_tasks[comp_task_def['task_id']]
        key_id = self.get_node_for_task_id(comp_task_def['task_id'])
        not_accepted_message = "Cannot accept subtask %s for task %s. %s"
        log_args = [comp_task_def['subtask_id'], comp_task_def['task_id']]

        if not check_id_seed(comp_task_def['subtask_id'],
                             decode_hex(key_id)):
            logger.info(not_accepted_message, *log_args, "Subtask id was not "
                                                         "generated from "
                                                         "requestor's key.")
            return False
        if not task.requests > 0:
            logger.info(not_accepted_message, *log_args,
                        "Request for this task was not send.")

            return False
        if not task.check_deadline(comp_task_def['deadline']):
            msg = "Request for this task has wrong deadline %r" % \
                  comp_task_def['deadline']
            logger.info(not_accepted_message, *log_args, msg)
            return False
        if comp_task_def['subtask_id'] in task.subtasks:
            logger.info(not_accepted_message, *log_args,
                        "Definition of this subtask was already received.")
            return False
        return True

    def get_task_id_for_subtask(self, subtask_id):
        return self.subtask_to_task.get(subtask_id)

    @handle_key_error
    def get_node_for_task_id(self, task_id):
        return self.active_tasks[task_id].header.task_owner.key

    @handle_key_error
    def get_value(self, task_id: str) -> int:
        comp_task_info: CompTaskInfo = self.active_tasks[task_id]
        return comp_task_info.subtask_price

    def check_task_owner_by_subtask(self, task_owner_key_id, subtask_id):
        task_id = self.subtask_to_task.get(subtask_id)
        task = self.active_tasks.get(task_id)
        return task and task.header.task_owner.key == task_owner_key_id

    @handle_key_error
    def request_failure(self, task_id):
        logger.debug('CT.request_failure(%r)', task_id)
        self.active_tasks[task_id].requests -= 1
        self.dump()

    def remove_old_tasks(self):
        for task_id in frozenset(self.active_tasks):
            deadline = self.active_tasks[task_id].keeping_deadline
            delta = deadline - common.get_timestamp_utc()
            if delta > 0:
                continue
            logger.info("Removing comp_task after deadline: %s", task_id)
            for subtask_id in self.active_tasks[task_id].subtasks:
                del self.subtask_to_task[subtask_id]
            del self.active_tasks[task_id]

        self.dump()


class TaskHeaderKeeper:
    """Keeps information about tasks living in Golem Network. Node may
       choose one of those task to compute or will pass information
       to other nodes.
       Provider uses Taskkeeper to find tasks for itself
    """

    def __init__(
            self,
            environments_manager,
            min_price=0.0,
            app_version=golem.__version__,
            remove_task_timeout=180,
            verification_timeout=3600,
            max_tasks_per_requestor=10,
            task_archiver=None):
        # all computing tasks that this node knows about
        self.task_headers: typing.Dict[str, TaskHeader] = {}
        # ids of tasks that this node may try to compute
        self.supported_tasks = []
        # results of tasks' support checks
        self.support_status = {}
        # tasks that were removed from network recently, so they won't
        # be added again to task_headers
        self.removed_tasks = {}
        # task ids by owner
        self.tasks_by_owner = {}

        self.min_price = min_price
        self.app_version = app_version
        self.verification_timeout = verification_timeout
        self.removed_task_timeout = remove_task_timeout
        self.environments_manager = environments_manager
        self.max_tasks_per_requestor = max_tasks_per_requestor
        self.task_archiver = task_archiver

    def check_support(self, header: TaskHeader) -> SupportStatus:
        """Checks if task described with given task header dict
           may be computed by this node. This node must
           support proper environment, be allowed to make computation
           cheaper than with max price declared in task and have proper
           application version.
        :param TaskHeader header: task header
        :return SupportStatus: ok() if this node may compute a task
        """
        supported = self.check_environment(header.environment)
        supported = supported.join(self.check_price(header))
        supported = supported.join(self.check_version(header))
        if not supported.is_ok():
            logger.info("Unsupported task %s, reason: %r",
                        header.task_id, supported.desc)
        return supported

    def check_environment(self, env: str) -> SupportStatus:
        """Checks if this node supports the given environment

        :param str env: environment
        :return SupportStatus: ok() if this node support environment for this
                               task, err() otherwise
        """
        status = SupportStatus.ok()
        if not self.environments_manager.accept_tasks(env):
            status = SupportStatus.err(
                {UnsupportReason.ENVIRONMENT_NOT_ACCEPTING_TASKS: env})
        return self.environments_manager.get_support_status(env).join(status)

    def check_price(self, header: TaskHeader) -> SupportStatus:
        """Check if this node offers prices that isn't greater than maximum
           price described in task header.
        :param TaskHeader header: task header
        :return SupportStatus: err() if price offered by this node is higher
                               than maximum price for this task,
                               ok() otherwise.
        """
        max_price = getattr(header, "max_price", None)
        if max_price and max_price >= self.min_price:
            return SupportStatus.ok()
        return SupportStatus.err(
            {UnsupportReason.MAX_PRICE: getattr(header, "max_price", None)})

    def check_version(self, header: TaskHeader) -> SupportStatus:
        """Check if this node has a version that isn't less than minimum
           version described in task header.
        :param TaskHeader header: task header
        :return SupportStatus: err() if node's version is lower than minimum
                               version for this task, False otherwise.
        """
        min_v = getattr(header, "min_version", None)

        ok = False
        try:
            ok = self.check_version_compatibility(min_v)
        except ValueError:
            logger.error(
                "Wrong app version - app version %r, required version %r",
                self.app_version,
                min_v
            )
        if ok:
            return SupportStatus.ok()
        return SupportStatus.err({UnsupportReason.APP_VERSION: min_v})

    def check_version_compatibility(self, remote):
        """For local a1.b1.c1 and remote a2.b2.c2, check if "a1.b1" == "a2.b2"
           and c1 >= c2
        :param remote: remote version string
        :return: whether the local version is compatible with remote version
        """
        remote = Version(remote)
        local = Version(self.app_version, partial=True)
        if local.major != remote.major or local.minor != remote.minor:
            return False
        return local.patch >= remote.patch

    def get_support_status(self, task_id) -> typing.Optional[SupportStatus]:
        """Return SupportStatus stating if and why the task is supported or not.
        :param task_id: id of the task
        :return SupportStatus|None: the support status
                                    or None when task_id is unknown
        """
        return self.support_status.get(task_id)

    def get_all_tasks(self):
        """ Return all known tasks
        :return list: list of all known tasks
        """
        return list(self.task_headers.values())

    def change_config(self, config_desc):
        """Change config options, ie. minimal price that this node may offer
           for computation. If a minimal price didn't change it won't do
           anything. If it has changed it will try again to check which
           tasks are supported.
        :param ClientConfigDescriptor config_desc: new config descriptor
        """
        if config_desc.min_price == self.min_price:
            return
        self.min_price = config_desc.min_price
        self.supported_tasks = []
        for id_, th in self.task_headers.items():
            supported = self.check_support(th)
            self.support_status[id_] = supported
            if supported:
                self.supported_tasks.append(id_)
            if self.task_archiver:
                self.task_archiver.add_support_status(id_, supported)

    def add_task_header(self, header: TaskHeader):
        """This function will try to add to or update a task header
           in a list of known headers. The header will be added / updated
           only if it hasn't been removed recently. If it's new and supported
           its id will be put in supported task list.
        :param TaskHeader header: task header
        :return bool: True if task header was well formatted and
                      no error occurs, False otherwise
        """
        try:
            task_id = header.task_id
            task_owner_id = header.task_owner.key
            self.check_owner(task_id, task_owner_id)
            update = task_id in list(self.task_headers.keys())

            if task_id in list(self.removed_tasks.keys()):  # recent
                logger.debug("Received a task which has been already "
                             "cancelled/removed/timeout/banned/etc "
                             "Task id %s .", task_id)
                return True

            self.task_headers[task_id] = header

            self._get_tasks_by_owner_set(header.task_owner.key).add(task_id)

            self.update_supported_set(header, update)

            self.check_max_tasks_per_owner(header.task_owner.key)

            if self.task_archiver and task_id in self.task_headers:
                self.task_archiver.add_task(header)
                self.task_archiver.add_support_status(
                    task_id, self.support_status[task_id])

            return True
        except (KeyError, TypeError, WrongOwnerException) as err:
            logger.warning("Wrong task header received: {}".format(err))
            return False

    def update_supported_set(self, header: TaskHeader, update_header: bool) \
            -> None:

        task_id = header.task_id
        support = self.check_support(header)
        self.support_status[task_id] = support

        if update_header:
            if not support and task_id in self.supported_tasks:
                self.supported_tasks.remove(task_id)
        elif support:
            logger.info(
                "Adding task %r support=%r",
                task_id,
                support
            )
            self.supported_tasks.append(task_id)

    @staticmethod
    def check_owner(task_id, owner_id):
        if not check_id_seed(task_id, decode_hex(owner_id)):
            raise WrongOwnerException("Task_id %s doesn't suit to task "
                                      "owner %s", task_id, owner_id)

    def _get_tasks_by_owner_set(self, owner_key_id):
        if owner_key_id not in self.tasks_by_owner:
            self.tasks_by_owner[owner_key_id] = set()

        return self.tasks_by_owner[owner_key_id]

    def check_max_tasks_per_owner(self, owner_key_id):
        owner_task_set = self._get_tasks_by_owner_set(owner_key_id)

        if len(owner_task_set) <= self.max_tasks_per_requestor:
            return

        by_age = sorted(owner_task_set,
                        key=lambda tid: self.task_headers[tid].last_checking)

        # leave alone the first (oldest) max_tasks_per_requestor
        # headers, remove the rest
        to_remove = by_age[self.max_tasks_per_requestor:]

        logger.warning("Too many tasks from %s, dropping %d tasks",
                       owner_key_id, len(to_remove))

        for tid in to_remove:
            self.remove_task_header(tid)

    def remove_task_header(self, task_id) -> bool:
        """ Removes task with given id from a list of known task headers.
        return: False if task was already removed
        """
        if task_id in self.removed_tasks:
            return False

        if task_id in self.task_headers:
            owner_key_id = self.task_headers[task_id].task_owner.key
            del self.task_headers[task_id]
            if owner_key_id in self.tasks_by_owner:
                self.tasks_by_owner[owner_key_id].discard(task_id)
        if task_id in self.supported_tasks:
            self.supported_tasks.remove(task_id)
        if task_id in self.support_status:
            del self.support_status[task_id]
        self.removed_tasks[task_id] = time.time()
        return True

    def get_owner(self, task_id) -> typing.Optional[str]:
        """ Returns key_id of task owner or None if there is no information
        about this task.
        """
        task = self.task_headers.get(task_id)
        if task is None:
            return None
        return task.task_owner.key

    def get_task(self) -> TaskHeader:
        """ Returns random task from supported tasks that may be computed
        :return TaskHeader|None: returns either None if there are no tasks
                                 that this node may want to compute
        """
        if self.supported_tasks:
            tn = random.randrange(0, len(self.supported_tasks))
            task_id = self.supported_tasks[tn]
            return self.task_headers[task_id]

    def remove_old_tasks(self):
        for t in list(self.task_headers.values()):
            cur_time = common.get_timestamp_utc()
            if cur_time > t.deadline:
                logger.warning("Task owned by %s dies, task_id: %s",
                               t.task_owner.key, t.task_id)
                self.remove_task_header(t.task_id)

        for task_id, remove_time in list(self.removed_tasks.items()):
            cur_time = time.time()
            if cur_time - remove_time > self.removed_task_timeout:
                del self.removed_tasks[task_id]

    def request_failure(self, task_id):
        self.remove_task_header(task_id)

    def get_unsupport_reasons(self):
        """
        :return: list of dictionaries of the form {'reason': reason_type,
         'ntasks': task_count, 'avg': avg} where reason_type is one of
         unsupport reason types, task_count is the number of tasks currently
         affected with that reason, and avg (if available) is the current most
         typical corresponding value.  For unsupport reason
         MAX_PRICE avg is the average price of all tasks currently observed in
         the network. For unsupport reason APP_VERSION avg is
         the most popular app version of all tasks currently observed in the
         network.
        """
        c_reasons = Counter({r: 0 for r in UnsupportReason})
        for st in self.support_status.values():
            c_reasons.update(st.desc.keys())
        c_versions = Counter()
        c_price = 0
        for th in self.task_headers.values():
            c_versions[th.min_version] += 1
            c_price += th.max_price
        ret = []
        for (reason, count) in c_reasons.most_common():
            if reason == UnsupportReason.MAX_PRICE and self.task_headers:
                avg = int(c_price / len(self.task_headers))
            elif reason == UnsupportReason.APP_VERSION and c_versions:
                avg = c_versions.most_common(1)[0][0]
            else:
                avg = None
            ret.append({'reason': reason.value, 'ntasks': count, 'avg': avg})
        return ret
