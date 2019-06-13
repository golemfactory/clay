from copy import deepcopy
from pathlib import Path, PurePath
from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple, Type
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

logger = logging.getLogger("apps.wasm")


class WasmTaskOptions(Options):
    VERIFICATION_FACTOR = 2

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
    CALLBACKS = {}

    def __init__(self, total_tasks: int, task_definition: WasmTaskDefinition,
                 root_path: Optional[str] = None, owner: Node = None) -> None:
        super().__init__(
            total_tasks=total_tasks, task_definition=task_definition,
            root_path=root_path, owner=owner
        )
        self.options: WasmTaskOptions = task_definition.options
        self.subtask_names: Dict[str, str] = {}
        self.subtask_iterator = self.options.get_subtask_iterator()

        self.results: Dict[str, Dict[str, list]] = {}
        self.next_actor = None
        self.reputation_ranking = ReputationRanking()
        self.reputation_view = ReputationRankingView(self.reputation_ranking)

    def get_next_subtask_extra_data(self) -> Tuple[str, Dict[str, Any]]:
        next_subtask_name, next_subtask_params = next(self.subtask_iterator)
        return next_subtask_name, {
            'entrypoint': self.JOB_ENTRYPOINT,
            **next_subtask_params
        }

    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        next_subtask_name, next_extra_data = self.get_next_subtask_extra_data()
        self.last_task += 1

        ctd = self._new_compute_task_def(
            subtask_id=self.create_subtask_id(), extra_data=next_extra_data,
            perf_index=perf_index
        )
        sid = ctd['subtask_id']

        self.subtask_names[sid] = next_subtask_name

        self.subtasks_given[sid] = deepcopy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["subtask_id"] = sid

        self.next_actor = None

        return Task.ExtraData(ctd=ctd)

    def computation_finished(self, subtask_id, task_result,
                             verification_finished=None):
        logger.info("Called in WasmTask")
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return
        self.interpret_task_results(subtask_id, task_result)

        subtask_name = self.subtask_names[subtask_id]
        results_dict = self.results.get(subtask_name)
        self.subtasks_given[subtask_id]["status"] = SubtaskStatus.verifying
        WasmTask.CALLBACKS[subtask_id] = verification_finished

        if len(results_dict) < 2:
            return

        # VbR time!
        results = [results_dict[key] for key in results_dict]
        if self.verify_results(results):
            self.save_results(self.subtask_names[subtask_id], results[0])
            self.accept([sid for sid in results_dict])
        # else:
        #     self.computation_failed(subtask_id)

    def verify_results(self, results: List[list]) -> bool:
        for r1, r2 in zip(*results):
            with open(r1, 'rb') as f1, open(r2, 'rb') as f2:
                b1 = f1.read()
                b2 = f2.read()
                if b1 != b2:
                    logger.info("Verification of task failed")
                    return False

        logger.info("Verification of task was successful")
        return True

    def accept(self, subtask_ids: List[str]) -> None:
        for sid in subtask_ids:
            subtask = self.subtasks_given[sid]
            subtask["status"] = SubtaskStatus.finished
            node_id = self.subtasks_given[sid]['node_id']
            logger.info("Accepting results for subtask %s", sid)
            TaskClient.assert_exists(node_id, self.counting_nodes).accept()
            self.num_tasks_received += 1
            WasmTask.CALLBACKS[sid]()

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
        next_subtask_name, next_extra_data = self.get_next_subtask_extra_data()

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

        name = self.subtask_names[subtask_id]
        self.results.setdefault(name, {})[subtask_id] = results

    # def finished_computation(self):
    #     logger.info("Finished computaing Wasm task")
    #     return self.num_tasks_received == self.total_tasks * 2

        def should_accept_client(self, node_id: str) -> AcceptClientVerdict:
        """Deciding whether to accept particular node_id for next task computation.

        Arguments:
            node_id {str} -- Node offered to compute next task

        Returns:
            AcceptClientVerdict -- When AcceptClientVerdict.ACCEPTED value is returned the task will get a call to
            `query_extra_data` with corresponding `node_id`. On AcceptClientVerdict.REJECTED and
            AcceptClientVerdict.SHOULD_WAIT the node offer will be turned down, but might appear
            in subsequent `should_accept_client` invocation. The only difference between REJECTED
            and SHOULD_WAIT is the log message.
        """

        """TODO
        What this method should do for VbR:
        Coordinate with `query_extra_data` and `computation_finished` on what node has been
        assigned to particular task and has completed it to make sure that particular Node is
        not computing the same subtask twice, because this would not provide the desired computation provider redundancy.
        By "The same subtask twice" I mean two redundant jobs of the same subtask.

        Handling a negative scenario where a subtask computation failed must be addressed here too, only if
        we decide to change:

        if client.rejected():
            return AcceptClientVerdict.REJECTED
        elif finishing >= max_finishing or \
                client.started() - finishing >= max_finishing:
            return AcceptClientVerdict.SHOULD_WAIT

        This part of the routine depends on `CoreTask._mark_subtask_failed`. If we change this logic we should coordinate
        with or override  `CoreTask.computation_failed` and `CoreTask.restart_subtask`. Also, in `computation_finished`
        we get some results, but we might decide that they are undoubtedly wrong and we need to communicate it to this method.
        To sum up negative scenario, we have three cases:
            - task has been restarted
            - task has failed on provider side (exception or segfault)
            - task has not passed sanity check (if any) in computation_finished
        All of them should somehow affect choosing next provider here.
        """

        """If we have already chosen the next actor, then lets wait for OfferPool to provide him.
        """
        if self.next_actor:
            if self.next_actor.id == node_id:
                return AcceptClientVerdict.ACCEPTED
            else:
                return AcceptClientVerdict.REJECTED

        # Add node to ReputationRanking
        # TODO Add method to check if this node_id exists in ReputationRanking
        # So we don't have to traverse entire list.
        if node_id not in list(map(lambda actor: actor.id, self.reputation_ranking.get_actors()))
            self.reputation_ranking.add_actor(Actor(node_id))

        if len(self.reputation.get_actors()) < self.options.VERIFICATION_FACTOR:
            logger.info('Not enough providers, postponing')
            return AcceptClientVerdict.SHOULD_WAIT

        """For now I assumed that there is subtask `s` instance of some class Subtask
        that has method "get_next_actor" implemented. Probably this is a forward call to it's
        internal VerificationByRedundancy instance. @kubkon
        """
        for s in self.subtasks:
            self.next_actor = s.get_next_actor()
            if self.next_actor:
                """Since query_extra_data is called immediately after this function returns we can
                safely save subtask that yielded next actor to retrieve ComputeTaskDef from it.
                """
                self.next_subtask = s
                return AcceptClientVerdict.ACCEPTED

        """No subtask has yielded next actor meaning that there is no work to be done at the moment
        """
        return AcceptClientVerdict.SHOULD_WAIT

        # if client.rejected():
        #     return AcceptClientVerdict.REJECTED
        # elif finishing >= max_finishing or \
        #         client.started() - finishing >= max_finishing:
        #     return AcceptClientVerdict.SHOULD_WAIT

        # return AcceptClientVerdict.ACCEPTED


class WasmTaskBuilder(CoreTaskBuilder):
    TASK_CLASS: Type[WasmTask] = WasmTask

    @classmethod
    def build_full_definition(cls, task_type: 'CoreTaskTypeInfo',
                              dictionary: Dict[str, Any]) -> WasmTaskDefinition:
        # Resources are generated from 'input_dir' later on.
        dictionary['resources'] = []
        # Output is determined from 'output_dir' later on.
        dictionary['options']['output_path'] = ''
        # Subtasks count is determined by the amount of subtask info provided.
        dictionary['subtasks_count'] = 2 * len(dictionary['options']['subtasks'])

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
    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
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
