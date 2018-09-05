import logging
from copy import copy
from typing import Optional, Dict, Set
from uuid import uuid4

import enforce
from golem_messages.message import ComputeTaskDef

from apps.blender.verification_queue import VerificationQueue
from apps.core.task import coretask
from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.runf.runfenvironment import RunFEnvironment
from apps.runf.task.queue_helpers import Queue
from apps.runf.task.runf_helpers import SubtaskID, SubtaskDefinition, \
    SubtaskData
from apps.runf.task.runftaskstate import RunFDefaults, RunFOptions
from apps.runf.task.runftaskstate import RunFDefinition
from apps.runf.task.verifier import RunFVerifier
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.runf")


class RunFTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "RunF",
            RunFDefinition,
            RunFDefaults(),
            RunFOptions,
            RunFBuilder
        )


@enforce.runtime_validation(group="runf")
class RunF(CoreTask):
    ENVIRONMENT_CLASS = RunFEnvironment
    VERIFIER_CLASS = RunFVerifier
    VERIFICATION_QUEUE = None

    RESULT_EXT = "result"

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
        self.submitted_subtasks: Queue = Queue(
            name=task_definition.task_id,
            host=task_definition.options.queue_host,
            port=task_definition.options.queue_port
        )
        self.waiting_queue: Set[SubtaskID] = set()
        self.subtasks_being_processed: Set[SubtaskID] = set()
        self.finished_subtasks: Queue = Queue(
            name=task_definition.task_id,
            host=task_definition.options.queue_host,
            port=task_definition.options.queue_port
        )
        self.finished = False

    # S = 0
    # E = 1000

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["submitted_subtasks"]
        del state["finished_subtasks"]
        # if "VERIFICATION_QUEUE" in state:  # TODO why do I need this
        #     del state["VERIFICATION_QUEUE"]
        # l = list(state.items())
        # S = self.S
        # E = self.E
        # return dict(l[S:E])
        del state["listeners"]  # TODO why?
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        td = self.task_definition
        self.submitted_subtasks: Queue = Queue(
            name=td.task_id,
            host=td.options.queue_host,
            port=td.options.queue_port
        )
        self.finished_subtasks: Queue = Queue(
            name=td.task_id,
            host=td.options.queue_host,
            port=td.options.queue_port
        )
        self.listeners = []
        # self.VERIFICATION_QUEUE = VerificationQueue()  # TODO why do I need this

    def short_extra_data_repr(self, extra_data):
        return "Runf extra_data: {}".format(extra_data)

    def _extra_data(self, perf_index=0.0) -> ComputeTaskDef:
        data = self._get_example_data()
        queue_id = str(uuid4())
        # queue_id, data = self.submitted_subtasks.get_nowait()

        subtask_id = self.create_subtask_id()

        self.subtasks_definitions[subtask_id] = SubtaskDefinition(
            subtask_id=subtask_id,
            queue_id=queue_id,
            data=data
        )
        self.subtasks_being_processed.add(subtask_id)

        extra_data = {
            "data": data,
            "RESULT_EXT": self.RESULT_EXT
        }

        return self._new_compute_task_def(
            subtask_id,
            extra_data,
            perf_index=perf_index
        )

    @coretask.accepting
    def query_extra_data(self,
                         perf_index: float,
                         num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        # if self.finished or self.submitted_subtasks.empty():
        #     return None  # TODO what should I do in such situation?

        logger.debug("Query extra data on runftask")

        ctd = self._extra_data(perf_index)
        sid = ctd['subtask_id']

        # TODO these should all be in CoreTask
        self.subtasks_given[sid] = copy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["result_extension"] = self.RESULT_EXT

        self.subtasks_given[sid]["subtask_id"] = sid

        return self.ExtraData(ctd=ctd)

    def accept_results(self, subtask_id: SubtaskID, result_files):
        super().accept_results(subtask_id, result_files)
        self.counting_nodes[
            self.subtasks_given[subtask_id]['node_id']
        ].accept()
        self.num_tasks_received += 1

        result_file = [t for t in result_files if self.RESULT_EXT in t]
        assert len(result_file) == 1
        result_file = result_file[0]

        # TODO this is probably unncecesary
        # as we can just return the path of the result file
        with open(result_file, "r") as f:
            result = f.read()

        logger.info("Subtask finished")

        queue_id = self.subtasks_definitions[subtask_id].queue_id
        self.finished_subtasks.set(f"{queue_id}-OUT", result)  # TODO document this
        self.subtasks_being_processed.remove(subtask_id)

    def _end_computation(self):
        logger.info("Ending computation")

        self.finished = True
        del self.waiting_queue
        self.subtasks_being_processed = set()  # TODO I should send "abort" signal

    def _get_example_data(self):
        ###################################################
        # TODO code from golem_remote/encoding.py
        # change that when golem_remote will be published to pypi
        import base64
        import codecs
        import cloudpickle as pickle
        import json
        from typing import Any

        def encode_obj_to_str(obj: Any):
            result = pickle.dumps(obj)
            result = base64.b64encode(result)
            result = codecs.decode(result, "ascii")
            result = {"r": result}
            result = json.dumps(result)
            return result
        ###################################################

        f = lambda x: x + x
        args = [2]
        kwargs = {}
        # data = SubtaskData(
        #     function=f,
        #     args=args,
        #     kwargs=kwargs
        # )
        data = {
            "function": f,
            "args": args,
            "kwargs": kwargs
        }
        return encode_obj_to_str(data)

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        queue_id = str(uuid4())
        data = self._get_example_data()
        subtask_id = "subtask12345"

        self.subtasks_definitions[subtask_id] = SubtaskDefinition(
            subtask_id=subtask_id,
            queue_id=queue_id,
            data=data
        )
        self.subtasks_being_processed.add(subtask_id)

        extra_data = {
            "data": data,
            "RESULT_EXT": self.RESULT_EXT
        }

        return self._new_compute_task_def(
            subtask_id,
            extra_data,
        )

    def react_to_state_update(self, subtask_id: SubtaskID, data: Dict):
        pass



class RunFBuilder(CoreTaskBuilder):
    TASK_CLASS = RunF

    @classmethod
    def build_dictionary(cls, definition: RunFDefinition):
        dictionary = super().build_dictionary(definition)
        opts = dictionary['options']

        opts["queue_port"] = int(definition.options.queue_port)
        opts["queue_host"] = str(definition.options.queue_host)

        return dictionary

    @classmethod
    def build_full_definition(cls, task_type: RunFTypeInfo, dictionary):
        # dictionary comes from GUI
        opts = dictionary["options"]

        definition: RunFDefinition = super().build_full_definition(task_type,
                                                                   dictionary)

        queue_port = int(opts.get("queue_port",
                                  definition.options.queue_port))
        queue_host = str(opts.get("queue_host",
                               definition.options.queue_host))

        definition.options.queue_port = queue_port
        definition.options.queue_host = queue_host
        return definition


class RunFMod(RunF):
    def query_extra_data(self, *args, **kwargs):
        ctd = self.query_extra_data_for_test_task()
        return self.ExtraData(ctd=ctd)


class RunFBuilderMod(RunFBuilder):
    TASK_CLASS = RunFMod


# comment that line to enable type checking
enforce.config({'groups': {'set': {'runf': False}}})
