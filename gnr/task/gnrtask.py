import copy
import logging
import pickle
import os

from golem.core.common import HandleKeyError, timeout_to_deadline
from golem.core.compress import decompress
from golem.core.fileshelper import outer_dir_path
from golem.environments.environment import Environment
from golem.network.p2p.node import Node
from golem.resource.resource import prepare_delta_zip, TaskResourceHeader
from golem.task.taskbase import Task, TaskHeader, TaskBuilder, result_types, resource_types
from golem.task.taskstate import SubtaskStatus

from gnr.gnrtaskstate import AdvanceVerificationOptions

logger = logging.getLogger("gnr.task")


def log_key_error(*args, **kwargs):
    logger.warning("This is not my subtask {}".format(args[1]))
    return False


class GNRTaskBuilder(TaskBuilder):
    def __init__(self, node_name, task_definition, root_path, dir_manager):
        super(GNRTaskBuilder, self).__init__()
        self.task_definition = task_definition
        self.node_name = node_name
        self.root_path = root_path
        self.dir_manager = dir_manager

    def build(self):
        pass


class GNRSubtask(object):
    def __init__(self, subtask_id, start_chunk, end_chunk):
        self.subtask_id = subtask_id
        self.start_chunk = start_chunk
        self.end_chunk = end_chunk


class GNROptions(object):
    def __init__(self):
        self.environment = Environment()

    def add_to_resources(self, resources):
        return resources

    def remove_from_resources(self, resources):
        return resources


class GNRTask(Task):
    handle_key_error = HandleKeyError(log_key_error)

    ################
    # Task methods #
    ################

    def __init__(self, src_code, node_name, task_id, owner_address, owner_port, owner_key_id, environment,
                 task_timeout, subtask_timeout, resource_size, estimated_memory, max_price, docker_images=None):

        """ Create more specific task implementation
        :param src_code:
        :param node_name:
        :param task_id:
        :param owner_address:
        :param owner_port:
        :param owner_key_id:
        :param environment:
        :param task_timeout:
        :param subtask_timeout:
        :param resource_size:
        :param estimated_memory:
        :param float max_price: maximum price that this node may par for an hour of computation
        :param docker_images: docker image specification
        """
        deadline = timeout_to_deadline(task_timeout)
        th = TaskHeader(node_name, task_id, owner_address, owner_port, owner_key_id, environment, Node(),
                        deadline, subtask_timeout, resource_size, estimated_memory, max_price=max_price,
                        docker_images=docker_images)

        Task.__init__(self, th, src_code)

        self.task_resources = set()

        self.total_tasks = 0
        self.last_task = 0

        self.num_tasks_received = 0
        self.subtasks_given = {}
        self.num_failed_subtasks = 0

        self.full_task_timeout = task_timeout
        self.counting_nodes = {}

        self.root_path = None

        self.stdout = {}  # for each subtask keep information about stdout received from computing node
        self.stderr = {}  # for each subtask keep information about stderr received from computing node
        self.results = {}  # for each subtask keep information about files containing results

        self.res_files = {}
        self.tmp_dir = None
        self.verification_options = AdvanceVerificationOptions()

    def is_docker_task(self):
        return self.header.docker_images is not None

    def initialize(self, dir_manager):
        self.tmp_dir = dir_manager.get_task_temporary_dir(self.header.task_id, create=True)

    def needs_computation(self):
        return (self.last_task != self.total_tasks) or (self.num_failed_subtasks > 0)

    def finished_computation(self):
        return self.num_tasks_received == self.total_tasks

    def computation_failed(self, subtask_id):
        self._mark_subtask_failed(subtask_id)

    @handle_key_error
    def verify_subtask(self, subtask_id):
        return self.subtasks_given[subtask_id]['status'] == SubtaskStatus.finished

    def verify_task(self):
        return self.finished_computation()

    def get_total_tasks(self):
        return self.total_tasks

    def get_active_tasks(self):
        return self.last_task

    def get_tasks_left(self):
        return (self.total_tasks - self.last_task) + self.num_failed_subtasks

    def restart(self):
        for subtask_id in self.subtasks_given.keys():
            self.restart_subtask(subtask_id)

    @handle_key_error
    def restart_subtask(self, subtask_id):
        was_failure_before = self.subtasks_given[subtask_id]['status'] in [SubtaskStatus.failure, SubtaskStatus.resent]
        if subtask_id in self.subtasks_given:
            if self.subtasks_given[subtask_id]['status'] == SubtaskStatus.starting:
                self._mark_subtask_failed(subtask_id)
            elif self.subtasks_given[subtask_id]['status'] == SubtaskStatus.finished:
                self._mark_subtask_failed(subtask_id)
                tasks = self.subtasks_given[subtask_id]['end_task'] - self.subtasks_given[subtask_id]['start_task'] + 1
                self.num_tasks_received -= tasks
        if not was_failure_before:
            self.subtasks_given[subtask_id]['status'] = SubtaskStatus.restarted

    def abort(self):
        pass

    def get_progress(self):
        return float(self.num_tasks_received) / self.total_tasks

    def get_resources(self, task_id, resource_header, resource_type=0, tmp_dir=None):

        dir_name = self._get_resources_root_dir()
        if tmp_dir is None:
            tmp_dir = self.tmp_dir

        if os.path.exists(dir_name):
            if resource_type == resource_types["zip"]:
                return prepare_delta_zip(dir_name, resource_header, tmp_dir, self.task_resources)

            elif resource_type == resource_types["parts"]:
                return TaskResourceHeader.build_parts_header_delta_from_chosen(resource_header, dir_name,
                                                                               self.res_files)
            elif resource_type == resource_types["hashes"]:
                return copy.copy(self.task_resources)

        return None

    def update_task_state(self, task_state):
        pass

    @handle_key_error
    def get_trust_mod(self, subtask_id):
        return 1.0

    def add_resources(self, res_files):
        self.res_files = res_files

    def get_stderr(self, subtask_id):
        return self.stderr.get(subtask_id, "")

    def get_stdout(self, subtask_id):
        return self.stdout.get(subtask_id, "")

    def get_results(self, subtask_id):
        return self.results.get(subtask_id, [])

    #########################
    # Specific task methods #
    #########################

    def interpret_task_results(self, subtask_id, task_results, result_type):
        """ Change received results into a list of image files, filter out ".log" files that should
        represents stdout and stderr from computing machine.
        :param subtask_id: id of a subtask for which results are received
        :param task_results: it may be a list of files if result_type is equal to result_types["files"] or
        it may be a pickled zip file containing all files if result_type is equal to result_types["data"]
        :param result_type: a number from result_types, it may represents data format or files format
        :return: list of files that don't have .log extension
        """
        self.stdout[subtask_id] = ""
        self.stderr[subtask_id] = ""
        tr_files = self.load_task_results(task_results, result_type, subtask_id)
        self.results[subtask_id] = self.filter_task_results(tr_files, subtask_id)

    def result_incoming(self, subtask_id):
        self.counting_nodes[self.subtasks_given[subtask_id]['node_id']].finish()

    def query_extra_data_for_test_task(self):
        return None  # Implement in derived methods

    def load_task_results(self, task_result, result_type, subtask_id):
        """ Change results to a list of files. If result_type is equal to result_types["files"} this
        function only return task_results without making any changes. If result_type is equal to
        result_types["data"] tham task_result is unpickled and unzipped and files are saved in tmp_dir.
        :param task_result: list of files of pickles ziped file with files
        :param result_type: result_types element
        :param tmp_dir: directory where files should be written if result_type is equal to result_types["data"]
        :param str subtask_id:
        :return:
        """
        if result_type == result_types['data']:
            output_dir = os.path.join(self.tmp_dir, subtask_id)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            return [self._unpack_task_result(trp, output_dir) for trp in task_result]
        elif result_type == result_types['files']:
            return task_result
        else:
            logger.error("Task result type not supported {}".format(result_type))
            self.stderr[subtask_id] = "[GOLEM] Task result {} not supported".format(result_type)
            return []

    def filter_task_results(self, task_results, subtask_id, log_ext=".log", err_log_ext="err.log"):
        """ From a list of files received in task_results, return only files that don't have extension
        <log_ext> or <err_log_ext>. File with log_ext is saved as stdout for this subtask (only one file
        is currently supported). File with err_log_ext is save as stderr for this subtask (only one file is
        currently supported).
        :param list task_results: list of files
        :param str subtask_id: if of a given subtask
        :param str log_ext: extension that stdout files have
        :param str err_log_ext: extension that stderr files have
        :return:
        """

        filtered_task_results = []
        for tr in task_results:
            if tr.endswith(err_log_ext):
                self.stderr[subtask_id] = tr
            elif tr.endswith(log_ext):
                self.stdout[subtask_id] = tr
            else:
                try:
                    new_tr = outer_dir_path(tr)
                    if os.path.isfile(new_tr):
                        os.remove(new_tr)
                    os.rename(tr, new_tr)
                    filtered_task_results.append(new_tr)
                except (IOError, OSError) as err:
                    logger.warning("Problem with moving file {} to new location: {}".format(tr, err))

        return filtered_task_results

    def after_test(self, results, tmp_dir):
        return None

    def notify_update_task(self):
        for l in self.listeners:
            l.notify_update_task(self.header.task_id)

    @handle_key_error
    def should_accept(self, subtask_id):
        if self.subtasks_given[subtask_id]['status'] != SubtaskStatus.starting:
            return False
        return True

    @staticmethod
    def _interpret_log(log):
        if log is None:
            return ""
        if not os.path.isfile(log):
            return log
        try:
            with open(log) as f:
                res = f.read()
            return res
        except IOError as err:
            logger.error("Can't read file {}: {}".format(f, err))
            return ""

    @handle_key_error
    def _mark_subtask_failed(self, subtask_id):
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.failure
        self.counting_nodes[self.subtasks_given[subtask_id]['node_id']].reject()
        self.num_failed_subtasks += 1

    def _unpack_task_result(self, trp, output_dir):
        tr = pickle.loads(trp)
        with open(os.path.join(output_dir, tr[0]), "wb") as fh:
            fh.write(decompress(tr[1]))
        return os.path.join(output_dir, tr[0])

    def _get_resources_root_dir(self):
        prefix = os.path.commonprefix(self.task_resources)
        return os.path.dirname(prefix)
