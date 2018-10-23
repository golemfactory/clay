import decimal
import logging
import os
from enum import Enum
from typing import Type, Optional, Dict, Any

from golem_messages import idgenerator
import golem_messages.message
from ethereum.utils import denoms
from golem_verificator.core_verifier import CoreVerifier
from golem_verificator.verifier import SubtaskVerificationState

from apps.blender.verification_queue import VerificationQueue
from apps.core.task.coretaskstate import TaskDefinition, Options
from golem.core.common import HandleKeyError, timeout_to_deadline, to_unicode, \
    string_to_timeout
from golem.core.compress import decompress
from golem.core.fileshelper import outer_dir_path
from golem.core.simpleserializer import CBORSerializer
from golem.docker.environment import DockerEnvironment
from golem.network.p2p.node import Node
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task, TaskHeader, TaskBuilder, ResultType, \
    TaskTypeInfo, AcceptClientVerdict
from golem.task.taskclient import TaskClient
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.core")


def log_key_error(*args, **_):
    logger.warning("This is not my subtask %s", args[1], exc_info=True)
    return False


MAX_PENDING_CLIENT_RESULTS = 1


class CoreTaskTypeInfo(TaskTypeInfo):
    """ Information about task that allows to define and build a new task,
    display outputs and previews. """

    # pylint:disable=too-many-arguments
    def __init__(self,
                 name: str,
                 definition: 'Type[TaskDefinition]',
                 defaults: 'TaskDefaults',
                 options: Type[Options],
                 builder_type: Type[TaskBuilder]):
        super().__init__(name, definition, defaults, options, builder_type)
        self.output_formats = []
        self.output_file_ext = []

    @classmethod
    # pylint:disable=unused-argument
    def get_task_num_from_pixels(cls, x, y, definition, subtasks_count,
                                 output_num=1):
        return 0

    @classmethod
    # pylint:disable=unused-argument
    def get_task_border(cls, subtask, definition, subtasks_count,
                        output_num=1, as_path=False):
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
    VERIFIER_CLASS = CoreVerifier  # type: Type[CoreVerifier]
    VERIFICATION_QUEUE = VerificationQueue()

    ENVIRONMENT_CLASS = None  # type: Type[Environment]

    handle_key_error = HandleKeyError(log_key_error)

    ################
    # Task methods #
    ################

    # pylint:disable=too-many-arguments
    def __init__(self,
                 task_definition: TaskDefinition,
                 owner: Node,
                 max_pending_client_results=MAX_PENDING_CLIENT_RESULTS,
                 resource_size=None,
                 root_path=None,
                 total_tasks=0):
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

        # src_code stuff
        self.main_program_file = self.environment.main_program_file
        try:
            with open(self.main_program_file, "r") as src_file:
                src_code = src_file.read()
        except OSError as err:
            logger.warning("Wrong main program file: %s", err)
            src_code = ""

        # docker_images stuff
        if task_definition.docker_images:
            self.docker_images = task_definition.docker_images
        elif isinstance(self.environment, DockerEnvironment):
            self.docker_images = self.environment.docker_images
        else:
            self.docker_images = None

        th = TaskHeader(
            task_id=task_definition.task_id,
            environment=self.environment.get_id(),
            task_owner=owner,
            deadline=self._deadline,
            subtask_timeout=task_definition.subtask_timeout,
            subtasks_count=total_tasks,
            resource_size=self.resource_size,
            estimated_memory=task_definition.estimated_memory,
            max_price=task_definition.max_price,
            concent_enabled=task_definition.concent_enabled,
        )

        Task.__init__(self, th, src_code, task_definition)

        self.total_tasks = total_tasks
        self.last_task = 0

        self.num_tasks_received = 0
        self.subtasks_given = {}
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
        self.max_pending_client_results = max_pending_client_results

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
        return (self.last_task != self.total_tasks) or \
               (self.num_failed_subtasks > 0)

    def finished_computation(self):
        return self.num_tasks_received == self.total_tasks

    def computation_failed(self, subtask_id):
        self._mark_subtask_failed(subtask_id)

    def computation_finished(self, subtask_id, task_result,
                             result_type=ResultType.DATA,
                             verification_finished=None):
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.verifying
        self.interpret_task_results(subtask_id, task_result, result_type)
        result_files = self.results.get(subtask_id)

        def verification_finished_(subtask_id, verdict, result):
            self.verification_finished(subtask_id, verdict, result)
            verification_finished()
        self.VERIFICATION_QUEUE.submit(
            self.VERIFIER_CLASS,
            subtask_id,
            self._deadline,
            verification_finished_,
            subtask_info={**self.subtasks_given[subtask_id],
                          **{'owner': self.header.task_owner.key}},
            results=result_files,
            resources=self.task_resources,
            reference_data=self.get_reference_data()
        )

    # pylint:disable=no-self-use
    def get_reference_data(self):
        return []

    def verification_finished(self, subtask_id, verdict, result):
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
        TaskClient.assert_exists(node_id, self.counting_nodes).accept()

    @handle_key_error
    def verify_subtask(self, subtask_id):
        return self.subtasks_given[subtask_id]['status'] == \
            SubtaskStatus.finished

    def verify_task(self):
        return self.finished_computation()

    def get_total_tasks(self):
        return self.total_tasks

    def get_active_tasks(self):
        return self.last_task

    def get_tasks_left(self):
        return (self.total_tasks - self.last_task) + self.num_failed_subtasks

    # pylint:disable=unused-argument,no-self-use
    def get_subtasks(self, part):
        return dict()

    def restart(self):
        for subtask_id in list(self.subtasks_given.keys()):
            self.restart_subtask(subtask_id)

    @handle_key_error
    def restart_subtask(self, subtask_id):
        subtask_info = self.subtasks_given[subtask_id]
        was_failure_before = subtask_info['status'] in [SubtaskStatus.failure,
                                                        SubtaskStatus.resent]

        if subtask_info['status'].is_active():
            # TODO Restarted tasks that were waiting for verification should
            # cancel it. Issue #2423
            self._mark_subtask_failed(subtask_id)
        elif subtask_info['status'] == SubtaskStatus.finished:
            self._mark_subtask_failed(subtask_id)
            tasks = subtask_info['end_task'] - subtask_info['start_task'] + 1
            self.num_tasks_received -= tasks

        if not was_failure_before:
            subtask_info['status'] = SubtaskStatus.restarted

    def abort(self):
        pass

    def get_progress(self):
        if self.total_tasks == 0:
            return 0.0
        return self.num_tasks_received / self.total_tasks

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

    def _new_blender_script_package(
            self,
            resolution,
            borders_x,
            borders_y,
            use_compositing,
            samples,
            frames,
            output_format
    ):

        return golem_messages.message.tasks.BlenderScriptPackage(
            resolution=resolution,
            borders_x=borders_x,
            borders_y=borders_y,
            use_compositing=use_compositing,
            samples=samples,
            frames=frames,
            output_format=golem_messages.message
            .tasks.OUTPUT_FORMAT(output_format).name
        )

    def _new_compute_task_def(
            self,
            subtask_id,
            extra_data,
            task_type,
            meta_parameters,
            perf_index=0,
    ):
        ctd = golem_messages.message.ComputeTaskDef(
            task_type=task_type,
            meta_parameters=meta_parameters,
        )
        ctd['task_id'] = self.header.task_id
        ctd['subtask_id'] = subtask_id
        ctd['extra_data'] = extra_data
        ctd['short_description'] = self.short_extra_data_repr(extra_data)
        ctd['src_code'] = self.src_code
        ctd['performance'] = perf_index
        if self.docker_images:
            ctd['docker_images'] = [di.to_dict() for di in self.docker_images]
        ctd['deadline'] = min(timeout_to_deadline(self.header.subtask_timeout),
                              self.header.deadline)

        return ctd

    #########################
    # Specific task methods #
    #########################

    def interpret_task_results(self, subtask_id, task_results, result_type: int,
                               sort=True):
        """Filter out ".log" files from received results.
        Log files should represent stdout and stderr from computing machine.
        Other files should represent subtask results.
        :param subtask_id: id of a subtask for which results are received
        :param task_results: it may be a list of files, if result_type is equal
        to ResultType.files or it may be a cbor serialized zip file containing
        all files, if result_type is equal to ResultType.data
        :param result_type: a number from ResultType, it may represents data
        format or files format
        :param bool sort: *default: True* Sort results, if set to True
        """
        self.stdout[subtask_id] = ""
        self.stderr[subtask_id] = ""
        tr_files = self.load_task_results(
            task_results, result_type, subtask_id)
        self.results[subtask_id] = self.filter_task_results(
            tr_files, subtask_id)
        if sort:
            self.results[subtask_id].sort()

    @handle_key_error
    def result_incoming(self, subtask_id):
        self.counting_nodes[self.subtasks_given[
            subtask_id]['node_id']].finish()
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.downloading

    def load_task_results(self, task_result, result_type, subtask_id):
        """ Change results to a list of files. If result_type is equal to
        ResultType.files this function only return task_results without making
        any changes. If result_type is equal to ResultType.data tham task_result
         is cbor and unzipped and files are saved in tmp_dir.
        :param task_result: list of files of cbor serialized ziped file with
        files
        :param result_type: int, ResultType element
        :param str subtask_id:
        :return:
        """
        if result_type == ResultType.DATA:
            output_dir = os.path.join(self.tmp_dir, subtask_id)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            return [self._unpack_task_result(trp, output_dir)
                    for trp in task_result]
        elif result_type == ResultType.FILES:
            return task_result
        else:
            logger.error(
                "Task result type not supported %r",
                result_type,
            )
            self.stderr[subtask_id] = "[GOLEM] Task result {} not supported" \
                .format(result_type)
            return []

    def filter_task_results(self, task_results, subtask_id, log_ext=".log",
                            err_log_ext="err.log"):
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
    def _mark_subtask_failed(self, subtask_id):
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.failure
        node_id = self.subtasks_given[subtask_id]['node_id']
        if node_id in self.counting_nodes:
            self.counting_nodes[node_id].reject()
        self.num_failed_subtasks += 1

    def _unpack_task_result(self, trp, output_dir):
        tr = CBORSerializer.loads(trp)
        with open(os.path.join(output_dir, tr[0]), "wb") as fh:
            fh.write(decompress(tr[1]))
        return os.path.join(output_dir, tr[0])

    def get_resources(self):
        return self.task_resources

    def _get_resources_root_dir(self):
        task_resources = list(self.task_resources)
        prefix = os.path.commonprefix(task_resources)
        return os.path.dirname(prefix)

    def should_accept_client(self, node_id):
        client = TaskClient.assert_exists(node_id, self.counting_nodes)
        finishing = client.finishing()
        max_finishing = self.max_pending_client_results

        if client.rejected():
            return AcceptClientVerdict.REJECTED
        elif finishing >= max_finishing or \
                client.started() - finishing >= max_finishing:
            return AcceptClientVerdict.SHOULD_WAIT

        return AcceptClientVerdict.ACCEPTED

    def accept_client(self, node_id):
        verdict = self.should_accept_client(node_id)

        if verdict == AcceptClientVerdict.ACCEPTED:
            client = TaskClient.assert_exists(node_id, self.counting_nodes)
            client.start()

        return verdict

    def copy_subtask_results(self, subtask_id, old_subtask_info, results):
        new_subtask = self.subtasks_given[subtask_id]

        new_subtask['node_id'] = old_subtask_info['node_id']
        new_subtask['ctd']['performance'] = \
            old_subtask_info['ctd']['performance']

        self.accept_client(new_subtask['node_id'])
        self.result_incoming(subtask_id)
        self.interpret_task_results(
            subtask_id=subtask_id,
            task_results=results,
            result_type=ResultType.FILES)
        self.accept_results(
            subtask_id=subtask_id,
            result_files=self.results[subtask_id])


class CoreTaskBuilder(TaskBuilder):
    TASK_CLASS = CoreTask

    def __init__(self,
                 owner: Node,
                 task_definition: TaskDefinition,
                 dir_manager: DirManager) -> None:
        super(CoreTaskBuilder, self).__init__()
        self.task_definition = task_definition
        self.root_path = dir_manager.root_path
        self.dir_manager = dir_manager
        self.owner = owner
        self.src_code = ""
        self.environment = None

    def build(self):
        # pylint:disable=abstract-class-instantiated
        task = self.TASK_CLASS(**self.get_task_kwargs())

        task.initialize(self.dir_manager)
        return task

    def get_task_kwargs(self, **kwargs):
        kwargs['total_tasks'] = int(self.task_definition.subtasks_count)
        kwargs["task_definition"] = self.task_definition
        kwargs["owner"] = self.owner
        kwargs["root_path"] = self.root_path
        return kwargs

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo, dictionary):
        definition = task_type.definition()
        definition.options = task_type.options()
        definition.task_type = task_type.name
        definition.compute_on = dictionary.get('compute_on', 'cpu')
        definition.resources = set(dictionary['resources'])
        definition.subtasks_count = int(dictionary['subtasks_count'])
        definition.main_program_file = task_type.defaults.main_program_file
        return definition

    @classmethod
    def build_definition(cls,  # type: ignore
                         task_type: CoreTaskTypeInfo,
                         dictionary: Dict[str, Any],
                         minimal=False):
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
                              dictionary: Dict[str, Any]):
        definition = cls.build_minimal_definition(task_type, dictionary)
        definition.name = dictionary['name']
        definition.max_price = \
            int(decimal.Decimal(dictionary['bid']) * denoms.ether)

        definition.timeout = string_to_timeout(
            dictionary['timeout'])
        definition.subtask_timeout = string_to_timeout(
            dictionary['subtask_timeout'])
        definition.output_file = cls.get_output_path(dictionary, definition)
        definition.estimated_memory = dictionary.get('estimated_memory', 0)

        return definition

    # TODO: Backward compatibility only. The rendering tasks should
    # move to overriding their own TaskDefinitions instead of
    # overriding `build_dictionary. Issue #2424`
    @staticmethod
    def build_dictionary(definition: TaskDefinition) -> dict:
        return definition.to_dict()

    @classmethod
    def get_output_path(cls, dictionary, definition):
        options = dictionary['options']

        absolute_path = cls.get_nonexistent_path(
            options['output_path'],
            definition.name,
            options.get('format', ''))

        return absolute_path

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
