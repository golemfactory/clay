import time
import logging
from math import ceil

from golem.manager.nodestatesnapshot import LocalTaskStateSnapshot
from golem.resource.ipfs.resourcesmanager import IPFSResourceManager
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.taskkeeper import CompTaskKeeper
from golem.task.taskstate import TaskState, TaskStatus, SubtaskStatus, SubtaskState
from golem.resource.dirmanager import DirManager
from golem.core.hostaddress import get_external_address

logger = logging.getLogger(__name__)


class TaskManagerEventListener:
    def __init__(self):
        pass

    def task_status_updated(self, task_id):
        pass

    def subtask_status_updated(self, subtask_id):
        pass


def react_to_key_error(func):
    def func_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError:
            logger.warning("This is not my subtask {}".format(args[1]))
            return None

    return func_wrapper


class TaskManager(object):
    """ Keeps and manages information about requested tasks
    """
    def __init__(self, node_name, node, listen_address="", listen_port=0, key_id="", root_path="res",
                 use_distributed_resources=True):
        self.node_name = node_name
        self.node = node

        self.tasks = {}
        self.tasks_states = {}
        self.subtask2task_mapping = {}

        self.listen_address = listen_address
        self.listen_port = listen_port
        self.key_id = key_id

        self.root_path = root_path
        self.dir_manager = DirManager(self.get_task_manager_root(), self.node_name)

        resource_manager = IPFSResourceManager(self.dir_manager,
                                               resource_dir_method=self.dir_manager.get_task_temporary_dir)
        self.task_result_manager = EncryptedResultPackageManager(resource_manager)

        self.listeners = []
        self.activeStatus = [TaskStatus.computing, TaskStatus.starting, TaskStatus.waiting]
        self.use_distributed_resources = use_distributed_resources

        self.comp_task_keeper = CompTaskKeeper()

    def get_task_manager_root(self):
        return self.root_path

    def register_listener(self, listener):
        assert isinstance(listener, TaskManagerEventListener)

        if listener in self.listeners:
            logger.error("listener {} already registered ".format(listener))
            return

        self.listeners.append(listener)

    def unregister_listener(self, listener):
        for i in range(len(self.listeners)):
            if self.listeners[i] is listener:
                del self.listeners[i]
                return

    def add_new_task(self, task):
        assert task.header.task_id not in self.tasks

        task.header.task_owner_address = self.listen_address
        task.header.task_owner_port = self.listen_port
        task.header.task_owner_key_id = self.key_id
        self.node.pub_addr, self.node.pub_port, self.node.nat_type = get_external_address(self.listen_port)
        task.header.task_owner = self.node

        self.dir_manager.clear_temporary(task.header.task_id, undeletable=task.undeletable)
        self.dir_manager.get_task_temporary_dir(task.header.task_id, create=True)

        task.initialize(self.dir_manager)
        task.notify_update_task = self.__notice_task_updated
        self.tasks[task.header.task_id] = task

        ts = TaskState()

        # if self.use_distributed_resources:
        #     task.task_status = TaskStatus.sending
        #     ts.status = TaskStatus.sending
        # else:
        #     task.task_status = TaskStatus.waiting
        #     ts.status = TaskStatus.waiting

        task.task_status = TaskStatus.waiting
        ts.status = TaskStatus.waiting

        ts.time_started = time.time()

        self.tasks_states[task.header.task_id] = ts
        logger.info("Task {} added".format(task.header.task_id))

        self.__notice_task_updated(task.header.task_id)

    def resources_send(self, task_id):
        self.tasks_states[task_id].status = TaskStatus.waiting
        self.tasks[task_id].task_status = TaskStatus.waiting
        self.__notice_task_updated(task_id)
        logger.info("Resources for task {} sent".format(task_id))

    def get_next_subtask(self, node_id, node_name, task_id, estimated_performance, price, max_resource_size,
                         max_memory_size, num_cores=0, address=""):
        """ Assign next subtask from task <task_id> to node with given id <node_id> and name. If subtask is assigned
        the function is returning a tuple (
        :param node_id:
        :param node_name:
        :param task_id:
        :param estimated_performance:
        :param price:
        :param max_resource_size:
        :param max_memory_size:
        :param num_cores:
        :param address:
        :return (ComputeTaskDef|None, bool): Function return a pair. First element is either ComputeTaskDef that
        describe assigned subtask or None. The second element describes whether the task_id is a wrong task that isn't
        in task manager register. If task with <task_id> it's a known task then second element of a pair is always
        False (regardless new subtask was assigned or not).
        """
        if task_id in self.tasks:
            task = self.tasks[task_id]
            ts = self.tasks_states[task_id]
            th = task.header
            if th.max_price < price:
                logger.info("Cannot get next task for this node - price too high.")
                return None, False

            if self.__has_subtasks(ts, task, max_resource_size, max_memory_size):
                ctd = task.query_extra_data(estimated_performance, num_cores, node_id, node_name)
                if ctd is None or ctd.subtask_id is None:
                    return None, False
                ctd.key_id = th.task_owner_key_id
                self.subtask2task_mapping[ctd.subtask_id] = task_id
                self.__add_subtask_to_tasks_states(node_name, node_id, price, ctd, address)
                self.__notice_task_updated(task_id)
                return ctd, False
            logger.info("Cannot get next task for estimated performance {}".format(estimated_performance))
            return None, False
        else:
            logger.info("Cannot find task {} in my tasks".format(task_id))
            return None, True

    def get_tasks_headers(self):
        ret = []
        for t in self.tasks.values():
            if t.needs_computation() and t.task_status in self.activeStatus:
                ret.append(t.header)

        return ret

    def get_trust_mod(self, subtask_id):
        if subtask_id in self.subtask2task_mapping:
            task_id = self.subtask2task_mapping[subtask_id]
            return self.tasks[task_id].get_trust_mod(subtask_id)
        else:
            logger.error("This is not my subtask {}".format(subtask_id))
            return 0

    def verify_subtask(self, subtask_id):
        if subtask_id in self.subtask2task_mapping:
            task_id = self.subtask2task_mapping[subtask_id]
            return self.tasks[task_id].verify_subtask(subtask_id)
        else:
            return False

    def get_node_id_for_subtask(self, subtask_id):
        if subtask_id in self.subtask2task_mapping:
            subtask_state = self.tasks_states[self.subtask2task_mapping[subtask_id]].subtask_states[subtask_id]
            return subtask_state.computer.node_id
        else:
            return None

    def set_value(self, task_id, subtask_id, value):
        assert type(value) in (int, long)
        task_state = self.tasks_states.get(task_id)
        if task_state is None:
            logger.warning("This is not my task {}".format(task_id))
            return
        subtask_state = task_state.subtask_states.get(subtask_id)
        if subtask_state is None:
            logger.warning("This is not my subtask {}".format(subtask_id))
            return
        subtask_state.value = value

    @react_to_key_error
    def get_value(self, subtask_id):
        """ Return value of a given subtask
        :param subtask_id:  id of a computed subtask
        :return float: price that should be paid for given subtask
        """
        task_id = self.subtask2task_mapping[subtask_id]
        return self.tasks_states[task_id].subtask_states[subtask_id].value

    @react_to_key_error
    def computed_task_received(self, subtask_id, result, result_type):
        task_id = self.subtask2task_mapping[subtask_id]

        subtask_status = self.tasks_states[task_id].subtask_states[subtask_id].subtask_status
        if subtask_status != SubtaskStatus.starting:
            if subtask_status == SubtaskStatus.restarted:
                self.tasks[task_id].computation_finished(subtask_id, result, self.dir_manager, result_type)
                return self.tasks[task_id].verify_subtask(subtask_id)
            else:
                logger.warning("Result for subtask {} when subtask state is {}".format(subtask_id, subtask_status))
                self.__notice_task_updated(task_id)
                return False

        self.tasks[task_id].computation_finished(subtask_id, result, self.dir_manager, result_type)
        ss = self.tasks_states[task_id].subtask_states[subtask_id]
        ss.subtask_progress = 1.0
        ss.subtask_rem_time = 0.0
        ss.subtask_status = SubtaskStatus.finished
        ss.stdout = self.tasks[task_id].get_stdout(subtask_id)
        ss.stderr = self.tasks[task_id].get_stderr(subtask_id)
        ss.results = self.tasks[task_id].get_results(subtask_id)

        if not self.tasks[task_id].verify_subtask(subtask_id):
            logger.debug("Subtask {} not accepted\n".format(subtask_id))
            ss.subtask_status = SubtaskStatus.failure
            self.__notice_task_updated(task_id)
            return False

        if self.tasks_states[task_id].status in self.activeStatus:
            if not self.tasks[task_id].finished_computation():
                self.tasks_states[task_id].status = TaskStatus.computing
            else:
                if self.tasks[task_id].verify_task():
                    logger.debug("Task {} accepted".format(task_id))
                    self.tasks_states[task_id].status = TaskStatus.finished
                else:
                    logger.debug("Task {} not accepted".format(task_id))
        self.__notice_task_updated(task_id)

        return True

    @react_to_key_error
    def task_computation_failure(self, subtask_id, err):
        task_id = self.subtask2task_mapping[subtask_id]
        subtask_status = self.tasks_states[task_id].subtask_states[subtask_id].subtask_status
        if subtask_status != SubtaskStatus.starting:
            logger.warning("Result for subtask {} when subtask state is {}".format(subtask_id, subtask_status))
            self.__notice_task_updated(task_id)
            return False

        self.tasks[task_id].computation_failed(subtask_id)
        ss = self.tasks_states[task_id].subtask_states[subtask_id]
        ss.subtask_progress = 1.0
        ss.subtask_rem_time = 0.0
        ss.subtask_status = SubtaskStatus.failure
        ss.stderr = str(err)

        self.__notice_task_updated(task_id)
        return True

    # CHANGE TO RETURN KEY_ID (check IF SUBTASK COMPUTER HAS KEY_ID
    def remove_old_tasks(self):
        nodes_with_timeouts = []
        self.comp_task_keeper.remove_old_tasks()
        for t in self.tasks.values():
            th = t.header
            if self.tasks_states[th.task_id].status not in self.activeStatus:
                continue
            cur_time = time.time()
            th.ttl = th.ttl - (cur_time - th.last_checking)
            th.last_checking = cur_time
            if th.ttl <= 0:
                logger.info("Task {} dies".format(th.task_id))
                del self.tasks[th.task_id]
                continue
            ts = self.tasks_states[th.task_id]
            for s in ts.subtask_states.values():
                if s.subtask_status == SubtaskStatus.starting:
                    s.ttl = s.ttl - (cur_time - s.last_checking)
                    s.last_checking = cur_time
                    if s.ttl <= 0:
                        logger.info("Subtask {} dies".format(s.subtask_id))
                        s.subtask_status = SubtaskStatus.failure
                        nodes_with_timeouts.append(s.computer.node_id)
                        t.computation_failed(s.subtask_id)
                        s.stderr = "[GOLEM] Timeout"
                        self.__notice_task_updated(th.task_id)
        return nodes_with_timeouts

    def get_progresses(self):
        tasks_progresses = {}

        for t in self.tasks.values():
            if t.get_progress() < 1.0:
                ltss = LocalTaskStateSnapshot(t.header.task_id, t.get_total_tasks(),
                                              t.get_active_tasks(), t.get_progress(), t.short_extra_data_repr(2200.0))
                tasks_progresses[t.header.task_id] = ltss

        return tasks_progresses

    def get_resources(self, task_id, resource_header, resource_type=0):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            return task.get_resources(task_id, resource_header, resource_type)

    def accept_results_delay(self, task_id):
        if task_id in self.tasks:
            return self.tasks[task_id].accept_results_delay()
        else:
            return -1.0

    def restart_task(self, task_id):
        if task_id in self.tasks:
            logger.info("restarting task")

            self.tasks[task_id].restart()
            self.tasks[task_id].task_status = TaskStatus.waiting
            self.tasks_states[task_id].status = TaskStatus.waiting
            self.tasks_states[task_id].time_started = time.time()

            self.dir_manager.clear_temporary(task_id, undeletable=self.tasks[task_id].undeletable)
            for ss in self.tasks_states[task_id].subtask_states.values():
                if ss.subtask_status != SubtaskStatus.failure:
                    ss.subtask_status = SubtaskStatus.restarted

            self.__notice_task_updated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    @react_to_key_error
    def restart_subtask(self, subtask_id):

        task_id = self.subtask2task_mapping[subtask_id]
        self.tasks[task_id].restart_subtask(subtask_id)
        self.tasks_states[task_id].status = TaskStatus.computing
        self.tasks_states[task_id].subtask_states[subtask_id].subtask_status = SubtaskStatus.restarted
        self.tasks_states[task_id].subtask_states[subtask_id].stderr = "[GOLEM] Restarted"
        self.__notice_task_updated(task_id)

    def abort_task(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].abort()
            self.tasks[task_id].task_status = TaskStatus.aborted
            self.tasks_states[task_id].status = TaskStatus.aborted
            for sub in self.tasks_states[task_id].subtask_states.values():
                del self.subtask2task_mapping[sub.subtask_id]
            self.tasks_states[task_id].subtask_states.clear()

            self.__notice_task_updated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    def pause_task(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].task_status = TaskStatus.paused
            self.tasks_states[task_id].status = TaskStatus.paused

            self.__notice_task_updated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    def resume_task(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].task_status = TaskStatus.starting
            self.tasks_states[task_id].status = TaskStatus.starting

            self.__notice_task_updated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    def delete_task(self, task_id):
        if task_id in self.tasks:

            for sub in self.tasks_states[task_id].subtask_states.values():
                del self.subtask2task_mapping[sub.subtask_id]
            self.tasks_states[task_id].subtask_states.clear()

            self.tasks[task_id].notify_update_task = None
            del self.tasks[task_id]
            del self.tasks_states[task_id]

            self.dir_manager.clear_temporary(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    def query_task_state(self, task_id):
        if task_id in self.tasks_states and task_id in self.tasks:
            ts = self.tasks_states[task_id]
            t = self.tasks[task_id]

            ts.progress = t.get_progress()
            ts.elapsed_time = time.time() - ts.time_started

            if ts.progress > 0.0:
                ts.remaining_time = (ts.elapsed_time / ts.progress) - ts.elapsed_time
            else:
                ts.remaining_time = -0.0

            t.update_task_state(ts)

            return ts
        else:
            assert False, "Should never be here!"

    def change_config(self, root_path, use_distributed_resource_management):
        self.dir_manager = DirManager(root_path, self.node_name)
        self.use_distributed_resources = use_distributed_resource_management

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.header.ttl = full_task_timeout
            task.header.subtask_timeout = subtask_timeout
            task.subtask_timeout = subtask_timeout
            task.full_task_timeout = full_task_timeout
            task.header.last_checking = time.time()
            ts = self.tasks_states[task_id]
            for s in ts.subtask_states.values():
                s.ttl = subtask_timeout
                s.last_checking = time.time()
            return True
        else:
            logger.info("Cannot find task {} in my tasks".format(task_id))
            return False

    def get_task_id(self, subtask_id):
        return self.subtask2task_mapping[subtask_id]

    @react_to_key_error
    def set_computation_time(self, subtask_id, computation_time):
        """
        Set computation time for subtask and also compute and set new value based on saved price for this subtask
        :param str subtask_id: subtask which was computed in given computation_time
        :param float computation_time: how long does it take to compute this task
        :return:
        """
        task_id = self.subtask2task_mapping[subtask_id]
        ss = self.tasks_states[task_id].subtask_states[subtask_id]
        ss.computation_time = computation_time
        ss.value = self.compute_subtask_value(ss.computer.price, computation_time)

    @staticmethod
    def compute_subtask_value(price, computation_time):
        return int(ceil(price * computation_time))

    def add_comp_task_request(self, theader, price):
        """ Add a header of a task which this node may try to compute """
        self.comp_task_keeper.add_request(theader, price)

    def __add_subtask_to_tasks_states(self, node_name, node_id, price, ctd, address):

        if ctd.task_id not in self.tasks_states:
            assert False, "Should never be here!"
        else:
            ts = self.tasks_states[ctd.task_id]

            ss = SubtaskState()
            ss.computer.node_id = node_id
            ss.computer.node_name = node_name
            ss.computer.performance = ctd.performance
            ss.computer.ip_address = address
            ss.computer.price = price
            ss.time_started = time.time()
            ss.ttl = self.tasks[ctd.task_id].header.subtask_timeout
            # TODO: read node ip address
            ss.subtask_definition = ctd.short_description
            ss.subtask_id = ctd.subtask_id
            ss.extra_data = ctd.extra_data
            ss.subtask_status = TaskStatus.starting
            ss.value = 0

            ts.subtask_states[ctd.subtask_id] = ss

    def __notice_task_updated(self, task_id):
        for l in self.listeners:
            l.task_status_updated(task_id)

    def __has_subtasks(self, task_state, task, max_resource_size, max_memory_size):
        if task_state.status not in self.activeStatus:
            logger.info("Task doesn't have more subtask for this node - task not active.")
            return False
        if not task.needs_computation():
            logger.info("Task doesn't have more subtask for this node - task doesn't need computation.")
            return False
        if task.header.resource_size > (long(max_resource_size) * 1024):
            logger.info("Task doesn't have more subtask for this node - resource size limits too small.")
            return False
        if task.header.estimated_memory > (long(max_memory_size) * 1024):
            logger.info("Task doesn't have more subtask for this node -  memory limits too small. ")
            return False
        return True
