from copy import deepcopy
from pathlib import Path, PurePath
from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple, Type

from golem_messages.message import ComputeTaskDef
from golem_messages.datastructures.p2p import Node

from apps.core.task.coretask import (
    CoreTask,
    CoreTaskBuilder,
    CoreTaskTypeInfo,
    CoreVerifier
)
from apps.core.task.coretaskstate import Options, TaskDefinition
from apps.wasm.environment import WasmTaskEnvironment
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus


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


class WasmTaskVerifier(CoreVerifier):
    def __init__(self,
                 verification_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.subtask_info = None
        self.results = None

        if verification_data:
            self.subtask_info = verification_data['subtask_info']
            self.results = verification_data['results']


class WasmTask(CoreTask):
    ENVIRONMENT_CLASS = WasmTaskEnvironment
    VERIFIER_CLASS = WasmTaskVerifier

    JOB_ENTRYPOINT = 'python3 /golem/scripts/job.py'

    def __init__(self, total_tasks: int, task_definition: WasmTaskDefinition,
                 root_path: Optional[str] = None, owner: Node = None) -> None:
        super().__init__(
            total_tasks=total_tasks, task_definition=task_definition,
            root_path=root_path, owner=owner
        )
        self.options: WasmTaskOptions = task_definition.options
        self.subtask_names: Dict[str, str] = {}
        self.subtask_iterator = self.options.get_subtask_iterator()

    def get_next_subtask_extra_data(self) -> Tuple[str, Dict[str, Any]]:
        next_subtask_name, next_subtask_params = next(self.subtask_iterator)
        return next_subtask_name, {
            'entrypoint': self.JOB_ENTRYPOINT,
            **next_subtask_params
        }

    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        next_subtask_name, next_extra_data = self.get_next_subtask_extra_data()
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

        return Task.ExtraData(ctd=ctd)

    def accept_results(self, subtask_id: str, result_files: List[str]) -> None:
        super().accept_results(subtask_id, result_files)
        self.num_tasks_received += 1

        subtask_name = self.subtask_names[subtask_id]

        output_dir_path = Path(self.options.output_dir, subtask_name)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        for result_file in result_files:
            output_file_path = output_dir_path / PurePath(result_file).name
            with open(result_file, 'rb') as f_in,\
                    open(output_file_path, 'wb') as f_out:
                f_out.write(f_in.read())

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
        dictionary['subtasks_count'] = len(dictionary['options']['subtasks'])

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
