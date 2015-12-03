import time
import logging

from golem.manager.nodestatesnapshot import LocalTaskStateSnapshot
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


class TaskManager:
    def __init__(self, node_name, node, listen_address="", listen_port=0, key_id="", root_path="res",
                 use_distributed_resources=True):
        self.node_name = node_name
        self.node = node

        self.tasks = {}
        self.tasks_states = {}

        self.listen_address = listen_address
        self.listen_port = listen_port
        self.key_id = key_id

        self.root_path = root_path
        self.dir_manager = DirManager(self.get_task_manager_root(), self.node_name)

        self.subtask2task_mapping = {}

        self.listeners = []
        self.activeStatus = [TaskStatus.computing, TaskStatus.starting, TaskStatus.waiting]

        self.use_distributed_resources = use_distributed_resources

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

        task.initialize()
        self.tasks[task.header.task_id] = task

        self.dir_manager.clear_temporary(task.header.task_id)
        self.dir_manager.get_task_temporary_dir(task.header.task_id, create=True)

        ts = TaskState()
        if self.use_distributed_resources:
            task.task_status = TaskStatus.sending
            ts.status = TaskStatus.sending
        else:
            task.task_status = TaskStatus.waiting
            ts.status = TaskStatus.waiting
        ts.time_started = time.time()

        self.tasks_states[task.header.task_id] = ts

        self.__notice_task_updated(task.header.task_id)

    def resources_send(self, task_id):
        self.tasks_states[task_id].status = TaskStatus.waiting
        self.tasks[task_id].task_status = TaskStatus.waiting
        self.__notice_task_updated(task_id)
        logger.info("Resources for task {} send".format(task_id))

    def get_next_subtask(self, node_id, node_name, task_id, estimated_performance, max_resource_size, max_memory_size,
                         num_cores=0):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            ts = self.tasks_states[task_id]
            th = task.header
            if self.__has_subtasks(ts, task, max_resource_size, max_memory_size):
                ctd = task.query_extra_data(estimated_performance, num_cores, node_id, node_name)
                if ctd is None or ctd.subtask_id is None:
                    return None, False
                ctd.key_id = node_id
                self.subtask2task_mapping[ctd.subtask_id] = task_id
                self.__add_subtask_to_tasks_states(node_name, ctd)
                self.__notice_task_updated(task_id)
                return ctd, False
            logger.info("Cannot get next task for estimated performence {}".format(estimated_performance))
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

    def get_price_mod(self, subtask_id):
        if subtask_id in self.subtask2task_mapping:
            task_id = self.subtask2task_mapping[subtask_id]
            return self.tasks[task_id].get_price_mod(subtask_id)
        else:
            logger.error("This is not my subtask {}".format(subtask_id))
            return 0

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

    def computed_task_received(self, subtask_id, result, result_type):
        if subtask_id in self.subtask2task_mapping:
            task_id = self.subtask2task_mapping[subtask_id]

            subtask_status = self.tasks_states[task_id].subtask_states[subtask_id].subtask_status
            if subtask_status != SubtaskStatus.starting:
                logger.warning("Result for subtask {} when subtask state is {}".format(subtask_id, subtask_status))
                self.__notice_task_updated(task_id)
                return False

            self.tasks[task_id].computation_finished(subtask_id, result, self.dir_manager, result_type)
            ss = self.tasks_states[task_id].subtask_states[subtask_id]
            ss.subtask_progress = 1.0
            ss.subtask_rem_time = 0.0
            ss.subtask_status = SubtaskStatus.finished

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
                    self.__notice_task_finished(task_id)
            self.__notice_task_updated(task_id)

            return True
        else:
            logger.error("It is not my task id {}".format(subtask_id))
            return False

    def task_computation_failure(self, subtask_id, err):
        if subtask_id in self.subtask2task_mapping:
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

            self.__notice_task_updated(task_id)
            return True
        else:
            logger.error("It is not my task id {}".format(subtask_id))
            return False

    # CHANGE TO RETURN KEY_ID (check IF SUBTASK COMPUTER HAS KEY_ID
    def remove_old_tasks(self):
        nodes_with_timeouts = []
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
            self.dir_manager.clear_temporary(task_id)

            self.tasks[task_id].restart()
            self.tasks[task_id].task_status = TaskStatus.waiting
            self.tasks_states[task_id].status = TaskStatus.waiting
            self.tasks_states[task_id].time_started = time.time()

            for sub in self.tasks_states[task_id].subtask_states.values():
                del self.subtask2task_mapping[sub.subtask_id]
            self.tasks_states[task_id].subtask_states.clear()

            self.__notice_task_updated(task_id)
        else:
            logger.error("Task {} not in the active tasks queue ".format(task_id))

    def restart_subtask(self, subtask_id):
        if not subtask_id in self.subtask2task_mapping:
            logger.error("Subtask {} not in subtasks queue".format(subtask_id))
            return

        task_id = self.subtask2task_mapping[subtask_id]
        self.tasks[task_id].restart_subtask(subtask_id)
        self.tasks_states[task_id].status = TaskStatus.computing
        self.tasks_states[task_id].subtask_states[subtask_id].subtask_status = SubtaskStatus.failure

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

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout, min_subtask_time):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.header.ttl = full_task_timeout
            task.header.subtask_timeout = subtask_timeout
            task.subtask_timeout = subtask_timeout
            task.min_subtask_time = min_subtask_time
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

    def __add_subtask_to_tasks_states(self, node_name, ctd):

        if ctd.task_id not in self.tasks_states:
            assert False, "Should never be here!"
        else:
            ts = self.tasks_states[ctd.task_id]

            ss = SubtaskState()
            ss.computer.node_id = ctd.key_id
            ss.computer.node_name = node_name
            ss.computer.performance = ctd.performance
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

    def __notice_task_finished(self, task_id):
        for l in self.listeners:
            l.task_finished(task_id)

    def __has_subtasks(self, task_state, task, max_resource_size, max_memory_size):
        if task_state.status not in self.activeStatus:
            return False
        if not task.needs_computation():
            return False
        if task.header.resource_size > (long(max_resource_size) * 1024):
            return False
        if task.header.estimated_memory > (long(max_memory_size) * 1024):
            return False
        return True
