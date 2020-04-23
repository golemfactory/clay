import os
from copy import deepcopy
from pathlib import Path, PurePath
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Set
)
import logging
from dataclasses import dataclass

from ethereum.utils import denoms

from golem_messages.message import ComputeTaskDef
from golem_messages.datastructures.p2p import Node

from apps.core.task.coretask import (
    CoreTask,
    CoreTaskBuilder,
    CoreTaskTypeInfo
)
from apps.core.task.coretaskstate import Options, TaskDefinition
from apps.wasm.environment import WasmTaskEnvironment
from golem.marketplace.wasm_marketplace import (
    ProviderWasmMarketStrategy,
    RequestorWasmMarketStrategy,
    UsageReport
)
import golem.model
from golem.task.taskbase import Task, AcceptClientVerdict, TaskResult
from golem.task.taskstate import SubtaskStatus
from golem.task.taskclient import TaskClient

from .vbr import (
    Actor,
    BucketVerifier,
    VerificationResult,
    NotAllowedError,
    MissingResultsError
)

NANOSECOND = 1e-9

logger = logging.getLogger("apps.wasm")


@dataclass
class SubtaskInstance:
    status: SubtaskStatus
    actor: Actor
    results: Optional[TaskResult]


class VbrSubtask:
    """Encapsulating subtask handling behavior for Verification by
    Redundancy. This class hides result handling, subtask spawning
    and subtask related data management from the client code.
    """
    # __DEBUG_COUNTER: int = 0
    def __init__(
            self, id_gen: Callable[[], str], name: str, params: Dict[str, str],
            redundancy_factor: int
    ):
        self.id_gen = id_gen
        self.name = name
        self.params = params
        self.result: Optional[TaskResult] = None
        self.redundancy_factor = redundancy_factor
        self.subtasks: Dict[str, SubtaskInstance] = {}
        self.verifier = BucketVerifier(
            redundancy_factor, WasmTask.cmp_results, referee_count=1)

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
        self.subtasks[s_id] = SubtaskInstance(
            SubtaskStatus.starting, actor, TaskResult())

        return s_id, deepcopy(self.params)

    def get_instance(self, s_id) -> SubtaskInstance:
        return self.subtasks[s_id]

    def get_instances(self) -> List[str]:
        return list(self.subtasks.keys())

    def add_result(self, s_id: str, task_result: Optional[TaskResult]):
        result_files = task_result.files if task_result else None
        self.verifier.add_result(
            self.subtasks[s_id].actor, result_files)
        self.subtasks[s_id].results = task_result

    def get_result(self) -> Optional[TaskResult]:
        return self.result

    def is_finished(self) -> bool:
        return self.verifier.get_verdicts() is not None

    def get_verdicts(self):
        verdicts = []
        for actor, result, verdict in self.verifier.get_verdicts():
            if verdict == VerificationResult.SUCCESS and not self.result:
                self.result = TaskResult(files=result)

            verdicts.append((actor, verdict))

        return verdicts

    def get_subtask_count(self) -> int:
        """Returns a number of subtasks that will be computed
        within this VbrSubtask instance. This is a dynamic value
        that will change if referee is called into action.
        """
        instances_cnt = len(self.get_instances())
        if instances_cnt < self.redundancy_factor + 1:
            instances_cnt = self.redundancy_factor + 1
        return instances_cnt

    def get_tasks_left(self) -> int:
        return self.get_subtask_count() - len(
            [
                s for s in self.subtasks.values()
                if s.status != SubtaskStatus.finished
            ])

    def restart_subtask(self, subtask_id: str):
        subtask = self.subtasks[subtask_id]
        if subtask.status != SubtaskStatus.starting:
            raise ValueError(
                "Cannot restart subtask with status: " + str(
                    subtask.status))
        if subtask.results is not None and subtask.results.files:
            logger.warning(
                "results subtask status=%s results=%s", str(subtask.status),
                repr(subtask.results))
            raise ValueError("Cannot restart computed VbR subtask")
        self.verifier.remove_actor(subtask.actor)
        subtask.status = SubtaskStatus.restarted


class WasmTaskOptions(Options):
    class SubtaskOptions:
        def __init__(self, name: str, exec_args: List[str],
                     output_file_paths: List[str]) -> None:
            self.name: str = name
            self.exec_args: List[str] = exec_args
            self.output_file_paths: List[str] = output_file_paths

        def to_dict(self) -> dict:
            return {
                'name': self.name,
                'exec_args': self.exec_args,
                'output_file_paths': self.output_file_paths
            }

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
        self.budget: int = 1 * denoms.ether

    def add_to_resources(self) -> None:
        self.resources = [self.options.input_dir]

    def to_dict(self) -> dict:
        dictionary = super().to_dict()
        dictionary['options']['js_name'] = self.options.js_name
        dictionary['options']['wasm_name'] = self.options.wasm_name
        dictionary['options']['input_dir'] = self.options.input_dir
        dictionary['options']['output_dir'] = self.options.output_dir
        dictionary['options']['subtasks'] = {
            k: v.to_dict() for k, v in self.options.subtasks.items()
        }
        return dictionary


class WasmTask(CoreTask):  # pylint: disable=too-many-public-methods
    REQUESTOR_MARKET_STRATEGY: Type[RequestorWasmMarketStrategy] = \
        RequestorWasmMarketStrategy
    PROVIDER_MARKET_STRATEGY: Type[ProviderWasmMarketStrategy] = \
        ProviderWasmMarketStrategy

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
        self.task_definition: WasmTaskDefinition = task_definition
        self.options: WasmTaskOptions = task_definition.options
        self.subtasks: List[VbrSubtask] = []

        for s_name, s_params in self.options.get_subtask_iterator():
            s_params = {
                'entrypoint': self.JOB_ENTRYPOINT,
                **s_params
            }
            subtask = VbrSubtask(self.create_subtask_id,
                                 s_name, s_params, self.REDUNDANCY_FACTOR)
            self.subtasks.append(subtask)

        self.nodes_blacklist: Set[str] = set()
        self._load_requestor_perf()

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
                self.subtasks_given[s_id] = dict(
                    status=SubtaskStatus.starting, node_id=node_id)
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

    def _resolve_subtasks_statuses(self, subtask: VbrSubtask):
        verdicts = subtask.get_verdicts()

        for s_id in subtask.get_instances():
            instance = subtask.get_instance(s_id)
            for actor, verdict in verdicts:
                if actor is not instance.actor:
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

    def _handle_vbr_subtask_result(self, subtask: VbrSubtask):
        # save the results but only if verification was successful
        result: Optional[TaskResult] = subtask.get_result()
        if result is not None:
            self.save_results(subtask.name, result.files)
        else:
            new_subtask = VbrSubtask(self.create_subtask_id, subtask.name,
                                     subtask.params, subtask.redundancy_factor)
            self.subtasks.append(new_subtask)

    def computation_finished(
            self, subtask_id: str, task_result: TaskResult,
            verification_finished: Callable[[], None]) -> None:
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return
        # Save the callback and wait for VbrSubtask verdict.
        WasmTask.CALLBACKS[subtask_id] = verification_finished
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.verifying

        self.interpret_task_results(subtask_id, task_result)
        task_result.files = self.results[subtask_id]

        subtask = self._find_vbrsubtask_by_id(subtask_id)
        subtask.add_result(subtask_id, task_result)

        if subtask.is_finished():
            self._resolve_subtasks_statuses(subtask)
            self._handle_vbr_subtask_result(subtask)

            subtask_usages: List[UsageReport] = []
            for s_id in subtask.get_instances():
                s_instance = subtask.get_instance(s_id)
                if not s_instance.results:
                    continue
                if s_instance.results.stats.cpu_stats is not None:
                    subtask_usages.append(
                        (
                            s_instance.actor.uuid, s_id,
                            s_instance.results.stats.
                            cpu_stats.cpu_usage['total_usage'] * NANOSECOND))
                else:
                    logger.warning(
                        "invalid result stats %s",
                        repr(s_instance.results.stats))
            self.REQUESTOR_MARKET_STRATEGY.report_subtask_usages(
                self.task_definition.task_id,
                subtask_usages
            )

            for s_id in subtask.get_instances():
                try:
                    WasmTask.CALLBACKS.pop(s_id)()
                except KeyError:
                    # For cases with referee there will be a subtask instance
                    # that failed and therefore not delivered results.
                    pass

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
        next_subtask_instance = self.subtasks[0] \
            .new_instance("benchmark_node_id")

        if not next_subtask_instance:
            raise ValueError()

        _next_subtask_name, next_extra_data = next_subtask_instance

        # When the resources are sent through Hyperg, the input directory is
        # copied to RESOURCE_DIR inside the container. But when running the
        # benchmark task, the input directory _becomes_ the RESOURCE_DIR, so
        # the outer input directory name has to be discarded.
        next_extra_data['input_dir_name'] = ''

        return self._new_compute_task_def(
            subtask_id=self.create_subtask_id(), extra_data=next_extra_data
        )

    def filter_task_results(
            self, task_results: List[str], subtask_id: str,
            log_ext: str = ".log",
            err_log_ext: str = "err.log") -> List[str]:
        filtered_task_results: List[str] = []
        for tr in task_results:
            if tr.endswith(err_log_ext):
                self.stderr[subtask_id] = tr
            elif tr.endswith(log_ext):
                self.stdout[subtask_id] = tr
            else:
                filtered_task_results.append(tr)

        return filtered_task_results

    def should_accept_client(
            self, node_id: str, offer_hash: str) -> AcceptClientVerdict:
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

        # No subtask has yielded next actor meaning that there is no work
        # to be done at the moment
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
        try:
            subtask.add_result(subtask_id, None)
        except ValueError:
            # Handle a case of duplicate call from __remove_old_tasks
            pass
        if subtask.is_finished():
            self._resolve_subtasks_statuses(subtask)
            self._handle_vbr_subtask_result(subtask)

    def verify_task(self):
        return self.finished_computation()

    def get_total_tasks(self):
        return sum([s.get_subtask_count() for s in self.subtasks])

    def get_active_tasks(self):
        return sum(
            [0 if s.is_finished() else s.get_subtask_count()
             for s in self.subtasks]
        )

    def get_tasks_left(self):
        return self.get_active_tasks()

    def get_progress(self) -> float:
        num_total = self.get_total_tasks()
        if num_total == 0:
            return 0.0

        tasks_left = self.get_tasks_left()

        assert num_total >= tasks_left

        progress = (num_total - tasks_left) / num_total

        return progress

    def get_results(self, subtask_id):
        subtask = self._find_vbrsubtask_by_id(subtask_id)
        results = subtask.get_result()
        return results.files if results else []

    @classmethod
    def calculate_subtask_budget(cls, task_definition: TaskDefinition) -> int:
        assert isinstance(task_definition, WasmTaskDefinition)
        num_payable_subtasks = len(task_definition.options.subtasks) * \
                               (cls.REDUNDANCY_FACTOR + 1)
        return task_definition.budget // num_payable_subtasks

    @property
    def subtask_price(self) -> int:
        """WASM subtask_price is calculated based on user provided budget.
        """
        sub_price: int = self.task_definition.budget // self.get_total_tasks()
        logger.debug("subtask price: %d", sub_price)
        return sub_price

    def _load_requestor_perf(self):
        try:
            cpu_usage_str = golem.model.Performance.get(
                golem.model.Performance.environment_id ==
                WasmTaskEnvironment.ENV_ID
            ).cpu_usage
            cpu_usage: float = float(cpu_usage_str)
        except golem.model.Performance.DoesNotExist:
            cpu_usage: float = 1.0 / NANOSECOND

        self.REQUESTOR_MARKET_STRATEGY.set_my_usage_benchmark(
            cpu_usage * NANOSECOND)

    def restart_subtask(
            self,
            subtask_id,
            new_state: Optional[SubtaskStatus] = None,
    ):
        for vbr_subtask in self.subtasks:
            try:
                vbr_subtask.restart_subtask(subtask_id)
            except KeyError:
                pass
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.restarted


class WasmTaskBuilder(CoreTaskBuilder):
    TASK_CLASS: Type[WasmTask] = WasmTask

    @classmethod
    def build_full_definition(
            cls, task_type: 'CoreTaskTypeInfo',
            dictionary: Dict[str, Any]) -> TaskDefinition:
        options = dictionary['options']

        # Resources are generated from 'input_dir' later on.
        dictionary['resources'] = []
        # Subtasks count is determined by the amount of subtask info provided.
        dictionary['subtasks_count'] = len(options['subtasks'])

        task_def: Any = super().build_full_definition(task_type, dictionary)
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

        if 'budget' not in dictionary:
            logger.warning("Assigning task default budget: %d",
                           task_def.budget / denoms.ether)
        else:
            task_def.budget = round(dictionary.get('budget') * denoms.ether)

        return task_def

    @classmethod
    def get_output_path(
            cls,
            dictionary: Dict[str, Any],
            definition: 'TaskDefinition') -> str:
        options = dictionary['options']

        if 'output_path' in options:
            output_path = options['output_path']
        else:
            output_path = options['output_dir']

        return os.path.join(output_path, '/')


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
