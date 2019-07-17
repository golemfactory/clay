from typing import Optional, Dict, Any

import golem_messages
from apps.core.task.coretask import CoreTaskBuilder, CoreTaskTypeInfo
from apps.core.task.coretaskstate import TaskDefinition, Options, TaskDefaults
from apps.core.task.manualtask import ManualTask
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task


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
        self.times = None
        self.environment = SimpleTaskEnvironment()


class SimpleTaskDefinition(TaskDefinition):
    def __init__(self):
        super().__init__()
        self.options = SimpleTaskOptions()


class SimpleManualTask(ManualTask):
    def __init__(self, task_definition: SimpleTaskDefinition,
                 owner: 'dt_p2p.Node', **kwargs):
        super().__init__(task_definition, owner)
        self.task_definition = task_definition
        self.chosen_provider = None

    def initialize(self, dir_manager: DirManager):
        super().initialize(dir_manager)

        self.task_definition.subtasks_count = self.task_definition.options.times
        self.total_tasks = self.task_definition.options.times

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        self.num_tasks_received += 1

    def query_extra_data(self, perf_index: float, node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        sid = self.create_subtask_id()
        return Task.ExtraData(ctd=self._get_task_computing_definition(
            sid,
            {'name': self.task_definition.options.name},
            perf_index,
            resources=[]))

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
        task_def.options.times = dictionary.get('options', {}).get('times', 1)
        task_def.options.name = dictionary.get('options', {}).get('name',
                                                                  'radek')
        return task_def

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo,
                                 dictionary: Dict[str, Any]):
        return super().build_minimal_definition(task_type, dictionary)
