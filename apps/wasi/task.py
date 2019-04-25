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
from apps.wasi.environment import WasiTaskEnvironment
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus


class WasiTaskOptions(Options):
    class SubtaskOptions:
        def __init__(self, name: str, exec_args: List[str]) -> None:
            self.name: str = name
            self.exec_args: List[str] = exec_args

    def __init__(self) -> None:
        super().__init__()
        self.bin = ''
        self.workdir = ''
        self.subtasks: Dict[str, WasiTaskOptions.SubtaskOptions] = {}

    def _subtasks(self) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        for subtask_name, subtask_opts in self.subtasks.items():
            yield subtask_name, {
                'name': subtask_name,
                'bin': self.bin,
                'workdir': PurePath(self.workdir).name,
                'exec_args': subtask_opts.exec_args
            }

    def get_subtask_iterator(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        # The generator has to be listed first because the resulting iterator
        # has to be picklable.
        return iter(list(self._subtasks()))


class WasiTaskDefinition(TaskDefinition):
    def __init__(self) -> None:
        super().__init__()
        self.options = WasiTaskOptions()
        self.task_type = 'WASI'

    def add_to_resources(self) -> None:
        self.resources = [self.options.workdir]


class WasiTaskVerifier(CoreVerifier):
    def __init__(self,
                 verification_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.subtask_info = None
        self.results = None

        if verification_data:
            self.subtask_info = verification_data['subtask_info']
            self.results = verification_data['results']


class WasiTask(CoreTask):
    ENVIRONMENT_CLASS = WasiTaskEnvironment
    VERIFIER_CLASS = WasiTaskVerifier

    JOB_ENTRYPOINT = 'python3 /golem/scripts/job.py'

    def __init__(self, total_tasks: int, task_definition: WasiTaskDefinition,
                 root_path: Optional[str] = None, owner: Node = None) -> None:
        super().__init__(
            total_tasks=total_tasks, task_definition=task_definition,
            root_path=root_path, owner=owner
        )
        self.options: WasiTaskOptions = task_definition.options
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

        output_dir_path = Path(self.options.workdir, subtask_name)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        for result_file in result_files:
            print(result_file)
            output_file_path = output_dir_path / PurePath(result_file).name
            with open(result_file, 'rb') as f_in,\
                    open(output_file_path, 'wb') as f_out:
                f_out.write(f_in.read())

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        next_subtask_name, next_extra_data = self.get_next_subtask_extra_data()

        next_extra_data['workdir'] = ''

        return self._new_compute_task_def(
            subtask_id=self.create_subtask_id(), extra_data=next_extra_data
        )


class WasiTaskBuilder(CoreTaskBuilder):
    TASK_CLASS: Type[WasiTask] = WasiTask

    @classmethod
    def build_full_definition(cls, task_type: 'CoreTaskTypeInfo',
                              dictionary: Dict[str, Any]) -> WasiTaskDefinition:
        dictionary['resources'] = []
        dictionary['options']['output_path'] = ''
        dictionary['subtasks_count'] = len(dictionary['options']['subtasks'])

        task_def = super().build_full_definition(task_type, dictionary)

        options = dictionary['options']
        task_def.options.bin = options['bin']
        task_def.options.workdir = options['workdir']

        task_def.options.subtasks = {
            name: WasiTaskOptions.SubtaskOptions(
                name, subtask_opts['exec_args']
            )
            for name, subtask_opts in options['subtasks'].items()
        }

        return task_def


class WasiBenchmarkTask(WasiTask):
    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        ctd = self.query_extra_data_for_test_task()
        return self.ExtraData(ctd)


class WasiBenchmarkTaskBuilder(WasiTaskBuilder):
    TASK_CLASS: Type[WasiTask] = WasiBenchmarkTask


class WasiTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self) -> None:
        super().__init__(
            'WASI', WasiTaskDefinition, WasiTaskOptions, WasiTaskBuilder
        )
