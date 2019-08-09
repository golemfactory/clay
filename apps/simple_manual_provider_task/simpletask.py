import logging
from typing import Optional, Dict, Any

import golem_messages
from apps.core.task.coretask import CoreTaskBuilder, CoreTaskTypeInfo
from apps.core.task.coretaskstate import TaskDefinition, Options, TaskDefaults
from apps.core.task.chooseoffermanuallytask import ChooseOfferManuallyTask
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import SubtaskStatus
from golem.verifier import CoreVerifier
from golem.verifier.subtask_verification_state import SubtaskVerificationState

logger = logging.getLogger(__name__)


class SimpleTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = 'alpine'
    DOCKER_TAG = 'latest'
    ENV_ID = 'SIMPLE_MANUAL_TASK'
    SHORT_DESCRIPTION = ''

    def __init__(self):
        super().__init__(additional_images=[DockerImage(
            repository=self.DOCKER_IMAGE,
            tag=self.DOCKER_TAG
        )])


class SimpleTaskOptions(Options):
    def __init__(self):
        super().__init__()
        self.name = None
        self.environment = SimpleTaskEnvironment()


class SimpleTaskDefinition(TaskDefinition):
    def __init__(self):
        super().__init__()
        self.options = SimpleTaskOptions()


class SimpleTaskVerifier(CoreVerifier):
    def __init__(self, verification_data):
        super().__init__(verification_data)
        self.results = verification_data['results']
        self.state = SubtaskVerificationState.WAITING

    def simple_verification(self):
        return True


class SimpleManualTask(ChooseOfferManuallyTask):
    ENVIRONMENT_CLASS = SimpleTaskEnvironment
    VERIFIER_CLASS = SimpleTaskVerifier

    def __init__(self, task_definition: SimpleTaskDefinition,
                 owner: 'dt_p2p.Node', **kwargs):
        super().__init__(task_definition, owner)
        self.task_definition = task_definition
        self.chosen_provider = None

    def initialize(self, dir_manager: DirManager):
        super().initialize(dir_manager)
        self.task_definition.subtasks_count = len(self.task_definition.resources)
        self.total_tasks = len(self.task_definition.resources)

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        self.num_tasks_received += 1

    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        sid = self.create_subtask_id()
        extra_data = {
            'name': self.task_definition.options.name,
            'entrypoint': 'echo {} from {}'.format(self.task_definition.options.name, node_id)
        }
        subtask_num = self._get_next_subtask()

        subtask: Dict[str, Any] = {
            'perf': perf_index,
            'node_id': node_id,
            'subtask_id': sid,
            'subtask_num': subtask_num,
            'status': SubtaskStatus.starting
        }

        self.subtasks_given[sid] = subtask
        subtask_resource = list(self.task_definition.resources)[subtask_num]

        return Task.ExtraData(ctd=self._get_task_computing_definition(
            sid,
            extra_data,
            perf_index,
            resources=[subtask_resource]))

    def _get_next_subtask(self):
        subtasks = self.subtasks_given.values()
        subtasks = filter(lambda sub: sub['status'] in [
            SubtaskStatus.failure, SubtaskStatus.restarted], subtasks)

        failed_subtask = next(iter(subtasks), None)
        if failed_subtask:
            failed_subtask['status'] = SubtaskStatus.resent
            self.num_failed_subtasks -= 1
            return failed_subtask['subtask_num']

        assert self.last_task < self.total_tasks
        curr = self.last_task + 1
        self.last_task = curr
        return curr - 1

    def query_extra_data_for_test_task(self):
        pass

    def _get_task_computing_definition(self,
                                       sid,
                                       transcoding_params,
                                       perf_idx,
                                       resources):
        ctd = golem_messages.message.ComputeTaskDef()
        ctd['task_id'] = self.header.task_id
        ctd['subtask_id'] = sid
        ctd['extra_data'] = transcoding_params
        ctd['performance'] = perf_idx
        ctd['docker_images'] = [di.to_dict() for di in self.docker_images]
        ctd['deadline'] = self.header.deadline
        ctd['resources'] = resources
        return ctd


class SimpleTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = SimpleManualTask
    DEFAULTS = TaskDefaults

    @classmethod
    def build_full_definition(cls, task_type: CoreTaskTypeInfo,
                              dictionary: Dict[str, Any]):
        task_def = super().build_full_definition(task_type, dictionary)
        task_def.options.name = dictionary.get('options', {}).get('name',
                                                                  'radek')
        return task_def

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo,
                                 dictionary: Dict[str, Any]):
        return super().build_minimal_definition(task_type, dictionary)


class ManualSimpleTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__('MANUAL', SimpleTaskDefinition,
                         SimpleTaskOptions, SimpleTaskBuilder)

