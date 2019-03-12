import base64
import logging
import os
import shutil
from enum import IntEnum
from typing import List, Optional, Dict, Any, Type

import cloudpickle
from golem_messages.datastructures import p2p as dt_p2p

from apps.core.task.coretask import CoreTask, CoreTaskBuilder, \
    CoreVerifier
from apps.core.task.coretaskstate import TaskDefinition, Options
from apps.glambda.glambdaenvironment import GLambdaTaskEnvironment
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task, TaskTypeInfo
from golem.task.taskstate import SubtaskStatus
from golem.verificator.verifier import SubtaskVerificationState

logger = logging.getLogger(__name__)


class GLambdaTaskOptions(Options):
    def __init__(self) -> None:
        super().__init__()
        self.method: str = ''
        self.args: str = ''
        self.verification: Dict[str, IntEnum] = {}
        self.outputs: List[str] = []


class GLambdaTaskDefinition(TaskDefinition):
    def __init__(self) -> None:
        super().__init__()
        self.task_type: str = 'GLambda'
        self.options: GLambdaTaskOptions = GLambdaTaskOptions()


class GLambdaTaskTypeInfo(TaskTypeInfo):
    def __init__(self) -> None:
        super().__init__(
            "GLambda",
            GLambdaTaskDefinition,
            GLambdaTaskOptions,
            GLambdaTaskBuilder
        )


# pylint:disable=too-many-instance-attributes
class GLambdaTask(CoreTask):
    class PythonObjectSerializer:
        @classmethod
        def serialize(cls, obj) -> str:
            return base64.b64encode(cloudpickle.dumps(obj)).decode('ascii')

        @classmethod
        def deserialize(cls, obj) -> Any:
            return cloudpickle.loads(base64.b64decode(obj))

    class VerificationMethod():
        NO_VERIFICATION = "None"
        EXTERNALLY_VERIFIED = "External"

    ENVIRONMENT_CLASS = GLambdaTaskEnvironment
    MAX_PENDING_CLIENT_RESULTS = 1

    # pylint:disable=too-many-arguments
    def __init__(self,
                 task_definition: TaskDefinition,
                 owner: dt_p2p.Node,
                 dir_manager: DirManager,
                 max_pending_client_results=MAX_PENDING_CLIENT_RESULTS,
                 resource_size=None,
                 root_path: Optional[str] = None,
                 total_tasks=1) -> None:
        super(GLambdaTask, self).__init__(task_definition, owner,
                                          max_pending_client_results,
                                          resource_size, root_path,
                                          total_tasks)
        self.method = task_definition.options.method
        self.args = task_definition.options.args
        self.verification_metadata = task_definition.options.verification
        self.verification_type = self.verification_metadata['type']
        self.dir_manager = dir_manager
        self.outputs = [
            os.path.join(
                dir_manager.get_task_output_dir(task_definition.task_id),
                output)
            for output in task_definition.options.outputs
        ]

    def _get_subtask_data(self) -> Dict[str, Any]:
        return {
            'method': self.method,
            'args': self.args,
            'content_type': None,
            'entrypoint': 'python3 /golem/scripts/job.py'
        }

    def query_extra_data(self, perf_index: float,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        start_task = self._get_next_task()

        extra_data = self._get_subtask_data()

        ctd = self._new_compute_task_def(
            subtask_id=self.create_subtask_id(),
            extra_data=extra_data,
            perf_index=perf_index
        )

        subtask_id = ctd['subtask_id']

        logger.debug(
            'Created new subtask for task. '
            'task_id=%s, subtask_id=%s, node_id=%s',
            self.header.task_id,
            subtask_id,
            (node_id or '')
        )

        self.subtasks_given[subtask_id] = {
            'subtask_id': subtask_id,
            'subtask_data': extra_data,
        }
        self.subtasks_given[subtask_id]['subtask_id'] = subtask_id
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.starting
        self.subtasks_given[subtask_id]['start_task'] = start_task
        self.subtasks_given[subtask_id]['node_id'] = node_id
        self.subtasks_given[subtask_id]['subtask_timeout'] = \
            self.header.subtask_timeout

        return Task.ExtraData(ctd=ctd)

    def query_extra_data_for_test_task(self) -> TaskDefinition:
        return self._new_compute_task_def(
            subtask_id=self.create_subtask_id(),
            extra_data=self._get_subtask_data()
        )

    def _get_next_task(self) -> Optional[int]:
        if self.last_task != self.total_tasks:
            self.last_task += 1
            start_task = self.last_task
            return start_task
        else:
            for sub in self.subtasks_given.values():
                if sub['status'] \
                        in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                    sub['status'] = SubtaskStatus.resent
                    start_task = sub['start_task']
                    self.num_failed_subtasks -= 1
                    return start_task
        return None

    def _copy_results(self, subtask_id) -> None:
        outdir_content = os.listdir(
            os.path.join(
                self.dir_manager.get_task_temporary_dir(
                    self.task_definition.task_id),
                subtask_id
            )
        )

        for obj in outdir_content:
            shutil.move(
                os.path.join(
                    self.dir_manager.get_task_temporary_dir(
                        self.task_definition.task_id),
                    subtask_id,
                    obj),
                self.dir_manager.get_task_output_dir(
                    self.task_definition.task_id,
                    os.path.basename(obj))
            )

    def _task_verified(self, subtask_id, verif_cb) -> None:
        self.accept_results(subtask_id, None)
        verif_cb()
        self._copy_results(subtask_id)

    def computation_finished(self, subtask_id, task_result,
                             verification_finished=None) -> None:
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return

        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.verifying

        # NOTE: Only VerificationMethod.NO_VERIFICATION is supported at this
        # moment. branch golem^glambda0.2 contains logic for EXTERNALLY_VERIFIED
        # user tasks.
        if self.verification_type == self.VerificationMethod.NO_VERIFICATION:
            verdict = SubtaskVerificationState.VERIFIED
        elif self.verification_type == \
                self.VerificationMethod.EXTERNALLY_VERIFIED:
            self.subtasks_given[subtask_id]['verif_cb'] = verification_finished
            verdict = SubtaskVerificationState.IN_PROGRESS
        try:
            self._handle_verification_verdict(subtask_id, verdict,
                                              verification_finished)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Failed during accepting results %s", e)

    def _handle_verification_verdict(self, subtask_id, verdict,
                                     verif_cb) -> None:
        if verdict == SubtaskVerificationState.VERIFIED:
            self.num_tasks_received += 1
            self._task_verified(subtask_id, verif_cb)
        elif verdict in [SubtaskVerificationState.TIMEOUT,
                         SubtaskVerificationState.WRONG_ANSWER,
                         SubtaskVerificationState.NOT_SURE]:
            self.computation_failed(subtask_id)
            verif_cb()
        else:
            logger.warning("Unhandled verification verdict: %d", verdict)

    def get_output_names(self) -> List[str]:
        return self.outputs


class GLambdaTaskVerifier(CoreVerifier):
    def __init__(self,
                 verification_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        if verification_data:
            self.subtask_info = verification_data['subtask_info']
            self.results = verification_data['results']
        else:
            self.subtask_info = None
            self.results = None

    def _verify_result(self, results: Dict[str, Any]):
        return True


class GLambdaTaskBuilder(CoreTaskBuilder):
    TASK_CLASS: Type[GLambdaTask] = GLambdaTask

    def get_task_kwargs(self, **kwargs):
        kwargs = super().get_task_kwargs(**kwargs)
        kwargs["dir_manager"] = self.dir_manager
        return kwargs

    @classmethod
    def build_minimal_definition(cls, task_type: TaskTypeInfo, dictionary):
        definition = task_type.definition()
        definition.task_type = task_type.name
        definition.compute_on = dictionary.get('compute_on', 'cpu')
        if 'resources' in dictionary:
            definition.resources = set(dictionary['resources'])
        options = dictionary['options']
        definition.subtasks_count = int(dictionary['subtasks_count'])
        definition.options.method = options['method']
        definition.options.args = options['args']
        definition.options.verification = options['verification']
        definition.options.outputs = options['outputs']
        return definition


class GLambdaBenchmarkTask(GLambdaTask):
    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        ctd = self.query_extra_data_for_test_task()
        return self.ExtraData(ctd)


class GLambdaBenchmarkTaskBuilder(GLambdaTaskBuilder):
    TASK_CLASS: Type[GLambdaTask] = GLambdaBenchmarkTask
