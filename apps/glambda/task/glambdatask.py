import base64
from pydispatch import dispatcher
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
    SUBTASK_CALLBACKS: Dict[str, Any] = {}

    # pylint:disable=too-many-arguments
    def __init__(self,
                 task_definition: TaskDefinition,
                 owner: dt_p2p.Node,
                 dir_manager: DirManager,
                 resource_size=None,
                 root_path: Optional[str] = None,
                 total_tasks=1) -> None:
        super().__init__(task_definition,
                         owner,
                         self.MAX_PENDING_CLIENT_RESULTS,
                         resource_size,
                         root_path,
                         total_tasks)

        self.dir_manager = dir_manager

        '''A serialized representation of method/algorithms to be computed
        provider side. For serialisation details see
        GLambdaTask::PythonObjectSerializer class.
        '''
        self.method = task_definition.options.method

        '''A serialized representation of arguments to be provided
        for the algorithm. For serialisation details see
        GLambdaTask::PythonObjectSerializer class.
        '''
        self.args = self._decompose_args(task_definition.options.args)
        self.multitask = isinstance(self.args, list)

        self.verification_metadata = task_definition.options.verification

        '''
        See class GLambdaTask::VerificationMethod
        '''
        self.verification_type = self.verification_metadata['type']

        '''Defining how self.outputs are structured.
        For multitask scenario results of subtasks are placed within
        task output directory in a folder named after their index
        in `task_definition.options.args` list e.g. subtask_0 results will
        be placed in: task_id/0/results.
        For a single task scenario subtask's results are placed directly
        into the task output directory.
        '''
        task_output_dir = dir_manager.get_task_output_dir(
            task_definition.task_id
        )
        if self.multitask:
            self.outputs = [
                os.path.join(task_output_dir, str(index), output)
                for output in task_definition.options.outputs
                for index, _ in enumerate(self.args)
            ]
        else:
            self.outputs = [
                os.path.join(task_output_dir, output)
                for output in task_definition.options.outputs
            ]

    def _decompose_args(self, args):
        '''
        Create a list of serialized objects from a serialized list of objects.
        '''
        deser_obj = self.PythonObjectSerializer.deserialize(args)
        if isinstance(deser_obj, list):
            return [
                self.PythonObjectSerializer.serialize(arg)
                for arg in deser_obj
            ]
        return args

    def send_app_data(self, app_data):
        dispatcher.send(signal='golem.app_data',
                        sender=dispatcher.Anonymous,
                        task_id=self.header.task_id,
                        app_data=app_data)

    def _get_subtask_data(self, subtask_seq_id=None) -> Dict[str, Any]:
        if subtask_seq_id is not None:
            args = self.args[subtask_seq_id]
        else:
            args = self.args
        return {
            'method': self.method,
            'args': args,
            'content_type': None,
            'entrypoint': 'python3 /golem/scripts/job.py'
        }

    def query_extra_data(self, perf_index: float,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:

        next_task = self._eval_next_task()
        if self.multitask:
            extra_data = self._get_subtask_data(next_task)
        else:
            extra_data = self._get_subtask_data()

        ctd = self._new_compute_task_def(
            subtask_id=self.create_subtask_id(),
            extra_data=extra_data,
            perf_index=perf_index
        )

        subtask_id = ctd['subtask_id']

        self.send_app_data({
            'type': 'SubtaskCreatedEvent',
            'subtask_id': subtask_id,
            'subtask_seq_index': next_task
        })

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
        self.subtasks_given[subtask_id]['node_id'] = node_id
        self.subtasks_given[subtask_id]['subtask_seq_id'] = next_task
        self.subtasks_given[subtask_id]['subtask_timeout'] = \
            self.header.subtask_timeout

        return Task.ExtraData(ctd=ctd)

    def _eval_next_task(self):
        '''Returns next task index. Golem task driver requires last_task to be
        equal to total_tasks AND num_failed_subtasks to be not bigger than zero
        to terminate the task. Once last_task reaches total_tasks we only
        manipulate num_failed_subtasks.
        '''
        if self.last_task != self.total_tasks:
            self.last_task += 1
            # Return last_task - 1 because we want first task to be 0.
            return self.last_task - 1
        for sub in self.subtasks_given.values():
            if sub['status'] \
                    in [SubtaskStatus.failure, SubtaskStatus.restarted]:
                sub['status'] = SubtaskStatus.resent
                self.num_failed_subtasks -= 1
                return sub['subtask_seq_id']
        return None

    def query_extra_data_for_test_task(self) -> TaskDefinition:
        return self._new_compute_task_def(
            subtask_id=self.create_subtask_id(),
            extra_data=self._get_subtask_data()
        )

    def _move_subtask_results_to_task_output_dir(self, subtask_id) -> None:
        '''Defines how subtask results are placed in task output directory.
        For multitask scenario we create a subtask directory tree for results
        and for single task scenario we put results directly into task
        output directory.
        '''

        task_temp_dir = self.dir_manager.get_task_temporary_dir(
            self.task_definition.task_id
        )
        task_output_dir = self.dir_manager.get_task_output_dir(
            self.task_definition.task_id
        )

        if self.multitask:
            output_directory = os.path.join(
                task_output_dir,
                str(self.subtasks_given[subtask_id]['subtask_seq_id'])
            )
            os.mkdir(output_directory)
        else:
            output_directory = task_output_dir

        subtask_outdir = os.path.join(task_temp_dir, subtask_id)
        subtask_outdir_content = os.listdir(subtask_outdir)

        for obj in subtask_outdir_content:
            shutil.move(
                os.path.join(subtask_outdir, obj),
                os.path.join(output_directory, obj)
            )

    def _task_verified(self, subtask_id, verif_cb) -> None:
        self.accept_results(subtask_id, None)
        verif_cb()
        self._move_subtask_results_to_task_output_dir(subtask_id)

    def computation_finished(self, subtask_id, task_result,
                             verification_finished=None) -> None:
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.verifying

        if self.verification_type == self.VerificationMethod.NO_VERIFICATION:
            verdict = SubtaskVerificationState.VERIFIED
        elif self.verification_type == \
                self.VerificationMethod.EXTERNALLY_VERIFIED:
            self.SUBTASK_CALLBACKS[subtask_id] = verification_finished
            self.results[subtask_id] = task_result
            verdict = SubtaskVerificationState.IN_PROGRESS
            self.send_app_data({
                'type': 'VerificationRequest',
                'subtask_id': subtask_id,
                'results': task_result
            })
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

    def external_verify_subtask(self, subtask_id, verdict):
        verif_cb = self.SUBTASK_CALLBACKS.pop(subtask_id)
        self._handle_verification_verdict(subtask_id, verdict, verif_cb)
        return None


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
