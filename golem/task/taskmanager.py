import copy
import logging
import os
import pickle
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Iterable
from zipfile import ZipFile

from golem_messages.message import ComputeTaskDef
from pydispatch import dispatcher
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

from apps.appsmanager import AppsManager
from apps.core.task.coretask import CoreTask
from golem.core.common import HandleKeyError, get_timestamp_utc, \
    to_unicode, update_dict
from golem.manager.nodestatesnapshot import LocalTaskStateSnapshot
from golem.network.transport.tcpnetwork import SocketAddress
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resourcesmanager import \
    HyperdriveResourceManager
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.taskbase import TaskEventListener, Task
from golem.task.taskkeeper import CompTaskKeeper, compute_subtask_value
from golem.task.taskrequestorstats import RequestorTaskStatsManager
from golem.task.taskstate import TaskState, TaskStatus, SubtaskStatus, \
    SubtaskState, Operation, TaskOp, SubtaskOp, OtherOp

logger = logging.getLogger(__name__)


def log_subtask_key_error(*args, **kwargs):
    logger.warning("This is not my subtask %r", args[1])
    return None


def log_task_key_error(*args, **kwargs):
    logger.warning("This is not my task %r", args[1])
    return None


subtask_priority = {
    None: -1,
    SubtaskStatus.failure: 0,
    SubtaskStatus.restarted: 1,
    SubtaskStatus.resent: 2,
    SubtaskStatus.starting: 3,
    SubtaskStatus.downloading: 4,
    SubtaskStatus.finished: 5
}


class TaskManager(TaskEventListener):
    """ Keeps and manages information about requested tasks
    Requestor uses TaskManager to assign task to providers
    """
    handle_task_key_error = HandleKeyError(log_task_key_error)
    handle_subtask_key_error = HandleKeyError(log_subtask_key_error)

    class Error(Exception):
        pass

    class AlreadyRestartedError(Error):
        pass

    def __init__(
            self, node_name, node, keys_auth, listen_address="",
            listen_port=0, root_path="res", use_distributed_resources=True,
            tasks_dir="tasks", task_persistence=True,
            apps_manager=AppsManager(False)):
        super().__init__()

        self.apps_manager = apps_manager
        apps = list(apps_manager.apps.values())
        task_types = [app.task_type_info() for app in apps]
        self.task_types = {t.name.lower(): t for t in task_types}

        self.node_name = node_name
        self.node = node
        self.keys_auth = keys_auth
        self.key_id = keys_auth.key_id

        self.tasks = {}  # type: Dict[str, Task]
        self.tasks_states = {}  # type: Dict[str, TaskState]
        self.subtask2task_mapping = {}  # type: Dict[str, str]

        self.listen_address = listen_address
        self.listen_port = listen_port

        self.task_persistence = task_persistence

        tasks_dir = Path(tasks_dir)
        self.tasks_dir = tasks_dir / "tmanager"
        if not self.tasks_dir.is_dir():
            self.tasks_dir.mkdir(parents=True)
        self.root_path = root_path
        self.dir_manager = DirManager(self.get_task_manager_root())

        resource_manager = HyperdriveResourceManager(
            self.dir_manager,
            resource_dir_method=self.dir_manager.get_task_temporary_dir,
        )
        self.task_result_manager = EncryptedResultPackageManager(
            resource_manager
        )

        self.activeStatus = [TaskStatus.computing, TaskStatus.starting,
                             TaskStatus.waiting]
        self.use_distributed_resources = use_distributed_resources

        self.comp_task_keeper = CompTaskKeeper(
            tasks_dir,
            persist=self.task_persistence,
        )

        self.requestor_stats_manager = RequestorTaskStatsManager()

        if self.task_persistence:
            self.restore_tasks()

    def get_task_manager_root(self):
        return self.root_path

    def create_task(self, dictionary, minimal=False):
        type_name = dictionary['type'].lower()
        task_type = self.task_types[type_name]
        builder_type = task_type.task_builder_type

        definition = builder_type.build_definition(task_type, dictionary,
                                                   minimal)
        definition.task_id = CoreTask.create_task_id(self.keys_auth.public_key)
        builder = builder_type(self.node_name, definition, self.root_path,
                               self.dir_manager)

        return Task.build_task(builder)

    def get_task_definition_dict(self, task: Task):
        if isinstance(task, dict):
            return task
        definition = task.task_definition
        task_type = self.task_types[definition.task_type.lower()]
        return task_type.task_builder_type.build_dictionary(definition)

    def add_new_task(self, task):
        task_id = task.header.task_id
        if task_id in self.tasks:
            raise RuntimeError("Task {} has been already added"
                               .format(task.header.task_id))
        if not self.key_id:
            raise ValueError("'key_id' is not set")
        if not SocketAddress.is_proper_address(self.listen_address,
                                               self.listen_port):
            raise IOError("Incorrect socket address")

        task.header.task_owner_address = self.listen_address
        task.header.task_owner_port = self.listen_port
        task.header.task_owner_key_id = self.key_id
        task.header.task_owner = self.node
        task.header.signature = self.sign_task_header(task.header)

        task.create_reference_data_for_task_validation()
        task.register_listener(self)

        ts = TaskState()
        ts.status = TaskStatus.notStarted
        ts.outputs = task.get_output_names()
        ts.total_subtasks = task.get_total_tasks()
        ts.time_started = time.time()

        self.tasks[task_id] = task
        self.tasks_states[task_id] = ts
        logger.info("Task %s added", task_id)

        self.notice_task_updated(task_id,
                                 op=TaskOp.CREATED,
                                 persist=False)

    @handle_task_key_error
    def start_task(self, task_id):
        task_state = self.tasks_states[task_id]

        if task_state.status != TaskStatus.notStarted:
            raise RuntimeError("Task {} has already been started"
                               .format(task_id))

        task_state.status = TaskStatus.waiting
        self.notice_task_updated(task_id, op=TaskOp.STARTED)
        logger.info("Task %s started", task_id)

    def _dump_filepath(self, task_id):
        return self.tasks_dir / ('%s.pickle' % (task_id,))

    def dump_task(self, task_id: str) -> None:
        logger.debug('DUMP TASK %r', task_id)
        try:
            data = self.tasks[task_id], self.tasks_states[task_id]
            filepath = self._dump_filepath(task_id)
            logger.debug('DUMPING TASK %r', filepath)
            with filepath.open('wb') as f:
                pickle.dump(data, f, protocol=2)
            logger.debug('TASK %s DUMPED in %r', task_id, filepath)
        except Exception as e:
            logger.exception(
                'DUMP ERROR task_id: %r task: %r state: %r',
                task_id, self.tasks.get(task_id, '<not found>'),
                self.tasks_states.get(task_id, '<not found>'),
            )
            if filepath.exists():
                filepath.unlink()
            raise

    def remove_dump(self, task_id: str):
        filepath = self._dump_filepath(task_id)
        try:
            filepath.unlink()
            logger.debug('TASK DUMP with id %s REMOVED from %r',
                         task_id, filepath)
        except (FileNotFoundError, OSError) as e:
            logger.warning("Couldn't remove dump file: %s - %s", filepath, e)

    def restore_tasks(self) -> None:
        logger.debug('SEARCHING FOR TASKS TO RESTORE')
        broken_paths = set()
        for path in self.tasks_dir.iterdir():
            if not path.suffix == '.pickle':
                continue
            logger.debug('RESTORE TASKS %r', path)

            task_id = None
            with path.open('rb') as f:
                try:
                    task, state = pickle.load(f)
                    task.register_listener(self)

                    task_id = task.header.task_id
                    self.tasks[task_id] = task
                    self.tasks_states[task_id] = state

                    for sub in state.subtask_states.values():
                        self.subtask2task_mapping[sub.subtask_id] = task_id

                    logger.debug('TASK %s RESTORED from %r', task_id, path)
                except (pickle.UnpicklingError, EOFError, ImportError,
                        KeyError):
                    logger.exception('Problem restoring task from: %s', path)
                    # On Windows, attempting to remove a file that is in use
                    # causes an exception to be raised, therefore
                    # we'll remove broken files later
                    broken_paths.add(path)

            if task_id is not None:
                self.notice_task_updated(task_id, op=TaskOp.RESTORED,
                                         persist=False)

        for path in broken_paths:
            path.unlink()

    @handle_task_key_error
    def resources_send(self, task_id):
        self.tasks_states[task_id].status = TaskStatus.waiting
        self.notice_task_updated(task_id)
        logger.info("Resources for task {} sent".format(task_id))

    def got_wants_to_compute(self,
                             task_id: str,
                             key_id: str,  # pylint: disable=unused-argument
                             node_name: str):  # pylint: disable=unused-argument
        """
        Updates number of offers to compute task.

        For statistical purposes only, real processing of the offer is done
        elsewhere. Silently ignores wrong task ids.

        :param str task_id: id of the task in the offer
        :param key_id: id of the node offering computations
        :param node_name: name of the node offering computations
        :return: Nothing
        :rtype: None
        """
        if task_id in self.tasks:
            self.notice_task_updated(task_id,
                                     op=TaskOp.WORK_OFFER_RECEIVED,
                                     persist=False)

    def get_next_subtask(
            self, node_id, node_name, task_id, estimated_performance, price,
            max_resource_size, max_memory_size, num_cores=0, address=""):
        """ Assign next subtask from task <task_id> to node with given
        id <node_id> and name. If subtask is assigned the function
        is returning a tuple (
        :param node_id:
        :param node_name:
        :param task_id:
        :param estimated_performance:
        :param price:
        :param max_resource_size:
        :param max_memory_size:
        :param num_cores:
        :param address:
        :return (ComputeTaskDef|None, bool, bool): Function returns a triplet.
        First element is either ComputeTaskDef that describe assigned subtask
        or None. The second element describes whether the task_id is a wrong
        task that isn't in task manager register. If task with <task_id> it's
        a known task then second element of a pair is always False (regardless
        new subtask was assigned or not). The third element describes whether
        we're waiting for client's other task results.
        """
        logger.debug(
            'get_next_subtask(%r, %r, %r, %r, %r, %r, %r, %r, %r)',
            node_id, node_name, task_id, estimated_performance, price,
            max_resource_size, max_memory_size, num_cores, address,
        )
        if task_id not in self.tasks:
            logger.info("Cannot find task {} in my tasks".format(task_id))
            return None, True, False

        task = self.tasks[task_id]

        if task.header.max_price < price:
            return None, False, False

        def has_subtasks():
            if self.tasks_states[task_id].status not in self.activeStatus:
                logger.debug('state no in activestatus')
                return False
            if not task.needs_computation():
                logger.debug('not task.needs_computation')
                return False
            if task.header.resource_size > (int(max_resource_size) * 1024):
                logger.debug('resources size >')
                return False
            if task.header.estimated_memory > (int(max_memory_size) * 1024):
                logger.debug('estimated memory >')
                return False
            return True

        if not has_subtasks():
            logger.info(
                "Cannot get next task for estimated performance %r",
                estimated_performance,
            )
            return None, False, False

        extra_data = task.query_extra_data(
            estimated_performance,
            num_cores,
            node_id,
            node_name
        )
        if extra_data.should_wait:
            return None, False, True

        ctd = extra_data.ctd

        def check_compute_task_def():
            if not isinstance(ctd, ComputeTaskDef) or not ctd['subtask_id']:
                logger.debug('check ctd: ctd not instance or not subtask_id')
                return False
            if task_id != ctd['task_id'] \
                    or ctd['subtask_id'] in self.subtask2task_mapping:
                logger.debug(
                    'check ctd: %r != %r or %r in self.subtask2task_maping',
                    task_id, ctd['task_id'], ctd['subtask_id'],
                )
                return False
            if (ctd['subtask_id'] in self.tasks_states[ctd['task_id']].
                    subtask_states):
                logger.debug('check ctd: subtask_states')
                return False
            return True

        if not check_compute_task_def():
            return None, False, False

        self.subtask2task_mapping[ctd['subtask_id']] = task_id
        self.__add_subtask_to_tasks_states(
            node_name, node_id, price, ctd, address,
        )
        self.notice_task_updated(task_id,
                                 subtask_id=ctd['subtask_id'],
                                 op=SubtaskOp.ASSIGNED)
        return ctd, False, extra_data.should_wait

    def copy_results(
            self,
            old_task_id: str,
            new_task_id: str,
            subtask_ids_to_copy: Iterable[str]) -> None:

        try:
            old_task = self.tasks[old_task_id]
            new_task = self.tasks[new_task_id]
            assert isinstance(old_task, CoreTask)
            assert isinstance(new_task, CoreTask)
        except (KeyError, AssertionError):
            logger.exception(
                'Cannot copy results from task %r to %r',
                old_task_id, new_task_id)
            return

        # Map new subtasks to old by 'start_task'
        subtasks_to_copy = {
            subtask['start_task']: subtask for subtask in
            map(lambda id_: old_task.subtasks_given[id_], subtask_ids_to_copy)
        }

        # Generate all subtasks for the new task
        while new_task.needs_computation():
            extra_data = new_task.query_extra_data(0, node_id=str(uuid.uuid4()))
            self.subtask2task_mapping[extra_data.ctd['subtask_id']] = \
                new_task_id
            self.__add_subtask_to_tasks_states(
                node_name=None,
                node_id=None,
                address=None,
                comp_price=0,
                ctd=extra_data.ctd)

        for new_subtask_id, new_subtask in new_task.subtasks_given.items():
            old_subtask = subtasks_to_copy.get(new_subtask['start_task'])

            if old_subtask:  # Copy results from old subtask
                self._copy_subtask_results(
                    old_task=old_task,
                    new_task=new_task,
                    old_subtask=old_subtask,
                    new_subtask=new_subtask
                )

            else:  # Restart subtask to get it computed
                self.restart_subtask(new_subtask_id)

    def _copy_subtask_results(
            self,
            old_task: CoreTask,
            new_task: CoreTask,
            old_subtask: dict,
            new_subtask: dict) -> Deferred:

        old_task_id = old_task.header.task_id
        new_task_id = new_task.header.task_id
        assert isinstance(old_task.tmp_dir, str)
        assert isinstance(new_task.tmp_dir, str)
        old_tmp_dir = Path(old_task.tmp_dir)
        new_tmp_dir = Path(new_task.tmp_dir)
        old_subtask_id = old_subtask['subtask_id']
        new_subtask_id = new_subtask['subtask_id']

        def copy_and_extract_zips():
            # TODO: Refactor this using package manager (?)
            old_result_path = old_tmp_dir / '{}.{}.zip'.format(
                old_task_id, old_subtask_id)
            new_result_path = new_tmp_dir / '{}.{}.zip'.format(
                new_task_id, new_subtask_id)
            shutil.copy(old_result_path, new_result_path)

            subtask_result_dir = new_tmp_dir / new_subtask_id
            os.makedirs(subtask_result_dir)
            with ZipFile(new_result_path, 'r') as zf:
                zf.extractall(subtask_result_dir)
                return [
                    str(subtask_result_dir / name)
                    for name in zf.namelist()
                    if name != '.package_desc'
                ]

        def after_results_extracted(results):
            new_task.copy_subtask_results(
                new_subtask_id, old_subtask, results)

            new_subtask_state = \
                self.__set_subtask_state_finished(new_subtask_id)
            old_subtask_state = self.tasks_states[old_task_id] \
                .subtask_states[old_subtask_id]
            new_subtask_state.computer = \
                copy.deepcopy(old_subtask_state.computer)

            self.notice_task_updated(
                task_id=new_task_id,
                subtask_id=new_subtask_id,
                op=SubtaskOp.FINISHED)

        deferred = deferToThread(copy_and_extract_zips)
        deferred.addCallback(after_results_extracted)
        return deferred

    def get_tasks_headers(self):
        ret = []
        for tid, task in self.tasks.items():
            status = self.tasks_states[tid].status
            if task.needs_computation() and status in self.activeStatus:
                ret.append(task.header)

        return ret

    def get_trust_mod(self, subtask_id):
        if subtask_id in self.subtask2task_mapping:
            task_id = self.subtask2task_mapping[subtask_id]
            return self.tasks[task_id].get_trust_mod(subtask_id)
        else:
            logger.error("This is not my subtask {}".format(subtask_id))
            return 0

    def update_task_signatures(self):
        for task in list(self.tasks.values()):
            task.header.signature = self.sign_task_header(task.header)

    def sign_task_header(self, task_header):
        return self.keys_auth.sign(task_header.to_binary())

    def verify_subtask(self, subtask_id):
        if subtask_id in self.subtask2task_mapping:
            task_id = self.subtask2task_mapping[subtask_id]
            return self.tasks[task_id].verify_subtask(subtask_id)
        else:
            return False

    def get_node_id_for_subtask(self, subtask_id):
        if subtask_id not in self.subtask2task_mapping:
            return None
        task = self.subtask2task_mapping[subtask_id]
        subtask_state = self.tasks_states[task].subtask_states[subtask_id]
        return subtask_state.computer.node_id

    def set_value(self, task_id, subtask_id, value):
        if not isinstance(value, int):
            raise TypeError("Incorrect 'value' type: {}. Should be int"
                            .format(type(value)))
        task_state = self.tasks_states.get(task_id)
        if task_state is None:
            logger.warning("This is not my task {}".format(task_id))
            return
        subtask_state = task_state.subtask_states.get(subtask_id)
        if subtask_state is None:
            logger.warning("This is not my subtask {}".format(subtask_id))
            return
        subtask_state.value = value

    @handle_subtask_key_error
    def get_value(self, subtask_id):
        """ Return value of a given subtask
        :param subtask_id:  id of a computed subtask
        :return long: price that should be paid for given subtask
        """
        task_id = self.subtask2task_mapping[subtask_id]
        value = self.tasks_states[task_id].subtask_states[subtask_id].value
        return value

    @handle_subtask_key_error
    def computed_task_received(self, subtask_id, result, result_type,
                               verification_finished_):
        task_id = self.subtask2task_mapping[subtask_id]

        subtask_state = self.tasks_states[task_id].subtask_states[subtask_id]
        subtask_status = subtask_state.subtask_status

        if not SubtaskStatus.is_computed(subtask_status):
            logger.warning("Result for subtask {} when subtask state is {}"
                           .format(subtask_id, subtask_status))
            self.notice_task_updated(task_id,
                                     subtask_id=subtask_id,
                                     op=OtherOp.UNEXPECTED)
            verification_finished_()
            return
        subtask_state.subtask_status = SubtaskStatus.verifying

        def verification_finished():
            ss = self.__set_subtask_state_finished(subtask_id)

            if not self.tasks[task_id].verify_subtask(subtask_id):
                logger.debug("Subtask %r not accepted\n", subtask_id)
                ss.subtask_status = SubtaskStatus.failure
                self.notice_task_updated(
                    task_id,
                    subtask_id=subtask_id,
                    op=SubtaskOp.NOT_ACCEPTED)
                verification_finished_()
                return

            self.notice_task_updated(task_id,
                                     subtask_id=subtask_id,
                                     op=SubtaskOp.FINISHED)

            if self.tasks_states[task_id].status in self.activeStatus:
                if not self.tasks[task_id].finished_computation():
                    self.tasks_states[task_id].status = TaskStatus.computing
                else:
                    if self.tasks[task_id].verify_task():
                        logger.debug("Task %r accepted", task_id)
                        self.tasks_states[task_id].status = TaskStatus.finished
                        self.notice_task_updated(task_id, op=TaskOp.FINISHED)
                    else:
                        logger.debug("Task %r not accepted", task_id)
                        self.notice_task_updated(task_id,
                                                 op=TaskOp.NOT_ACCEPTED)

            verification_finished_()

        self.tasks[task_id].computation_finished(
            subtask_id, result, result_type, verification_finished
        )

    @handle_subtask_key_error
    def __set_subtask_state_finished(self, subtask_id: str) -> SubtaskState:
        task_id = self.subtask2task_mapping[subtask_id]
        ss = self.tasks_states[task_id].subtask_states[subtask_id]
        ss.subtask_progress = 1.0
        ss.subtask_rem_time = 0.0
        ss.subtask_status = SubtaskStatus.finished
        ss.stdout = self.tasks[task_id].get_stdout(subtask_id)
        ss.stderr = self.tasks[task_id].get_stderr(subtask_id)
        ss.results = self.tasks[task_id].get_results(subtask_id)
        return ss

    @handle_subtask_key_error
    def task_computation_failure(self, subtask_id, err):
        task_id = self.subtask2task_mapping[subtask_id]

        subtask_state = self.tasks_states[task_id].subtask_states[subtask_id]
        subtask_status = subtask_state.subtask_status

        if not SubtaskStatus.is_computed(subtask_status):
            logger.warning("Result for subtask {} when subtask state is {}"
                           .format(subtask_id, subtask_status))
            self.notice_task_updated(task_id,
                                     subtask_id=subtask_id,
                                     op=OtherOp.UNEXPECTED)
            return False

        self.tasks[task_id].computation_failed(subtask_id)
        ss = self.tasks_states[task_id].subtask_states[subtask_id]
        ss.subtask_progress = 1.0
        ss.subtask_rem_time = 0.0
        ss.subtask_status = SubtaskStatus.failure
        ss.stderr = str(err)

        self.notice_task_updated(task_id,
                                 subtask_id=subtask_id,
                                 op=SubtaskOp.FAILED)
        return True

    def task_result_incoming(self, subtask_id):
        node_id = self.get_node_id_for_subtask(subtask_id)

        if node_id and subtask_id in self.subtask2task_mapping:
            task_id = self.subtask2task_mapping[subtask_id]
            if task_id in self.tasks:
                task = self.tasks[task_id]
                states = self.tasks_states[task_id].subtask_states[subtask_id]

                task.result_incoming(subtask_id)
                states.subtask_status = SubtaskStatus.downloading

                self.notice_task_updated(
                    task_id,
                    subtask_id=subtask_id,
                    op=SubtaskOp.RESULT_DOWNLOADING)
            else:
                logger.error("Unknown task id: {}".format(task_id))
        else:
            logger.error("Node_id {} or subtask_id {} does not exist"
                         .format(node_id, subtask_id))

    # CHANGE TO RETURN KEY_ID (check IF SUBTASK COMPUTER HAS KEY_ID
    def check_timeouts(self):
        nodes_with_timeouts = []
        for t in list(self.tasks.values()):
            th = t.header
            if self.tasks_states[th.task_id].status not in self.activeStatus:
                continue
            cur_time = get_timestamp_utc()
            if cur_time > th.deadline:
                logger.info("Task {} dies".format(th.task_id))
                self.tasks_states[th.task_id].status = TaskStatus.timeout
                self.notice_task_updated(th.task_id, op=TaskOp.TIMEOUT)
            ts = self.tasks_states[th.task_id]
            for s in list(ts.subtask_states.values()):
                if SubtaskStatus.is_computed(s.subtask_status):
                    if cur_time > s.deadline:
                        logger.info("Subtask {} dies".format(s.subtask_id))
                        s.subtask_status = SubtaskStatus.failure
                        nodes_with_timeouts.append(s.computer.node_id)
                        t.computation_failed(s.subtask_id)
                        s.stderr = "[GOLEM] Timeout"
                        self.notice_task_updated(th.task_id,
                                                 subtask_id=s.subtask_id,
                                                 op=SubtaskOp.TIMEOUT)
        return nodes_with_timeouts

    def get_progresses(self):
        tasks_progresses = {}

        for t in list(self.tasks.values()):
            if t.get_progress() < 1.0:
                ltss = LocalTaskStateSnapshot(
                    t.header.task_id,
                    t.get_total_tasks(),
                    t.get_active_tasks(),
                    t.get_progress(),
                    t.short_extra_data_repr(2200.0)
                )  # FIXME in short_extra_data_repr should there be extra data
                # Issue #2460
                tasks_progresses[t.header.task_id] = ltss

        return tasks_progresses

    @handle_task_key_error
    def put_task_in_restarted_state(self, task_id, clear_tmp=True):
        """
        When restarting task, it's put in a final state 'restarted' and
        a new one is created.
        """
        task_state = self.tasks_states[task_id]
        if task_state.status == TaskStatus.restarted:
            raise self.AlreadyRestartedError()
        if clear_tmp:
            self.dir_manager.clear_temporary(task_id)

        task_state.status = TaskStatus.restarted
        for ss in self.tasks_states[task_id].subtask_states.values():
            if ss.subtask_status != SubtaskStatus.failure:
                ss.subtask_status = SubtaskStatus.restarted

        logger.info("Task %s put into restarted state", task_id)
        self.notice_task_updated(task_id, op=TaskOp.RESTARTED)

    @handle_subtask_key_error
    def restart_subtask(self, subtask_id):
        task_id = self.subtask2task_mapping[subtask_id]
        self.tasks[task_id].restart_subtask(subtask_id)
        task_state = self.tasks_states[task_id]
        task_state.status = TaskStatus.computing
        subtask_state = task_state.subtask_states[subtask_id]
        subtask_state.subtask_status = SubtaskStatus.restarted
        subtask_state.stderr = "[GOLEM] Restarted"

        self.notice_task_updated(task_id,
                                 subtask_id=subtask_id,
                                 op=SubtaskOp.RESTARTED)

    @handle_task_key_error
    def restart_frame_subtasks(self, task_id, frame):
        task = self.tasks[task_id]
        task_state = self.tasks_states[task_id]
        subtasks = task.get_subtasks(frame)

        if not subtasks:
            return

        for subtask_id in list(subtasks.keys()):
            task.restart_subtask(subtask_id)
            subtask_state = task_state.subtask_states[subtask_id]
            subtask_state.subtask_status = SubtaskStatus.restarted
            subtask_state.stderr = "[GOLEM] Restarted"
            self.notice_task_updated(task_id,
                                     subtask_id=subtask_id,
                                     op=SubtaskOp.RESTARTED,
                                     persist=False)

        task.status = TaskStatus.computing
        self.notice_task_updated(task_id, op=OtherOp.FRAME_RESTARTED)

    @handle_task_key_error
    def abort_task(self, task_id):
        self.tasks[task_id].abort()
        self.tasks_states[task_id].status = TaskStatus.aborted
        for sub in list(self.tasks_states[task_id].subtask_states.values()):
            del self.subtask2task_mapping[sub.subtask_id]
        self.tasks_states[task_id].subtask_states.clear()

        self.notice_task_updated(task_id, op=TaskOp.ABORTED)

    @handle_task_key_error
    def get_output_states(self, task_id):
        return self.tasks[task_id].get_output_states()

    @handle_task_key_error
    def delete_task(self, task_id):
        for sub in list(self.tasks_states[task_id].subtask_states.values()):
            del self.subtask2task_mapping[sub.subtask_id]
        self.tasks_states[task_id].subtask_states.clear()

        self.tasks[task_id].unregister_listener(self)
        del self.tasks[task_id]
        del self.tasks_states[task_id]

        self.dir_manager.clear_temporary(task_id)
        self.remove_dump(task_id)

    @handle_task_key_error
    def query_task_state(self, task_id):
        ts = self.tasks_states[task_id]
        t = self.tasks[task_id]

        ts.progress = t.get_progress()
        ts.elapsed_time = time.time() - ts.time_started

        if ts.progress > 0.0:
            proportion = (ts.elapsed_time / ts.progress)
            ts.remaining_time = proportion - ts.elapsed_time
        else:
            ts.remaining_time = None

        t.update_task_state(ts)

        return ts

    def get_subtasks(self, task_id) -> Optional[List[str]]:
        """
        Get all subtasks related to given task id
        :param task_id: Task ID
        :return: list of all subtasks related with @task_id or None
                 if @task_id is not known
        """
        task_state = self.tasks_states.get(task_id)
        if not task_state:
            return None

        subtask_states = list(task_state.subtask_states.values())
        return [subtask_state.subtask_id for subtask_state in subtask_states]

    def change_config(self, root_path, use_distributed_resource_management):
        self.dir_manager = DirManager(root_path)
        self.use_distributed_resources = use_distributed_resource_management

    def get_task_id(self, subtask_id):
        return self.subtask2task_mapping[subtask_id]

    def get_task_dict(self, task_id) -> Optional[Dict]:
        task = self.tasks.get(task_id)
        if not task:  # task might have been deleted after the request was made
            return None

        task_type_name = task.task_definition.task_type.lower()
        task_type = self.task_types[task_type_name]
        state = self.query_task_state(task.header.task_id)
        timeout = task.task_definition.full_task_timeout

        dictionary = {
            'duration': max(timeout - (state.remaining_time or 0), 0),
            # single=True retrieves one preview file. If rendering frames,
            # it's the preview of the most recently computed frame.
            'preview': task_type.get_preview(task, single=True)
        }

        return update_dict(dictionary,
                           task.to_dictionary(),
                           state.to_dictionary(),
                           self.get_task_definition_dict(task))

    def get_tasks_dict(self) -> List[Dict]:
        task_ids = list(self.tasks.keys())
        mapped = map(self.get_task_dict, task_ids)
        filtered = filter(None, mapped)
        return list(filtered)

    def get_subtask_dict(self, subtask_id):
        task_id = self.subtask2task_mapping[subtask_id]
        task_state = self.tasks_states[task_id]
        subtask = task_state.subtask_states[subtask_id]
        return subtask.to_dictionary()

    def get_subtasks_dict(self, task_id):
        task_state = self.tasks_states[task_id]
        subtasks = task_state.subtask_states
        return [subtask.to_dictionary() for subtask in subtasks.values()]

    def get_subtasks_borders(self, task_id, part=1):
        task = self.tasks[task_id]
        task_type_name = task.task_definition.task_type.lower()
        task_type = self.task_types[task_type_name]
        total_subtasks = task.get_total_tasks()

        return {
            to_unicode(subtask_id): task_type.get_task_border(
                subtask, task.task_definition, total_subtasks, as_path=True
            ) for subtask_id, subtask in task.get_subtasks(part).items()
        }

    def get_task_preview(self, task_id, single=False):
        task = self.tasks[task_id]
        task_type_name = task.task_definition.task_type.lower()
        task_type = self.task_types[task_type_name]
        return task_type.get_preview(task, single=single)

    @handle_subtask_key_error
    def set_computation_time(self, subtask_id, computation_time):
        """
        Set computation time for subtask and also compute and set new value
        based on saved price for this subtask
        :param str subtask_id: subtask which was computed in given
                               computation_time
        :param float computation_time: how long does it take to compute
        this task = max timeout

        :return:
        """
        task_id = self.subtask2task_mapping[subtask_id]

        # Max computation time should be in range [0;timeout]
        timeout = self.tasks[task_id].task_definition.subtask_timeout
        if computation_time > timeout:
            logger.warning(
                'Received computation time (%r) for subtask %r exceeds subtask '
                'timeout (%r)', computation_time, subtask_id, timeout)
            computation_time = timeout
        if computation_time < 0:
            logger.warning(
                'Received computation time (%r) for subtask %r is lower than 0',
                computation_time, subtask_id)
            computation_time = 0

        ss = self.tasks_states[task_id].subtask_states[subtask_id]
        ss.computation_time = computation_time
        ss.value = compute_subtask_value(ss.computer.price, computation_time)

    def add_comp_task_request(self, theader, price):
        """ Add a header of a task which this node may try to compute """
        self.comp_task_keeper.add_request(theader, price)

    @handle_task_key_error
    def get_payment_for_task_id(self, task_id):
        val = 0.0
        t = self.tasks_states[task_id]
        for ss in list(t.subtask_states.values()):
            val += ss.value
        return val

    def get_estimated_cost(self, task_type, options):
        try:
            subtask_value = options['price'] * options['subtask_time']
            return options['num_subtasks'] * subtask_value
        except (KeyError, ValueError):
            logger.exception("Cannot estimate price, wrong params")
            return None

    def __add_subtask_to_tasks_states(self, node_name, node_id, comp_price,
                                      ctd, address):

        logger.debug('add_subtask_to_tasks_states(%r, %r, %r, %r, %r)',
                     node_name, node_id, comp_price, ctd, address)

        price = self.tasks[ctd['task_id']].header.max_price

        ss = SubtaskState()
        ss.computer.node_id = node_id
        ss.computer.node_name = node_name
        ss.computer.performance = ctd['performance']
        ss.computer.ip_address = address
        ss.computer.price = price
        ss.time_started = time.time()
        ss.deadline = ctd['deadline']
        ss.subtask_definition = ctd['short_description']
        ss.subtask_id = ctd['subtask_id']
        ss.extra_data = ctd['extra_data']
        ss.subtask_status = TaskStatus.starting
        ss.value = 0

        (self.tasks_states[ctd['task_id']].
            subtask_states[ctd['subtask_id']]) = ss

    def notify_update_task(self, task_id):
        self.notice_task_updated(task_id)

    @handle_task_key_error
    def notice_task_updated(self, task_id: str, subtask_id: str = None,
                            op: Operation = None, persist: bool = True):
        """Called when a task is modified, saves the task and
        propagates information

        Whenever task is changed `notice_task_updated` should be called
        to save the task - if the change is save-worthy, as specified
        by the `persist` parameter - and propagate information about
        changed task to other parts of the system.

        Most of the calls are save-worthy, but a minority is not: for
        instance when the work offer is received, the task does not
        change so saving it does not make sense, but it still makes
        sense to let other parts of the system know about the change.
        Also, when a number of minor changes are always followed by a
        major one, as it is with restarting a frame task, it does not
        make sense to store all the partial changes, so only the
        final one is considered save-worthy.

        :param str task_id: id of the updated task
        :param str subtask_id: if the operation done on the
          task is related to a subtask, id of that subtask
        :param Operation op: performed operation
        :param bool persist: should the task be persisted now
        """
        # self.save_state()
        if persist and self.task_persistence:
            self.dump_task(task_id)
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id=task_id,
            task_state=self.tasks_states.get(task_id),
            subtask_id=subtask_id,
            op=op,
        )
