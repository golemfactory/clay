import enum
import logging
from copy import copy
from typing import Optional, Dict, List, NamedTuple, Set

import cloudpickle as pickle
import enforce
from golem_messages.message import ComputeTaskDef

from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.runf.runfenvironment import RunFEnvironment
from apps.runf.task.runftaskstate import RunFDefaults, RunFOptions
from apps.runf.task.runftaskstate import RunFDefinition
from apps.runf.task.verifier import RunFVerifier
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.runf")


class RunFTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "Dummy",
            RunFDefinition,
            RunFDefaults(),
            RunFOptions,
            RunFBuilder
        )


SubtaskID = str
PickledObject = bytes
PickledCallable = bytes


class SubtaskData(NamedTuple):
    args: List[PickledObject]
    kwargs: Dict[str, PickledObject]
    function: PickledCallable
    TYPE: str = "SubmitNewTask"


class SubtaskDefinition(NamedTuple):
    subtask_id: SubtaskID
    data: SubtaskData


class CheckSubtaskStatus(NamedTuple):
    subtask_id: SubtaskID
    TYPE: str = "CheckSubtaskStatus"


class FinishComputations(NamedTuple):
    TYPE: str = "FinishComputations"


class RunFSubtaskStatus(NamedTuple):
    """
        :status indicates status of subtask
        :result contains serialized output from function. it is present only
        if status == finished
        """

    class Status(enum.Enum):
        started = enum.auto()
        computing = enum.auto()
        timeout = enum.auto()
        finished = enum.auto()

    status: Status
    subtask_id: SubtaskID
    result: Optional[PickledObject]


@enforce.runtime_validation(group="runf")
class RunF(CoreTask):
    ENVIRONMENT_CLASS = RunFEnvironment
    VERIFIER_CLASS = RunFVerifier

    RESULT_EXT = ".result"

    def __init__(self,
                 total_tasks: int,
                 task_definition: RunFDefinition,
                 root_path=None,
                 owner=None):
        super().__init__(
            owner=owner,
            task_definition=task_definition,
            root_path=root_path,
            total_tasks=total_tasks
        )
        self.subtasks_definitions: Dict[SubtaskID, SubtaskDefinition] = {}
        self.waiting_for_processing_queue: Set[SubtaskID] = set()
        self.subtasks_being_processed: Set[SubtaskID] = set()
        self.finished_subtasks: Dict[SubtaskID, PickledObject] = {}
        self.finished = False

    def short_extra_data_repr(self, extra_data):
        return "Runf extra_data: {}".format(extra_data)

    def _extra_data(self, perf_index=0.0) -> ComputeTaskDef:
        subtask_id = self.waiting_for_processing_queue.pop()  # TODO do it non-blocking way?
        data = self.subtasks_definitions[subtask_id].data
        extra_data = {
            "args": data.args,
            "kwargs": data.kwargs,
            "function": data.function,
            "RESULT_EXT": self.RESULT_EXT
        }

        return self._new_compute_task_def(subtask_id,
                                          extra_data,
                                          perf_index=perf_index)

    @coretask.accepting
    def query_extra_data(self,
                         perf_index: float,
                         num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        if self.finished:
            return None  # TODO what should I do in such situation?
        
        logger.debug("Query extra data on runftask")

        ctd = self._extra_data(perf_index)
        sid = ctd['subtask_id']

        # TODO these should all be in CoreTask
        self.subtasks_given[sid] = copy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["result_extension"] = self.RESULT_EXT
        self.subtasks_given[sid]["shared_data_files"] = \
            self.task_definition.shared_data_files
        self.subtasks_given[sid]["subtask_id"] = sid

        return self.ExtraData(ctd=ctd)

    def accept_results(self, subtask_id: SubtaskID, result_files):
        super().accept_results(subtask_id, result_files)
        self.counting_nodes[
            self.subtasks_given[subtask_id]['node_id']
        ].accept()
        self.num_tasks_received += 1

        # TODO find true result file
        assert len(result_files) == 1
        result_file = result_files[0]
        with open(result_file, "rb") as f:
            result = pickle.load(f)

        logger.info("Subtask finished")

        self.finished_subtasks[subtask_id] = result
        self.subtasks_being_processed.remove(subtask_id)

    def _end_computation(self):
        logger.info("Ending computation")

        self.finished = True
        self.waiting_for_processing_queue = set()
        self.subtasks_being_processed = set()  # TODO I should send "abort" signal

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        pass
        # exd = self._extra_data()
        # size = self.task_definition.options.subtask_data_size
        # char = self.TESTING_CHAR
        # exd['extra_data']["subtask_data"] = char * size
        # return exd

    def _put_new_task_to_queue(self, data: SubtaskData) -> str:
        subtask_id = self.__get_new_subtask_id()
        self.subtasks_definitions[subtask_id] = SubtaskDefinition(
            subtask_id=subtask_id,
            data=data
        )
        self.waiting_for_processing_queue.add(subtask_id)
        return subtask_id

    def react_to_state_update(self, subtask_id: SubtaskID, data: Dict):
        pass

    def _check_subtask_status(self, subtask_id: SubtaskID) -> RunFSubtaskStatus:
        if subtask_id in self.waiting_for_processing_queue:
            return RunFSubtaskStatus(
                status=RunFSubtaskStatus.status.started,
                subtask_id=subtask_id,
                result=None
            )
        elif subtask_id in self.subtasks_being_processed:
            return RunFSubtaskStatus(
                status=RunFSubtaskStatus.status.computing,
                subtask_id=subtask_id,
                result=None
            )
        elif subtask_id in self.finished_subtasks:
            return RunFSubtaskStatus(
                status=RunFSubtaskStatus.status.finished,
                subtask_id=subtask_id,
                result=self.finished_subtasks[subtask_id]
            )
        else:
            # TODO what about timeout
            return RunFSubtaskStatus(
                status=RunFSubtaskStatus.status.timeout,
                subtask_id=subtask_id,
                result=None
            )

    def react_to_message(self, data: Dict) -> RunFSubtaskStatus:
        # TODO do the deserialization & processing in a beter way
        if data["TYPE"] == SubtaskData.TYPE:
            data = SubtaskData(**data)
            subtask_id = self._put_new_task_to_queue(data)
            status = RunFSubtaskStatus(
                status=RunFSubtaskStatus.Status.started,
                subtask_id=subtask_id,
                result=None
            )
            return status

        elif data["TYPE"] == CheckSubtaskStatus.TYPE:
            data = CheckSubtaskStatus(**data)
            status = self.check_subtask_status(data.subtask_id)
            return status

        elif data["TYPE"] == FinishComputations.TYPE:
            self._end_computation()


class RunFBuilder(CoreTaskBuilder):
    TASK_CLASS = RunF

    @classmethod
    def build_dictionary(cls, definition: RunFDefinition):
        dictionary = super().build_dictionary(definition)
        opts = dictionary['options']

        opts["function"] = bytes(definition.options.function)
        opts["kwargs"] = dict(definition.options.kwargs)
        opts["args"] = list(definition.options.args)

        return dictionary

    @classmethod
    def build_full_definition(cls, task_type: RunFTypeInfo, dictionary):
        # dictionary comes from GUI
        opts = dictionary["options"]

        definition: RunFDefinition = super().build_full_definition(task_type,
                                                                   dictionary)

        function = bytes(opts.get("function",
                                  definition.options.function))
        kwargs = dict(opts.get("kwargs",
                               definition.options.kwargs))
        args = list(opts.get("args",
                             definition.options.args))

        definition.options.function = function
        definition.options.kwargs = kwargs
        definition.options.args = args
        return definition


# comment that line to enable type checking
enforce.config({'groups': {'set': {'runf': False}}})
