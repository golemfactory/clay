import copy
import logging
import os
import pickle
import shutil
import time
import uuid
from functools import partial
from pathlib import Path
from typing import Optional, Dict, List, Iterable
from zipfile import ZipFile

from golem_messages.message import ComputeTaskDef
from pydispatch import dispatcher
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

from apps.appsmanager import AppsManager
from apps.core.task.coretask import CoreTask, AcceptClientVerdict
from golem.core.common import HandleKeyError, get_timestamp_utc, \
    to_unicode, update_dict, HandleForwardedError
from golem.manager.nodestatesnapshot import LocalTaskStateSnapshot
from golem.network.transport.tcpnetwork import SocketAddress
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resourcesmanager import \
    HyperdriveResourceManager
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.taskbase import TaskEventListener, Task, TaskHeader, TaskPurpose
from golem.task.taskkeeper import CompTaskKeeper
from golem.task.taskrequestorstats import RequestorTaskStatsManager
from golem.task.taskstate import TaskState, TaskStatus, SubtaskStatus, \
    SubtaskState, Operation, TaskOp, SubtaskOp, OtherOp

logger = logging.getLogger(__name__)


def log_subtask_key_error(*args, **kwargs):
    logger.warning("This is not my subtask %r", args[1])
    return None


def log_generic_key_error(err):
    logger.warning("Subtask key error: %r", err)
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
    handle_generic_key_error = HandleForwardedError(KeyError,
                                                    log_generic_key_error)

    class Error(Exception):
        pass

    class AlreadyRestartedError(Error):
        pass

    def __init__(
            self, node_name, node, keys_auth, listen_address="",
            listen_port=0, root_path="res", use_distributed_resources=True,
            tasks_dir="tasks", task_persistence=True,
            apps_manager=AppsManager(), finished_cb=None):
        super().__init__()

        self.apps_manager = apps_manager
        apps = list(apps_manager.apps.values())
        task_types = [app.task_type_info() for app in apps]
        self.task_types = {t.name.lower(): t for t in task_types}

        self.node_name = node_name
        self.node = node
        self.keys_auth = keys_auth
        self.key_id = keys_auth.key_id

        self.tasks: Dict[str, Task] = {}
        self.tasks_states: Dict[str, TaskState] = {}
        self.subtask2task_mapping: Dict[str, str] = {}

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

        self.finished_cb = finished_cb

        if self.task_persistence:
            self.restore_tasks()

    def get_task_manager_root(self):
        return self.root_path

    def create_task(self, dictionary, minimal=False):
        purpose = TaskPurpose.TESTING if minimal else TaskPurpose.REQUESTING
        type_name = dictionary['type'].lower()
        compute_on = dictionary.get('compute_on', 'cpu').lower()
        is_requesting = purpose == TaskPurpose.REQUESTING

        if type_name == "blender" and is_requesting and compute_on == "gpu":
            type_name = type_name + "_nvgpu"

        task_type = self.task_types[type_name].for_purpose(purpose)
        builder_type = task_type.task_builder_type

        definition = builder_type.build_definition(task_type, dictionary,
                                                   minimal)
        definition.task_id = CoreTask.create_task_id(self.keys_auth.public_key)
        definition.concent_enabled = dictionary['concent_enabled']
        builder = builder_type(self.node, definition, self.dir_manager)

        return builder.build()

    def get_task_definition_dict(self, task: Task):
        if isinstance(task, dict):
            return task
        definition = task.task_definition
        task_type = self.task_types[definition.task_type.lower()]
        return task_type.task_builder_type.build_dictionary(definition)

    def add_new_task(self, task: Task, estimated_fee: int = 0) -> None:
        task_id = task.header.task_id
        if task_id in self.tasks:
            raise RuntimeError("Task {} has been already added"
                               .format(task.header.task_id))
        if not self.key_id:
            raise ValueError("'key_id' is not set")
        if not SocketAddress.is_proper_address(self.listen_address,
                                               self.listen_port):
            raise IOError("Incorrect socket address: %s:%s" % (
                self.listen_address, self.listen_port))

        task.header.fixed_header.task_owner = self.node
        task.header.signature = self.sign_task_header(task.header)

        task.create_reference_data_for_task_validation()
        task.register_listener(self)

        ts = TaskState()
        ts.status = TaskStatus.notStarted
        ts.outputs = task.get_output_names()
        ts.total_subtasks = task.get_total_tasks()
        ts.time_started = time.time()
        ts.estimated_cost = task.price
        ts.estimated_fee = estimated_fee

        self.tasks[task_id] = task
        self.tasks_states[task_id] = ts
        logger.info("Task %s added", task_id)

        self.notice_task_updated(task_id,
                                 op=TaskOp.CREATED,
                                 persist=False)

    @handle_task_key_error
    def increase_task_mask(self, task_id: str, num_bits: int = 1) -> None:
        """ Increase mask for given task i.e. make it more restrictive """
        task = self.tasks[task_id]
        try:
            task.header.mask.increase(num_bits)
        except ValueError:
            logger.exception('Wrong number of bits for mask increase')
        else:
            task.header.signature = self.sign_task_header(task.header)

    @handle_task_key_error
    def decrease_task_mask(self, task_id: str, num_bits: int = 1) -> None:
        """ Decrease mask for given task i.e. make it less restrictive """
        task = self.tasks[task_id]
        try:
            task.header.mask.decrease(num_bits)
        except ValueError:
            logger.exception('Wrong number of bits for mask decrease')
        else:
            task.header.signature = self.sign_task_header(task.header)

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
        filepath = self._dump_filepath(task_id)
        try:
            data = self.tasks[task_id], self.tasks_states[task_id]
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

    @staticmethod
    def _migrate_status_to_enum(state: TaskState) -> None:
        """
        This is a migration for data stored in pickles.
        See #2768
        """
        if isinstance(state.status, str):
            state.status = TaskStatus(state.status)

        subtask_state: SubtaskState
        for subtask_state in state.subtask_states.values():
            if isinstance(subtask_state.subtask_status, str):
                subtask_state.subtask_status = \
                    SubtaskStatus(subtask_state.subtask_status)

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
                    task: Task
                    state: TaskState
                    task, state = pickle.load(f)

                    TaskManager._migrate_status_to_enum(state)

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

    def task_needs_computation(self, task_id: str) -> bool:
        task_status = self.tasks_states[task_id].status
        if task_status not in self.activeStatus:
            logger.info(
                f'task is not active: {task_id}, status: {task_status}')
            return False
        task = self.tasks[task_id]
        if not task.needs_computation():
            logger.info(f'no more computation needed: {task_id}')
            return False
        return True

    def get_next_subtask(
            self, node_id, node_name, task_id, estimated_performance, price,
            max_resource_size, max_memory_size, num_cores=0, address=""):
        """ Assign next subtask from task <task_id> to node with given
        id <node_id> and name. If subtask is assigned the function
        is returning a tuple
        :param node_id:
        :param node_name:
        :param task_id:
        :param estimated_performance:
        :param price:
        :param max_resource_size:
        :param max_memory_size:
        :param num_cores:
        :param address:
        :return (ComputeTaskDef|None: Function returns a ComputeTaskDef.
        First element is either ComputeTaskDef that describe assigned subtask
        or None. It is recommended to call is_my_task and should_wait_for_node
        before this to find the reason why the task is not able to be picked up
        """
        logger.debug(
            'get_next_subtask(%r, %r, %r, %r, %r, %r, %r, %r, %r)',
            node_id, node_name, task_id, estimated_performance, price,
            max_resource_size, max_memory_size, num_cores, address,
        )

        if not self.is_my_task(task_id):
            return None

        if not self.check_next_subtask(node_id, node_name, task_id, price):
            return None

        if self.should_wait_for_node(task_id, node_id):
            return None

        task = self.tasks[task_id]

        if task.get_progress() == 1.0:
            logger.error("Task already computed. "
                         "task_id=%r, node_name=%r, node_id=%r",
                         task_id, node_name, node_id)
            return None

        extra_data = task.query_extra_data(
            estimated_performance,
            num_cores,
            node_id,
            node_name
        )
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
            return None

        task.accept_client(node_id)

        self.subtask2task_mapping[ctd['subtask_id']] = task_id
        self.__add_subtask_to_tasks_states(
            node_name, node_id, ctd, address,
        )
        self.notice_task_updated(task_id,
                                 subtask_id=ctd['subtask_id'],
                                 op=SubtaskOp.ASSIGNED)
        return ctd

    def is_my_task(self, task_id) -> bool:
        """ Check if the task_id is known by this node """
        return task_id in self.tasks

    def should_wait_for_node(self, task_id, node_id) -> bool:
        """ Check if the node has too many tasks assigned already """
        if not self.is_my_task(task_id):
            return False

        task = self.tasks[task_id]

        verdict = task.should_accept_client(node_id)
        if verdict == AcceptClientVerdict.SHOULD_WAIT:
            logger.warning("Waiting for results from %s on %s", node_id,
                           task_id)
            return True
        elif verdict == AcceptClientVerdict.REJECTED:
            logger.warning("Client %s has failed on subtask within task %s"
                           " and is banned from it", node_id, task_id)

        return False

    def check_next_subtask(  # noqa pylint: disable=too-many-arguments
            self, node_id, node_name, task_id, price):
        """ Check next subtask from task <task_id> to give to node with
        id <node_id> and name. The returned tuple can be used to find the reason
        and handle accordingly.
        :param node_id:
        :param node_name:
        :param task_id:
        :param price:
        :return bool: Function returns a boolean.
        The return value describes if the task is able to be assigned
        """
        logger.debug(
            'check_next_subtask(%r, %r, %r, %r)',
            node_id, node_name, task_id, price,
        )
        if not self.is_my_task(task_id):
            logger.info("Cannot find task in my tasks. task_id=%r", task_id)
            return False

        task = self.tasks[task_id]

        if task.header.max_price < price:
            return False

        if not self.task_needs_computation(task_id):
            logger.info('Task does not need computation. provider=%r - %r',
                        node_name, node_id)
            return False

        return True

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
        new_subtasks_ids = []
        while new_task.needs_computation():
            extra_data = new_task.query_extra_data(0, node_id=str(uuid.uuid4()))
            new_subtask_id = extra_data.ctd['subtask_id']
            self.subtask2task_mapping[new_subtask_id] = \
                new_task_id
            self.__add_subtask_to_tasks_states(
                node_name=None,
                node_id=None,
                address=None,
                ctd=extra_data.ctd)
            new_subtasks_ids.append(new_subtask_id)

        # it's important to do this step separately, to not disturb
        # 'needs_computation' condition above
        for new_subtask_id in new_subtasks_ids:
            self.tasks_states[new_task_id].subtask_states[new_subtask_id]\
                .subtask_status = SubtaskStatus.failure
            new_task.subtasks_given[new_subtask_id]['status'] \
                = SubtaskStatus.failure
            new_task.num_failed_subtasks += 1

        def handle_copy_error(subtask_id, error):
            logger.error(
                'Cannot copy result of subtask %r: %r', subtask_id, error)
            self.restart_subtask(subtask_id)

        for new_subtask_id, new_subtask in new_task.subtasks_given.items():
            old_subtask = subtasks_to_copy.get(new_subtask['start_task'])

            if old_subtask:  # Copy results from old subtask
                deferred = self._copy_subtask_results(
                    old_task=old_task,
                    new_task=new_task,
                    old_subtask=old_subtask,
                    new_subtask=new_subtask
                )
                deferred.addErrback(partial(handle_copy_error, new_subtask_id))

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

    def is_this_my_task(self, header: TaskHeader) -> bool:
        return header.task_id in self.tasks or \
               header.task_owner.key == self.node.key

    def get_node_id_for_subtask(self, subtask_id):
        if subtask_id not in self.subtask2task_mapping:
            return None
        task = self.subtask2task_mapping[subtask_id]
        subtask_state = self.tasks_states[task].subtask_states[subtask_id]
        return subtask_state.computer.node_id

    @handle_subtask_key_error
    def set_subtask_value(self, subtask_id: str, price: int) -> None:
        """Set price for a subtask"""
        task_id = self.subtask2task_mapping[subtask_id]

        ss = self.tasks_states[task_id].subtask_states[subtask_id]
        ss.value = price

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
                               verification_finished):
        task_id = self.subtask2task_mapping[subtask_id]

        subtask_state = self.tasks_states[task_id].subtask_states[subtask_id]
        subtask_status = subtask_state.subtask_status

        if not subtask_status.is_computed():
            logger.warning("Result for subtask {} when subtask state is {}"
                           .format(subtask_id, subtask_status.value))
            self.notice_task_updated(task_id,
                                     subtask_id=subtask_id,
                                     op=OtherOp.UNEXPECTED)
            verification_finished()
            return
        subtask_state.subtask_status = SubtaskStatus.verifying

        @TaskManager.handle_generic_key_error
        def verification_finished_():
            ss = self.__set_subtask_state_finished(subtask_id)
            if not self.tasks[task_id].verify_subtask(subtask_id):
                logger.debug("Subtask %r not accepted\n", subtask_id)
                ss.subtask_status = SubtaskStatus.failure
                self.notice_task_updated(
                    task_id,
                    subtask_id=subtask_id,
                    op=SubtaskOp.NOT_ACCEPTED)
                verification_finished()
                return

            self.notice_task_updated(task_id,
                                     subtask_id=subtask_id,
                                     op=SubtaskOp.FINISHED)

            if self.tasks_states[task_id].status in self.activeStatus:
                if not self.tasks[task_id].finished_computation():
                    self.tasks_states[task_id].status = TaskStatus.computing
                else:
                    if self.tasks[task_id].verify_task():
                        logger.info("Task finished! task_id=%r", task_id)
                        self.tasks_states[task_id].status =\
                            TaskStatus.finished
                        self.notice_task_updated(task_id,
                                                 op=TaskOp.FINISHED)
                    else:
                        logger.warning("Task finished but was not accepted. "
                                       "task_id=%r", task_id)
                        self.notice_task_updated(task_id,
                                                 op=TaskOp.NOT_ACCEPTED)
            verification_finished()

        self.tasks[task_id].computation_finished(
            subtask_id, result, result_type, verification_finished_
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

        if not subtask_status.is_computed():
            logger.warning("Result for subtask {} when subtask state is {}"
                           .format(subtask_id, subtask_status.value))
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
            # Check subtask timeout
            ts = self.tasks_states[th.task_id]
            for s in list(ts.subtask_states.values()):
                if s.subtask_status.is_computed():
                    if cur_time > s.deadline:
                        logger.info("Subtask %r dies with status %r",
                                    s.subtask_id,
                                    s.subtask_status.value)
                        s.subtask_status = SubtaskStatus.failure
                        nodes_with_timeouts.append(s.computer.node_id)
                        t.computation_failed(s.subtask_id)
                        s.stderr = "[GOLEM] Timeout"
                        self.notice_task_updated(th.task_id,
                                                 subtask_id=s.subtask_id,
                                                 op=SubtaskOp.TIMEOUT)
            # Check task timeout
            if cur_time > th.deadline:
                logger.info("Task %r dies", th.task_id)
                self.tasks_states[th.task_id].status = TaskStatus.timeout
                # TODO: t.tell_it_has_timeout()?
                self.notice_task_updated(th.task_id, op=TaskOp.TIMEOUT)
        return nodes_with_timeouts

    def get_progresses(self):
        tasks_progresses = {}

        for t in list(self.tasks.values()):
            task_id = t.header.task_id
            task_state = self.tasks_states[task_id]
            task_status = task_state.status
            in_progress = not TaskStatus.is_completed(task_status)
            logger.info('Collecting progress %r %r %r',
                        task_id, task_status, in_progress)
            if in_progress:
                ltss = LocalTaskStateSnapshot(
                    task_id,
                    t.get_total_tasks(),
                    t.get_active_tasks(),
                    t.get_progress(),
                    t.short_extra_data_repr(task_state.extra_data)
                )  # FIXME in short_extra_data_repr should there be extra data
                # Issue #2460
                tasks_progresses[task_id] = ltss

        return tasks_progresses

    @handle_task_key_error
    def assert_task_can_be_restarted(self, task_id: str) -> None:
        task_state = self.tasks_states[task_id]
        if task_state.status == TaskStatus.restarted:
            raise self.AlreadyRestartedError()

    @handle_task_key_error
    def put_task_in_restarted_state(self, task_id, clear_tmp=True):
        """
        When restarting task, it's put in a final state 'restarted' and
        a new one is created.
        """
        self.assert_task_can_be_restarted(task_id)
        if clear_tmp:
            self.dir_manager.clear_temporary(task_id)

        task_state = self.tasks_states[task_id]
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

        task_state.status = TaskStatus.computing
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
        if self.finished_cb:
            self.finished_cb()

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

    def get_frame_subtasks(self, task_id: str, frame) \
            -> Optional[Dict[str, SubtaskState]]:
        task: Optional[Task] = self.tasks.get(task_id)
        if not task:
            return None
        if not isinstance(task, CoreTask):
            return None
        return task.get_subtasks(frame)

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

        dictionary = {
            'duration': state.elapsed_time,
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
        if subtasks:
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

    def __add_subtask_to_tasks_states(self, node_name, node_id,
                                      ctd, address):

        logger.debug('add_subtask_to_tasks_states(%r, %r, %r, %r)',
                     node_name, node_id, ctd, address)

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
        ss.subtask_status = SubtaskStatus.starting
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

        task_state = self.tasks_states.get(task_id)
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id=task_id,
            task_state=task_state,
            subtask_id=subtask_id,
            op=op,
        )

        if self.finished_cb and persist and op \
                and op.task_related() and op.is_completed():
            self.finished_cb()
