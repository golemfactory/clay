from copy import deepcopy
from pathlib import Path, PurePath
from typing import (
    Any,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Callable,
    Set
)
import logging

from golem_messages.message import ComputeTaskDef
from golem_messages.datastructures.p2p import Node

from apps.core.task.coretask import (
    CoreTask,
    CoreTaskBuilder,
    CoreTaskTypeInfo
)
from apps.core.task.coretaskstate import Options, TaskDefinition
from apps.wasm.environment import WasmTaskEnvironment
from golem.task.taskbase import Task, AcceptClientVerdict
from golem.task.taskstate import SubtaskStatus
from golem.task.taskclient import TaskClient

from .vbr import (
    Actor,
    BucketVerifier,
    VerificationResult,
    NotAllowedError,
    MissingResultsError
)

logger = logging.getLogger("apps.wasm")


class VbrSubtask:
    """Encapsulating subtask handling behavior for Verification by
    Redundancy. This class hides result handling, subtask spawning
    and subtask related data management from the client code.
    """
    # __DEBUG_COUNTER: int = 0
    def __init__(self, id_gen, name, params, redundancy_factor):
        self.id_gen = id_gen
        self.name = name
        self.params = params
        self.result = None
        self.redundancy_factor = redundancy_factor

        self.subtasks = {}
        self.verifier = BucketVerifier(
            redundancy_factor, WasmTask.cmp_results, referee_count=0)

    def contains(self, s_id) -> bool:
        return s_id in self.subtasks

    def is_allowed_node(self, node_id):
        actor = Actor(node_id)
        try:
            self.verifier.validate_actor(actor)
        except (NotAllowedError, MissingResultsError):
            return False
        return True

    def new_instance(self, node_id) -> Optional[Tuple[str, dict]]:
        actor = Actor(node_id)

        if not self.is_allowed_node(node_id):
            return None

        self.verifier.add_actor(actor)

        s_id = self.id_gen()
        self.subtasks[s_id] = {
            "status": SubtaskStatus.starting,
            "actor": actor,
            "results": None
        }

        return s_id, deepcopy(self.params)

    def get_instance(self, s_id) -> dict:
        return self.subtasks[s_id]

    def get_instances(self) -> List[str]:
        return self.subtasks.keys()

    def add_result(self, s_id, task_result):
        self.verifier.add_result(self.subtasks[s_id]["actor"], task_result)
        self.subtasks[s_id]["results"] = task_result

    def get_result(self):
        return self.result

    def is_finished(self) -> bool:
        return self.verifier.get_verdicts() is not None

    def get_verdicts(self):
        verdicts = []
        for actor, result, verdict in self.verifier.get_verdicts():
            if verdict == VerificationResult.SUCCESS and not self.result:
                self.result = result

            verdicts.append((actor, verdict))

        return verdicts


class WasmTaskOptions(Options):
    class SubtaskOptions:
        def __init__(self, name: str, exec_args: List[str],
                     output_file_paths: List[str]) -> None:
            self.name: str = name
            self.exec_args: List[str] = exec_args
            self.output_file_paths: List[str] = output_file_paths

    def __init__(self) -> None:
        super().__init__()
        self.js_name: str = ''
        self.wasm_name: str = ''
        self.input_dir: str = ''
        self.output_dir: str = ''
        self.subtasks: Dict[str, WasmTaskOptions.SubtaskOptions] = {}

    def _subtasks(self) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        for subtask_name, subtask_opts in self.subtasks.items():
            yield subtask_name, {
                'name': subtask_name,
                'js_name': self.js_name,
                'wasm_name': self.wasm_name,
                'exec_args': subtask_opts.exec_args,
                'input_dir_name': PurePath(self.input_dir).name,
                'output_file_paths': subtask_opts.output_file_paths,
            }

    def get_subtask_iterator(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        # The generator has to be listed first because the resulting iterator
        # has to be picklable.
        return iter(list(self._subtasks()))


class WasmTaskDefinition(TaskDefinition):
    def __init__(self) -> None:
        super().__init__()
        self.options = WasmTaskOptions()
        self.task_type = 'WASM'

    def add_to_resources(self) -> None:
        self.resources = [self.options.input_dir]


class WasmTask(CoreTask):
    ENVIRONMENT_CLASS = WasmTaskEnvironment

    JOB_ENTRYPOINT = 'python3 /golem/scripts/job.py'
    REDUNDANCY_FACTOR = 1
    CALLBACKS: Dict[str, Callable] = {}

    def __init__(self, task_definition: WasmTaskDefinition,
                 root_path: Optional[str] = None, owner: Node = None) -> None:
        super().__init__(
            task_definition=task_definition,
            root_path=root_path, owner=owner
        )
        self.options: WasmTaskOptions = task_definition.options
        self.subtasks: List[VbrSubtask] = []
        self.subtasks_given = {}

        for s_name, s_params in self.options.get_subtask_iterator():
            s_params = {
                'entrypoint': self.JOB_ENTRYPOINT,
                **s_params
            }
            subtask = VbrSubtask(self.create_subtask_id,
                                 s_name, s_params, self.REDUNDANCY_FACTOR)
            self.subtasks.append(subtask)

        self.nodes_blacklist: Set[str] = set()

    def query_extra_data(
            self, perf_index: float,
            node_id: Optional[str] = None,
            node_name: Optional[str] = None) -> Task.ExtraData:
        for s in self.subtasks:
            if s.is_finished():
                continue
            next_subtask = s.new_instance(node_id)
            if next_subtask:
                s_id, s_params = next_subtask
                self.subtasks_given[s_id] = {
                    'status': SubtaskStatus.starting,
                    'node_id': node_id
                }
                ctd = self._new_compute_task_def(s_id, s_params, perf_index)

                return Task.ExtraData(ctd=ctd)
        raise RuntimeError()

    def _find_vbrsubtask_by_id(self, subtask_id) -> VbrSubtask:
        for subtask in self.subtasks:
            if subtask.contains(subtask_id):
                return subtask
        raise KeyError()

    @staticmethod
    def cmp_results(result_list_a: List[Any],
                    result_list_b: List[Any]) -> bool:
        logger.debug("Comparing: %s and %s", result_list_a, result_list_b)
        for r1, r2 in zip(result_list_a, result_list_b):
            with open(r1, 'rb') as f1, open(r2, 'rb') as f2:
                b1 = f1.read()
                b2 = f2.read()
                if b1 != b2:
                    return False
        return True

    def __resolve_payments(self, subtask: VbrSubtask):
        verdicts = subtask.get_verdicts()

        for s_id in subtask.get_instances():
            instance = subtask.get_instance(s_id)
            for actor, verdict in verdicts:
                if actor is not instance['actor']:
                    continue

                if verdict == VerificationResult.SUCCESS:
                    # pay up!
                    logger.info("Accepting results for subtask %s", s_id)
                    self.subtasks_given[s_id]['status'] =\
                        SubtaskStatus.finished
                    TaskClient.get_or_initialize(actor.uuid,
                                                 self.counting_nodes).accept()
                else:
                    logger.info("Rejecting results for subtask %s", s_id)
                    self.subtasks_given[s_id]['status'] = SubtaskStatus.failure
                    TaskClient.get_or_initialize(actor.uuid,
                                                 self.counting_nodes).reject()
                    logger.info("Blacklisting node: %s", actor.uuid)
                    self.nodes_blacklist.add(actor.uuid)

        # save the results but only if verification was successful
        result = subtask.get_result()
        if result is not None:
            self.save_results(subtask.name, result)
        else:
            new_subtask = VbrSubtask(self.create_subtask_id, subtask.name,
                                     subtask.params, subtask.redundancy_factor)
            self.subtasks.append(new_subtask)

    def computation_finished(self, subtask_id, task_result,
                             verification_finished=None) -> None:
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return

        task_result = self.interpret_task_results(subtask_id, task_result)

        # find the VbrSubtask that contains subtask_id
        subtask = self._find_vbrsubtask_by_id(subtask_id)
        subtask.add_result(subtask_id, task_result)
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.verifying
        WasmTask.CALLBACKS[subtask_id] = verification_finished

        if subtask.is_finished():
            self.__resolve_payments(subtask)
            for s_id in subtask.get_instances():
                WasmTask.CALLBACKS.pop(s_id)()

    def save_results(self, name: str, result_files: List[str]) -> None:
        output_dir_path = Path(self.options.output_dir, name)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        for result_file in result_files:
            output_file_path = output_dir_path / PurePath(result_file).name
            with open(result_file, 'rb') as f_in, \
                    open(output_file_path, 'wb') as f_out:
                f_out.write(f_in.read())

    def accept_results(self, subtask_id, result_files):
        pass

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        next_subtask_instance = self.subtasks[0]\
            .new_instance("benchmark_node_id")

        if not next_subtask_instance:
            raise ValueError()

        next_subtask_name, next_extra_data = next_subtask_instance

        # When the resources are sent through Hyperg, the input directory is
        # copied to RESOURCE_DIR inside the container. But when running the
        # benchmark task, the input directory _becomes_ the RESOURCE_DIR, so
        # the outer input directory name has to be discarded.
        next_extra_data['input_dir_name'] = ''

        return self._new_compute_task_def(
            subtask_id=self.create_subtask_id(), extra_data=next_extra_data
        )

    def filter_task_results(self, task_results, subtask_id, log_ext=".log",
                            err_log_ext="err.log"):
        filtered_task_results = []
        for tr in task_results:
            if tr.endswith(err_log_ext):
                self.stderr[subtask_id] = tr
            elif tr.endswith(log_ext):
                self.stdout[subtask_id] = tr
            else:
                filtered_task_results.append(tr)

        return filtered_task_results

    def interpret_task_results(self, subtask_id, task_results, sort=True):
        """Filter out ".log" files from received results.
        Log files should represent stdout and stderr from computing machine.
        Other files should represent subtask results.
        :param subtask_id: id of a subtask for which results are received
        :param task_results: it may be a list of files
        :param bool sort: *default: True* Sort results, if set to True
        """
        self.stdout[subtask_id] = ""
        self.stderr[subtask_id] = ""
        results = self.filter_task_results(task_results, subtask_id)
        if sort:
            results.sort()

        return results

    def should_accept_client(self,
                             node_id: str,
                             offer_hash: str) -> AcceptClientVerdict:
        """Deciding whether to accept particular node_id for next task
        computation.

        Arguments:
            node_id {str} -- Node offered to compute next task

        Returns:
            AcceptClientVerdict -- When AcceptClientVerdict.ACCEPTED value is
            returned the task will get a call to `query_extra_data` with
            corresponding `node_id`. On AcceptClientVerdict.REJECTED and
            AcceptClientVerdict.SHOULD_WAIT the node offer will be turned down,
            but might appear in subsequent `should_accept_client` invocation.
            The only difference between REJECTED and SHOULD_WAIT is the logj
            message.
        """
        if node_id in self.nodes_blacklist:
            logger.info("Node %s has been blacklisted for this task", node_id)
            return AcceptClientVerdict.REJECTED

        for s in self.subtasks:
            if s.is_allowed_node(node_id):
                return AcceptClientVerdict.ACCEPTED

        return AcceptClientVerdict.SHOULD_WAIT

    def accept_client(self,
                      node_id: str,
                      offer_hash: str,
                      num_subtasks: int = 1) -> AcceptClientVerdict:
        client = TaskClient.get_or_initialize(node_id, self.counting_nodes)
        client.start(offer_hash, 1)
        return AcceptClientVerdict.ACCEPTED

    def needs_computation(self) -> bool:
        return not self.finished_computation()

    def finished_computation(self):
        finished = all([subtask.is_finished() for subtask in self.subtasks])
        logger.debug("Finished computation: %d", finished)
        return finished

    def computation_failed(self, subtask_id: str, ban_node: bool = True):
        subtask = self._find_vbrsubtask_by_id(subtask_id)
        subtask.add_result(subtask_id, None)
        if subtask.is_finished():
            self.__resolve_payments(subtask)

    def verify_task(self):
        return self.finished_computation()

    def get_total_tasks(self):
        return (WasmTask.REDUNDANCY_FACTOR + 1) * len(self.subtasks)

    def get_active_tasks(self):
        return sum(
            [0 if subtask.is_finished() else (WasmTask.REDUNDANCY_FACTOR + 1)
             for subtask in self.subtasks]
        )

    def get_tasks_left(self):
        num_finished = len(list(filter(lambda x: x.is_finished(),
                                       self.subtasks)))
        return self.get_total_tasks() - num_finished

    def restart(self):
        for subtask_id in list(self.subtasks_given.keys()):
            self.restart_subtask(subtask_id)

    def restart_subtask(self, subtask_id):
        logger.debug('restart_subtask. subtask_id=%r', subtask_id)

        subtask_info = self.subtasks_given[subtask_id]
        was_failure_before = subtask_info['status'] in [SubtaskStatus.failure,
                                                        SubtaskStatus.resent]

        if subtask_info['status'].is_active():
            # TODO Restarted tasks that were waiting for verification should
            # cancel it. Issue #2423
            self._mark_subtask_failed(subtask_id)
        elif subtask_info['status'] == SubtaskStatus.finished:
            self._mark_subtask_failed(subtask_id)
            self.num_tasks_received -= 1

        if not was_failure_before:
            subtask_info['status'] = SubtaskStatus.restarted

    def get_progress(self) -> float:
        """
        Returns current progress.

        Instead of tracking some aux variables, it polls VbrSubtasks
        directly for their current state; i.e., whether they are finished,
        or not.
        """
        num_total = self.get_total_tasks()
        if num_total == 0:
            return 0.0

        num_finished = len(list(filter(lambda x: x.is_finished(),
                                       self.subtasks)))

        return (WasmTask.REDUNDANCY_FACTOR + 1) * num_finished / num_total

    def get_results(self, subtask_id):
        subtask = self._find_vbrsubtask_by_id(subtask_id)
        instance = subtask.get_instance(subtask_id)
        return instance["results"]


class WasmTaskBuilder(CoreTaskBuilder):
    TASK_CLASS: Type[WasmTask] = WasmTask

    @classmethod
    def build_full_definition(cls, task_type: 'CoreTaskTypeInfo',
                              dictionary: Dict[str, Any]) -> TaskDefinition:
        # Resources are generated from 'input_dir' later on.
        dictionary['resources'] = []
        # Output is determined from 'output_dir' later on.
        dictionary['options']['output_path'] = ''
        # Subtasks count is determined by the amount of subtask info provided.
        dictionary['subtasks_count'] = (WasmTask.REDUNDANCY_FACTOR + 1)\
            * len(dictionary['options']['subtasks'])

        task_def = super().build_full_definition(task_type, dictionary)

        options = dictionary['options']
        task_def.options.js_name = options['js_name']
        task_def.options.wasm_name = options['wasm_name']
        task_def.options.input_dir = options['input_dir']
        task_def.options.output_dir = options['output_dir']

        task_def.options.subtasks = {
            name: WasmTaskOptions.SubtaskOptions(
                name, subtask_opts['exec_args'],
                subtask_opts['output_file_paths']
            )
            for name, subtask_opts in options['subtasks'].items()
        }

        return task_def


class WasmBenchmarkTask(WasmTask):
    def query_extra_data(self, perf_index: float,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        ctd = self.query_extra_data_for_test_task()
        return self.ExtraData(ctd)


class WasmBenchmarkTaskBuilder(WasmTaskBuilder):
    TASK_CLASS: Type[WasmTask] = WasmBenchmarkTask


class WasmTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self) -> None:
        super().__init__(
            'WASM', WasmTaskDefinition, WasmTaskOptions, WasmTaskBuilder
        )
