from datetime import datetime
import decimal
import logging
import os
import time
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TYPE_CHECKING,
)

from ethereum.utils import denoms
from golem_messages import idgenerator
from golem_messages.datastructures import tasks as dt_tasks
import golem_messages.message

from apps.core.verification_queue import VerificationQueue
from golem import constants as gconst
from golem.core.common import HandleKeyError, timeout_to_deadline, to_unicode, \
    string_to_timeout
from golem.core.fileshelper import outer_dir_path
from golem.docker.environment import DockerEnvironment
# importing DirManager could be under "if TYPE_CHECKING", but it's needed here
# for validation by 'enforce'
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task, TaskBuilder, \
    TaskTypeInfo, AcceptClientVerdict
from golem.task.taskbase import TaskResult
from golem.task.taskclient import TaskClient
from golem.task.taskstate import SubtaskStatus
from golem.verifier.subtask_verification_state import SubtaskVerificationState
from golem.verifier.core_verifier import CoreVerifier

from .coretaskstate import RunVerification


if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from golem_messages.datastructures import p2p as dt_p2p
    from .coretaskstate import TaskDefinition, Options
    from golem.environments.environment import Environment


logger = logging.getLogger("apps.core")


def log_key_error(*args, **_):
    logger.warning("This is not my subtask %s", args[1], exc_info=True)
    return False


class CoreTaskTypeInfo(TaskTypeInfo):
    """ Information about task that allows to define and build a new task,
    display outputs and previews. """

    # pylint:disable=too-many-arguments
    def __init__(self,
                 name: str,
                 definition: 'Type[TaskDefinition]',
                 options: 'Type[Options]',
                 builder_type: Type[TaskBuilder]):
        super().__init__(name, definition, options, builder_type)
        self.output_formats = []
        self.output_file_ext = []

    @classmethod
    # pylint:disable=unused-argument
    def get_task_border(cls, extra_data, definition, subtasks_count,
                        as_path=False):
        return []

    @classmethod
    # pylint:disable=unused-argument
    def get_preview(cls, task, single=False):
        pass

    # pylint:disable=no-else-return
    @staticmethod
    def _preview_result(result, single=False):
        if single:
            return result
        if result is not None:
            if isinstance(result, dict):
                return result
            else:
                return {'1': result}
        return {}


# pylint:disable=too-many-instance-attributes,too-many-public-methods
class CoreTask(Task):
    VERIFIER_CLASS: Type[CoreVerifier] = CoreVerifier
    VERIFICATION_QUEUE = VerificationQueue()

    ENVIRONMENT_CLASS: 'Type[Environment]'

    handle_key_error = HandleKeyError(log_key_error)

    ################
    # Task methods #
    ################

    # pylint:disable=too-many-arguments
    def __init__(self,
                 task_definition: 'TaskDefinition',
                 owner: 'dt_p2p.Node',
                 resource_size=None,
                 root_path=None):
        """Create more specific task implementation
        """

        task_timeout = task_definition.timeout
        self._deadline = timeout_to_deadline(task_timeout)

        # resources stuff
        self.task_resources = list(
            set(filter(os.path.exists, task_definition.resources)))
        if resource_size is None:
            self.resource_size = 0
            for resource in self.task_resources:
                self.resource_size += os.stat(resource).st_size
        else:
            self.resource_size = resource_size

        # pylint: disable=not-callable
        self.environment = self.ENVIRONMENT_CLASS()

        # docker_images stuff
        if task_definition.docker_images:
            self.docker_images = task_definition.docker_images
        elif isinstance(self.environment, DockerEnvironment):
            # pylint: disable=no-member
            self.docker_images = self.environment.docker_images
        else:
            self.docker_images = None

        th = dt_tasks.TaskHeader(
            min_version=str(gconst.GOLEM_MIN_VERSION),
            task_id=task_definition.task_id,
            environment=self.environment.get_id(),
            task_owner=owner,
            deadline=self._deadline,
            subtask_timeout=task_definition.subtask_timeout,
            subtasks_count=task_definition.subtasks_count,
            subtask_budget=self.calculate_subtask_budget(task_definition),
            estimated_memory=task_definition.estimated_memory,
            max_price=task_definition.max_price,
            concent_enabled=task_definition.concent_enabled,
            timestamp=int(time.time()),
        )

        logger.debug(
            "CoreTask TaskHeader "
            "task_id=%s, environment=%s, deadline=%s, "
            "subtask_timeout=%s, subtasks_count=%s, subtask_budget=%s, "
            "estimated_memory=%s, "
            "max_price=%s, "
            "concent_enabled=%s, ",
            th.task_id, th.environment, th.deadline,
            th.subtask_timeout, th.subtasks_count, th.subtask_budget,
            th.estimated_memory,
            th.max_price,
            th.concent_enabled,
        )

        Task.__init__(self, th, task_definition)

        self.last_task = 0

        self.num_tasks_received = 0
        self.subtasks_given: Dict[str, Dict[str, Any]] = {}
        self.num_failed_subtasks = 0

        self.timeout = task_timeout
        self.counting_nodes = {}

        self.root_path = root_path
        # for each subtask keep info about stdout received from computing node
        self.stdout: Dict[str, str] = {}
        # for each subtask keep info about stderr received from computing node
        self.stderr: Dict[str, str] = {}
        # for each subtask keep info about files containing results
        self.results: Dict[str, list] = {}

        self.res_files = {}
        self.tmp_dir = None

    @staticmethod
    def create_task_id(public_key: bytes) -> str:
        return idgenerator.generate_id(public_key)

    def create_subtask_id(self) -> str:
        return idgenerator.generate_new_id_from_id(self.header.task_id)

    def is_docker_task(self):
        return bool(self.docker_images)

    def initialize(self, dir_manager: DirManager) -> None:
        dir_manager.clear_temporary(self.header.task_id)
        self.tmp_dir = dir_manager.get_task_temporary_dir(self.header.task_id,
                                                          create=True)

    def needs_computation(self):
        return (self.last_task != self.get_total_tasks()) or \
               (self.num_failed_subtasks > 0)

    def finished_computation(self):
        return self.num_tasks_received == self.get_total_tasks()

    def computation_failed(self, subtask_id: str, ban_node: bool = True):
        self._mark_subtask_failed(subtask_id, ban_node)

    def computation_finished(self, subtask_id: str, task_result: TaskResult,
                             verification_finished: Callable[[], None]) -> None:
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.verifying
        self.interpret_task_results(subtask_id, task_result)
        result_files = self.results.get(subtask_id)

        def verification_finished_(subtask_id,
                                   verdict: SubtaskVerificationState, result):
            self.verification_finished(subtask_id, verdict, result)
            verification_finished()

        if self.task_definition.run_verification == RunVerification.disabled:
            logger.debug("verification disabled; calling verification_finished."
                         " subtask_id=%s", subtask_id)
            result = {'extra_data': {'results': result_files}}
            verification_finished_(
                subtask_id, SubtaskVerificationState.VERIFIED, result)
            return

        self.VERIFICATION_QUEUE.submit(
            self.VERIFIER_CLASS,
            subtask_id,
            self._deadline,
            verification_finished_,
            subtask_info={**self.subtasks_given[subtask_id],
                          **{'owner': self.header.task_owner.key}},
            results=result_files,
            resources=self.task_resources,
        )

    def verification_finished(self, subtask_id,
                              verdict: SubtaskVerificationState, result):
        try:
            if verdict == SubtaskVerificationState.VERIFIED:
                self.accept_results(subtask_id, result['extra_data']['results'])
            # TODO Add support for different verification states. issue #2422
            else:
                self.computation_failed(subtask_id)
        except Exception as exc:
            logger.warning("Failed during accepting results %s", exc)

    # pylint:disable=unused-argument
    def accept_results(self, subtask_id, result_files):
        subtask = self.subtasks_given[subtask_id]
        if "status" not in subtask:
            raise Exception("Subtask {} hasn't started".format(subtask_id))
        if subtask.get("status", None) == SubtaskStatus.finished:
            raise Exception("Subtask {} already accepted".format(subtask_id))
        if subtask.get("status", None) not in [SubtaskStatus.starting,
                                               SubtaskStatus.downloading,
                                               SubtaskStatus.verifying,
                                               SubtaskStatus.resent,
                                               SubtaskStatus.finished,
                                               SubtaskStatus.failure,
                                               SubtaskStatus.restarted]:
            raise Exception("Subtask {} has wrong type".format(subtask_id))

        subtask["status"] = SubtaskStatus.finished
        node_id = self.subtasks_given[subtask_id]['node_id']
        TaskClient.get_or_initialize(node_id, self.counting_nodes).accept()

    @handle_key_error
    def verify_subtask(self, subtask_id):
        return self.subtasks_given[subtask_id]['status'] == \
            SubtaskStatus.finished

    def verify_task(self):
        return self.finished_computation()

    def get_total_tasks(self):
        return self.task_definition.subtasks_count

    def get_active_tasks(self):
        return self.last_task

    def get_tasks_left(self):
        return (self.get_total_tasks() - self.last_task) \
            + self.num_failed_subtasks

    # pylint:disable=unused-argument,no-self-use
    def get_subtasks(self, part) -> Dict[str, dict]:
        return dict()

    def restart(self):
        for subtask_id in list(self.subtasks_given.keys()):
            self.restart_subtask(subtask_id)

    @handle_key_error
    def restart_subtask(
            self,
            subtask_id,
            new_state: Optional[SubtaskStatus] = None,
    ):
        subtask_info = self.subtasks_given[subtask_id]
        was_failure_before = subtask_info['status'] in [SubtaskStatus.failure,
                                                        SubtaskStatus.resent]

        logger.debug(
            'restart_subtask. subtask_id=%r, subtask_status=%r, new_state=%r',
            subtask_id,
            subtask_info['status'],
            new_state,
        )

        if subtask_info['status'].is_active():
            # TODO Restarted tasks that were waiting for verification should
            # cancel it. Issue #2423
            self._mark_subtask_failed(
                subtask_id,
                ban_node=(new_state != SubtaskStatus.cancelled)
            )
        elif subtask_info['status'] == SubtaskStatus.finished:
            self._mark_subtask_failed(subtask_id)
            self.num_tasks_received -= 1

        if not was_failure_before:
            subtask_info['status'] = SubtaskStatus.restarted

    def abort(self):
        pass

    def get_progress(self):
        if self.get_total_tasks() == 0:
            return 0.0
        return self.num_tasks_received / self.get_total_tasks()

    def update_task_state(self, task_state):
        pass

    @handle_key_error
    def get_trust_mod(self, subtask_id):
        return 1.0

    def add_resources(self, resources):
        self.res_files = resources

    def get_stderr(self, subtask_id):
        return self.stderr.get(subtask_id, "")

    def get_stdout(self, subtask_id):
        return self.stdout.get(subtask_id, "")

    def get_results(self, subtask_id):
        return self.results.get(subtask_id, [])

    def to_dictionary(self):
        return {
            'id': to_unicode(self.header.task_id),
            'name': to_unicode(self.task_definition.name),
            'type': to_unicode(self.task_definition.task_type),
            'subtasks_count': self.get_total_tasks(),
            'progress': self.get_progress()
        }

    def _new_compute_task_def(self, subtask_id, extra_data,
                              perf_index=0):
        ctd = golem_messages.message.ComputeTaskDef()
        ctd['task_id'] = self.header.task_id
        ctd['subtask_id'] = subtask_id
        ctd['extra_data'] = extra_data
        ctd['performance'] = perf_index
        if self.docker_images:
            ctd['docker_images'] = [di.to_dict() for di in self.docker_images]
        ctd['deadline'] = min(
            int(timeout_to_deadline(self.header.subtask_timeout)),
            self.header.deadline,
        )

        return ctd

    #########################
    # Specific task methods #
    #########################

    def interpret_task_results(
            self, subtask_id: str, task_results: TaskResult,
            sort: bool = True) -> None:
        """Filter out ".log" files from received results.
        Log files should represent stdout and stderr from computing machine.
        Other files should represent subtask results.
        :param subtask_id: id of a subtask for which results are received
        :param task_results: it may be a list of files
        :param bool sort: *default: True* Sort results, if set to True
        """
        self.stdout[subtask_id] = ""
        self.stderr[subtask_id] = ""
        self.results[subtask_id] = self.filter_task_results(
            task_results.files, subtask_id)
        if sort:
            self.results[subtask_id].sort()

    @handle_key_error
    def result_incoming(self, subtask_id):
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.downloading

    def filter_task_results(
            self, task_results: List[str], subtask_id: str,
            log_ext: str = ".log", err_log_ext: str = "err.log") -> List[str]:
        """ From a list of files received in task_results, return only files
        that don't have extension <log_ext> or <err_log_ext>. File with log_ext
        is saved as stdout for this subtask (only one file is currently
        supported). File with err_log_ext is save as stderr for this subtask
        (only one file is currently supported).
        :param list task_results: list of files
        :param str subtask_id: if of a given subtask
        :param str log_ext: extension that stdout files have
        :param str err_log_ext: extension that stderr files have
        :return:
        """

        filtered_task_results: List[str] = []
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
                    logger.warning("Cannot move file %s to new location: %s",
                                   tr, err)

        return filtered_task_results

    # pylint:disable=unused-argument,no-self-use
    def after_test(self, results, tmp_dir):
        return {}

    def notify_update_task(self):
        for l in self.listeners:
            l.notify_update_task(self.header.task_id)

    @handle_key_error
    def should_accept(self, subtask_id):
        status = self.subtasks_given[subtask_id]['status']
        return status.is_computed()

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
            logger.error("Can't read file %s: %s", log, err)
            return ""

    @handle_key_error
    def _mark_subtask_failed(self, subtask_id: str, ban_node: bool = True):
        logger.debug(
            '_mark_subtask_failed. subtask_id=%r, ban_node=%r',
            subtask_id,
            ban_node,
        )

        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.failure
        node_id = self.subtasks_given[subtask_id]['node_id']
        if node_id in self.counting_nodes:
            if ban_node:
                self.counting_nodes[node_id].reject()
            else:
                self.counting_nodes[node_id].cancel()
        self.num_failed_subtasks += 1

    def get_finishing_subtasks(self, node_id: str) -> List[dict]:
        return [
            subtask for subtask in self.subtasks_given.values()
            if subtask['status'].is_finishing()
            and subtask['node_id'] == node_id
        ]

    def get_resources(self):
        return self.task_resources

    def _get_resources_root_dir(self):
        task_resources = list(self.task_resources)
        prefix = os.path.commonprefix(task_resources)
        return os.path.dirname(prefix)

    def should_accept_client(self,
                             node_id: str,
                             offer_hash: str) -> AcceptClientVerdict:
        client = TaskClient.get_or_initialize(node_id, self.counting_nodes)
        if client.rejected():
            return AcceptClientVerdict.REJECTED
        elif client.should_wait(offer_hash):
            return AcceptClientVerdict.SHOULD_WAIT

        return AcceptClientVerdict.ACCEPTED

    def accept_client(self,
                      node_id: str,
                      offer_hash: str,
                      num_subtasks: int = 1) -> AcceptClientVerdict:
        verdict = self.should_accept_client(node_id, offer_hash)

        if verdict == AcceptClientVerdict.ACCEPTED:
            client = TaskClient.get_or_initialize(node_id, self.counting_nodes)
            client.start(offer_hash, num_subtasks)

        return verdict

    def copy_subtask_results(
            self, subtask_id: str, old_subtask_info: dict,
            results: TaskResult) -> None:
        new_subtask = self.subtasks_given[subtask_id]

        new_subtask['node_id'] = old_subtask_info['node_id']
        new_subtask['ctd']['performance'] = \
            old_subtask_info['ctd']['performance']

        self.accept_client(new_subtask['node_id'], '')
        self.result_incoming(subtask_id)
        self.interpret_task_results(
            subtask_id=subtask_id,
            task_results=results,
        )
        self.accept_results(
            subtask_id=subtask_id,
            result_files=self.results[subtask_id])


class CoreTaskBuilder(TaskBuilder):
    TASK_CLASS: Type[CoreTask]
    OUTPUT_DIR_TIME_FORMAT = '_%Y-%m-%d_%H-%M-%S'

    def __init__(self,
                 owner: 'dt_p2p.Node',
                 task_definition: 'TaskDefinition',
                 dir_manager: DirManager) -> None:
        super(CoreTaskBuilder, self).__init__()
        self.task_definition = task_definition
        self.root_path = dir_manager.root_path
        self.dir_manager = dir_manager
        self.owner = owner
        self.environment = None

    def build(self):
        # pylint:disable=abstract-class-instantiated
        return self.TASK_CLASS(**self.get_task_kwargs())

    def get_task_kwargs(self, **kwargs):
        kwargs["task_definition"] = self.task_definition
        kwargs["owner"] = self.owner
        kwargs["root_path"] = self.root_path
        return kwargs

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo, dictionary) \
            -> 'TaskDefinition':
        logger.debug(
            "build_minimal_definition. task_type=%r, dictionary=%r",
            task_type, dictionary
        )
        definition = task_type.definition()
        definition.options = task_type.options()
        definition.task_type = task_type.name
        definition.compute_on = dictionary.get('compute_on', 'cpu')
        definition.subtasks_count = int(dictionary['subtasks_count'])
        definition.concent_enabled = dictionary.get('concent_enabled', False)
        if 'resources' in dictionary:
            definition.resources = set(dictionary['resources'])
        return definition

    @classmethod
    def build_definition(cls,  # type: ignore
                         task_type: CoreTaskTypeInfo,
                         dictionary: Dict[str, Any],
                         minimal=False) \
            -> 'TaskDefinition':
        # dictionary comes from the GUI
        if not minimal:
            definition = cls.build_full_definition(task_type, dictionary)
        else:
            definition = cls.build_minimal_definition(task_type, dictionary)

        definition.add_to_resources()
        return definition

    @classmethod
    def build_full_definition(cls,
                              task_type: CoreTaskTypeInfo,
                              dictionary: Dict[str, Any]) \
            -> 'TaskDefinition':
        definition = cls.build_minimal_definition(task_type, dictionary)
        definition.name = dictionary['name']
        definition.max_price = \
            int(decimal.Decimal(dictionary['bid']) * denoms.ether)

        definition.timeout = string_to_timeout(dictionary['timeout'])
        definition.subtask_timeout = string_to_timeout(
            dictionary['subtask_timeout'],
        )
        definition.output_file = cls.get_output_path(dictionary, definition)
        definition.estimated_memory = dictionary.get('estimated_memory', 0)

        if 'x-run-verification' in dictionary:
            definition.run_verification = \
                RunVerification(dictionary['x-run-verification'])

        return definition

    # TODO: Backward compatibility only. The rendering tasks should
    # move to overriding their own TaskDefinitions instead of
    # overriding `build_dictionary. Issue #2424`
    @staticmethod
    def build_dictionary(definition: 'TaskDefinition') -> dict:
        return definition.to_dict()

    @classmethod
    def get_output_path(
            cls,
            dictionary: Dict[str, Any],
            definition: 'TaskDefinition') -> str:
        options = dictionary['options']

        output_dir_name = definition.name + \
            datetime.now().strftime(cls.OUTPUT_DIR_TIME_FORMAT)

        return cls.get_nonexistent_path(
            os.path.join(options['output_path'], output_dir_name),
            definition.name,
            options.get('format', '')
        )

    @classmethod
    def get_nonexistent_path(cls, path, name, extension=""):
        """
        Prevent overwriting with incremental filename
        @ref https://stackoverflow.com/a/43167607/1763249

        Example
        --------

        >>> get_nonexistent_path('/documents/golem/', 'task1', 'png')

        # if path is not exist
        '/documents/golem/task1'

        # or if exist
        '/documents/golem/task 1(1)'

        # or even if still exist
        '/documents/golem/task 1(2)'

        ...
        """
        fname_path = os.path.join(path, name)

        if extension:
            extension = "." + extension

        path_with_ext = os.path.join(path, name + extension)

        if not os.path.exists(path_with_ext):
            return fname_path

        i = 1
        new_fname = "{}({})".format(fname_path, i)

        while os.path.exists(new_fname + extension):
            i += 1
            new_fname = "{}({})".format(fname_path, i)

        return new_fname
