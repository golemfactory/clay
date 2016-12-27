from __future__ import division

import logging
import random
import time
from math import ceil

from golem.core.common import HandleKeyError, get_timestamp_utc
from golem.core.variables import APP_VERSION

from .taskbase import TaskHeader, ComputeTaskDef

logger = logging.getLogger(__name__)


def compute_subtask_value(price, computation_time):
    return int(ceil(price * computation_time / 3600))


class CompTaskInfo(object):
    def __init__(self, header, price):
        self.header = header
        self.price = price
        self.requests = 1
        self.subtasks = {}


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
    """ Keeps information about subtasks that should be computed by this node."""

    handle_key_error = HandleKeyError(log_key_error)

    def __init__(self):
        """ Create new instance of compuatational task's definition's keeper
        """
        self.active_tasks = {}  # information about tasks that this node wants to compute
        self.subtask_to_task = {}  # maps subtasks id to tasks id

    def add_request(self, theader, price):
        assert type(price) in (int, long)
        assert price >= 0
        task_id = theader.task_id
        if task_id in self.active_tasks:
            self.active_tasks[task_id].requests += 1
        else:
            self.active_tasks[task_id] = CompTaskInfo(theader, price)

    @handle_key_error
    def get_subtask_ttl(self, task_id):
        return self.active_tasks[task_id].header.subtask_timeout

    @handle_key_error
    def receive_subtask(self, comp_task_def):
        task = self.active_tasks[comp_task_def.task_id]
        if task.requests > 0 and comp_task_def.subtask_id not in task.subtasks:
            task.requests -= 1
            task.subtasks[comp_task_def.subtask_id] = comp_task_def
            self.subtask_to_task[comp_task_def.subtask_id] = comp_task_def.task_id
            return True

    def get_task_id_for_subtask(self, subtask_id):
        return self.subtask_to_task.get(subtask_id)

    @handle_key_error
    def get_node_for_task_id(self, task_id):
        return self.active_tasks[task_id].header.task_owner_key_id

    @handle_key_error
    def get_value(self, task_id, computing_time):
        price = self.active_tasks[task_id].price
        assert type(price) in (int, long)
        return compute_subtask_value(price, computing_time)

    @handle_key_error
    def remove_task(self, task_id):
        del self.active_tasks[task_id]

    @handle_key_error
    def request_failure(self, task_id):
        self.active_tasks[task_id].requests -= 1

    def remove_old_tasks(self):
        time_ = get_timestamp_utc()
        for task_id, task in self.active_tasks.items():
            if time_ > task.header.deadline and len(task.subtasks) == 0:
                self.remove_task(task_id)


class TaskHeaderKeeper(object):
    """ Keeps information about tasks living in Golem Network. Node may choose one of those task
    to compute or will pass information to other nodes.
    """

    def __init__(self, environments_manager, min_price=0.0, app_version=APP_VERSION, remove_task_timeout=180,
                 verification_timeout=3600):
        self.task_headers = {}  # all computing tasks that this node now about
        self.supported_tasks = []  # ids of tasks that this node may try to compute
        self.removed_tasks = {}  # tasks that were removed from network recently, so they won't be add to again

        self.min_price = min_price
        self.app_version = app_version
        self.verification_timeout = verification_timeout
        self.removed_task_timeout = remove_task_timeout
        self.environments_manager = environments_manager

    def is_supported(self, th_dict_repr):
        """ Checks if task described with given task header dict representation may be computed
        by this node. This node must support proper environment, be allowed to make computation cheaper than with
        max price declared in task and have proper application version.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: True if this node may compute a task
        """
        supported = self.check_environment(th_dict_repr)
        supported = supported and self.check_price(th_dict_repr)
        return supported and self.check_version(th_dict_repr)

    @staticmethod
    def is_correct(th_dict_repr):
        """ Checks if task header dict representation has correctly defined parameters
         :param dict th_dict_repr: task header dictionary representation
         :return (bool, error): First element is True if task is properly defined (the second element is then None).
         Otheriwse first element is False and the second is the string describing wrong element
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
        """ Checks if this node supports environment necessary to compute task described with task header.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: True if this node support environment for this task, False otherwise
        """
        env = th_dict_repr.get("environment")
        if not self.environments_manager.supported(env):
            return False
        return self.environments_manager.accept_tasks(env)

    def check_price(self, th_dict_repr):
        """ Check if this node offers prices that isn't greater than maximum price described in task header.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: False if price offered by this node is higher that maximum price for this task, True otherwise.
        """
        return th_dict_repr.get("max_price") >= self.min_price

    def check_version(self, th_dict_repr):
        """ Check if this node has a version that isn't less than minimum version described in task header. If there
        is no version specified it will return True.
        :param dict th_dict_repr: task header dictionary representation
        :return bool: False if node's version is lower than minimum version for this task, False otherwise.
        """
        min_v = th_dict_repr.get("min_version")
        if not min_v:
            return True
        try:
            supported = float(self.app_version) >= float(min_v)
            return supported
        except ValueError:
            logger.error(
                "Wrong app version - app version {}, required version {}".format(
                    self.app_version,
                    min_v
                )
            )
            return False

    def get_all_tasks(self):
        """ Return all known tasks
        :return list: list of all known tasks
        """
        return self.task_headers.values()

    def change_config(self, config_desc):
        """ Change config options, ie. minimal price that this node may offer for computation. If a minimal price
         didn't change it won't do anything. If it has changed it will try again to check which tasks are supported.
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
        """ This function will try to add to or update a task header in a list of known headers. The header will be
        added / updated only if it hasn't been removed recently. If it's new and supported its id will be put in
        supported task list.
        :param dict th_dict_repr: task dictionary representation
        :return bool: True if task header was well formatted and no error occurs, False otherwise
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
                    logger.info("Adding task {} is_supported={}".format(id_, is_supported))
                    self.supported_tasks.append(id_)

            return True
        except (KeyError, TypeError) as err:
            logger.error("Wrong task header received {}".format(err))
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
        :return TaskHeader|None: returns either None if there are no tasks that this node may want to compute
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
