from __future__ import division

import logging
import math
import pickle
import random
import time

from semantic_version import Version

from golem.core.common import HandleKeyError, get_timestamp_utc
from golem.core.variables import APP_VERSION

from .taskbase import TaskHeader, ComputeTaskDef

logger = logging.getLogger('golem.task.taskkeeper')


def compute_subtask_value(price, computation_time):
    return int(math.ceil(price * computation_time / 3600))


class CompTaskInfo(object):
    def __init__(self, header, price):
        self.header = header
        self.price = price
        self.requests = 1
        self.subtasks = {}

    def __repr__(self):
        return "<CompTaskInfo(%r, %r) reqs: %r>" % (
            self.header,
            self.price,
            self.requests
        )


class CompSubtaskInfo(object):
    def __init__(self, subtask_id):
        self.subtask_id = subtask_id


def log_key_error(*args, **kwargs):
    if isinstance(args[1], ComputeTaskDef):
        task_id = args[1].task_id
    else:
        task_id = args[1]
    logger.warning("This is not my task {}".format(task_id))
    return None


class CompTaskKeeper(object):
    """Keeps information about subtasks that should be computed by this node.
    """

    handle_key_error = HandleKeyError(log_key_error)

    def __init__(self, tasks_path, persist=True):
        """ Create new instance of compuatational task's definition's keeper

        tasks_path: pathlib.Path to tasks directory
        """
        # information about tasks that this node wants to compute
        self.active_tasks = {}
        self.subtask_to_task = {}  # maps subtasks id to tasks id
        self.dump_path = tasks_path / "comp_task_keeper.pickle"
        self.persist = persist
        self.restore()

    def dump(self):
        if not self.persist:
            return
        logger.debug('COMPTASK DUMP: %s', self.dump_path)
        with self.dump_path.open('wb') as f:
            dump_data = self.active_tasks, self.subtask_to_task
            from pprint import pformat
            for task in self.active_tasks.values():
                logger.debug('dump_data: %s', pformat(task))
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
            except (pickle.UnpicklingError, EOFError):
                logger.exception(
                    'Problem restoring dumpfile: %s',
                    self.dump_path
                )
                return
        self.active_tasks.update(active_tasks)
        self.subtask_to_task.update(subtask_to_task)

    def add_request(self, theader, price):
        logger.debug('CT.add_request()')
        if not type(price) in (int, long):
            raise TypeError(
                "Incorrect 'price' type: {}."
                " Should be int or long".format(type(price))
            )
        if price < 0:
            raise ValueError("Price should be greater or equal zero")
        task_id = theader.task_id
        if task_id in self.active_tasks:
            self.active_tasks[task_id].requests += 1
        else:
            self.active_tasks[task_id] = CompTaskInfo(theader, price)
        self.dump()

    @handle_key_error
    def get_subtask_ttl(self, task_id):
        return self.active_tasks[task_id].header.subtask_timeout

    @handle_key_error
    def get_task_env(self, task_id):
        return self.active_tasks[task_id].header.environment

    @handle_key_error
    def receive_subtask(self, comp_task_def):
        logger.debug('CT.receive_subtask()')
        task = self.active_tasks[comp_task_def.task_id]
        if not task.requests > 0:
            return
        if comp_task_def.subtask_id in task.subtasks:
            return
        task.requests -= 1
        task.subtasks[comp_task_def.subtask_id] = comp_task_def
        self.subtask_to_task[comp_task_def.subtask_id] = comp_task_def.task_id
        self.dump()
        return True

    def get_task_id_for_subtask(self, subtask_id):
        return self.subtask_to_task.get(subtask_id)

    @handle_key_error
    def get_node_for_task_id(self, task_id):
        return self.active_tasks[task_id].header.task_owner_key_id

    @handle_key_error
    def get_value(self, task_id, computing_time):
        price = self.active_tasks[task_id].price
        if not type(price) in (int, long):
            raise TypeError(
                "Incorrect 'price' type: {}."
                " Should be int or long".format(type(price))
            )
        return compute_subtask_value(price, computing_time)

    @handle_key_error
    def request_failure(self, task_id):
        logger.debug('CT.request_failure(%r)', task_id)
        self.active_tasks[task_id].requests -= 1
        self.dump()


class TaskHeaderKeeper(object):
    """Keeps information about tasks living in Golem Network. Node may
       choose one of those task to compute or will pass information
       to other nodes.
    """

    def __init__(
            self,
            environments_manager,
            min_price=0.0,
            app_version=APP_VERSION,
            remove_task_timeout=180,
            verification_timeout=3600
            ):
        # all computing tasks that this node knows about
        self.task_headers = {}
        # ids of tasks that this node may try to compute
        self.supported_tasks = []
        # tasks that were removed from network recently, so they won't
        # be added again to task_headers
        self.removed_tasks = {}

        self.min_price = min_price
        self.app_version = app_version
        self.verification_timeout = verification_timeout
        self.removed_task_timeout = remove_task_timeout
        self.environments_manager = environments_manager

    def is_supported(self, th_dict_repr):
        """Checks if task described with given task header dict
           representation may be computed by this node. This node must
           support proper environment, be allowed to make computation
           cheaper than with max price declared in task and have proper
           application version.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: True if this node may compute a task
        """
        supported = self.check_environment(th_dict_repr)
        supported = supported and self.check_price(th_dict_repr)
        return supported and self.check_version(th_dict_repr)

    @staticmethod
    def is_correct(th_dict_repr):
        """Checks if task header dict representation has correctly
           defined parameters
         :param dict th_dict_repr: task header dictionary representation
         :return (bool, error): First element is True if task is properly
                                defined (the second element is then None).
         Otheriwse first element is False and the second is the string
         describing wrong element
        """
        if not isinstance(th_dict_repr['deadline'], (int, long, float)):
            return False, "Deadline is not a timestamp"
        if th_dict_repr['deadline'] < get_timestamp_utc():
            return False, "Deadline already passed"
        if not isinstance(th_dict_repr['subtask_timeout'], int):
            return False, "Subtask timeout is not a number"
        if th_dict_repr['subtask_timeout'] < 0:
            return False, "Subtask timeout is less than 0"
        return True, None

    def check_environment(self, th_dict_repr):
        """Checks if this node supports environment necessary to compute task
           described with task header.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: True if this node support environment for this task,
                      False otherwise
        """
        env = th_dict_repr.get("environment")
        if not self.environments_manager.supported(env):
            return False
        return self.environments_manager.accept_tasks(env)

    def check_price(self, th_dict_repr):
        """Check if this node offers prices that isn't greater than maximum
           price described in task header.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: False if price offered by this node is higher than
                      maximum price for this task, True otherwise.
        """
        return th_dict_repr.get("max_price") >= self.min_price

    def check_version(self, th_dict_repr):
        """Check if this node has a version that isn't less than minimum
           version described in task header. If there is no version specified
           it will return True.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: False if node's version is lower than minimum version
                      for this task, False otherwise.
        """
        min_v = th_dict_repr.get("min_version")

        try:
            return self.check_version_compatibility(min_v)
        except ValueError:
            logger.error(
                "Wrong app version - app version %r, required version %r",
                self.app_version,
                min_v
            )
            return False

    def check_version_compatibility(self, remote):
        """For local a1.b1.c1 and remote a2.b2.c2, check if "a1.b1" == "a2.b2"
           and c1 >= c2
        :param remote: remote version string
        :return: whether the local version is compatible with remote version
        """
        remote = Version(remote)
        local = Version(self.app_version, partial=True)
        local_patch = local.patch
        local.patch = None
        return local == remote and local_patch >= remote.patch

    def get_all_tasks(self):
        """ Return all known tasks
        :return list: list of all known tasks
        """
        return self.task_headers.values()

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
        for id_, th in self.task_headers.iteritems():
            if self.is_supported(th.__dict__):
                self.supported_tasks.append(id_)

    def add_task_header(self, th_dict_repr):
        """This function will try to add to or update a task header
           in a list of known headers. The header will be added / updated
           only if it hasn't been removed recently. If it's new and supported
           its id will be put in supported task list.
        :param dict th_dict_repr: task dictionary representation
        :return bool: True if task header was well formatted and
                      no error occurs, False otherwise
        """
        try:
            id_ = th_dict_repr["task_id"]
            update = id_ in self.task_headers.keys()
            is_correct, err = self.is_correct(th_dict_repr)
            if not is_correct:
                raise TypeError(err)

            if id_ not in self.removed_tasks.keys():  # not removed recently
                self.task_headers[id_] = TaskHeader.from_dict(th_dict_repr)
                is_supported = self.is_supported(th_dict_repr)

                if update:
                    if not is_supported and id_ in self.supported_tasks:
                        self.supported_tasks.remove(id_)
                elif is_supported:
                    logger.info(
                        "Adding task %r is_supported=%r",
                        id_,
                        is_supported
                    )
                    self.supported_tasks.append(id_)

            return True
        except (KeyError, TypeError) as err:
            logger.warning("Wrong task header received {}".format(err))
            return False

    def remove_task_header(self, task_id):
        """ Removes task with given id from a list of known task headers.
        """
        if task_id in self.task_headers:
            del self.task_headers[task_id]
        if task_id in self.supported_tasks:
            self.supported_tasks.remove(task_id)
        self.removed_tasks[task_id] = time.time()

    def get_task(self):
        """ Returns random task from supported tasks that may be computed
        :return TaskHeader|None: returns either None if there are no tasks
                                 that this node may want to compute
        """
        if len(self.supported_tasks) > 0:
            tn = random.randrange(0, len(self.supported_tasks))
            task_id = self.supported_tasks[tn]
            return self.task_headers[task_id]

    def remove_old_tasks(self):
        for t in self.task_headers.values():
            cur_time = get_timestamp_utc()
            if cur_time > t.deadline:
                logger.warning("Task {} dies".format(t.task_id))
                self.remove_task_header(t.task_id)

        for task_id, remove_time in self.removed_tasks.items():
            cur_time = time.time()
            if cur_time - remove_time > self.removed_task_timeout:
                del self.removed_tasks[task_id]

    def request_failure(self, task_id):
        self.remove_task_header(task_id)
