import decimal
import json
import logging
import os
import time
import shutil
from typing import List, Optional

import mock
from ethereum.utils import denoms

import golem_messages
from golem_messages import idgenerator

from apps.core.task.coretaskstate import TaskDefinition, Options
from apps.glambda.glambdaenvironment import GLambdaTaskEnvironment
from golem_messages.datastructures import p2p as dt_p2p
from golem_messages.datastructures import tasks as dt_tasks
from golem import constants as gconst
from golem.resource.dirmanager import DirManager
from golem.core.common import timeout_to_deadline, string_to_timeout,\
                              to_unicode
from golem.docker.environment import DockerEnvironment
from golem.task.taskbase import Task, TaskState, TaskBuilder, \
                                TaskTypeInfo, TaskDefaults,  \
                                AcceptClientVerdict
from golem.task.taskclient import TaskClient

logger = logging.getLogger(__name__)


def apply(obj, *initial_data, **kwargs):
    for dictionary in initial_data:
        for key in dictionary:
            setattr(obj, key, dictionary[key])
    for key in kwargs:
        setattr(obj, key, kwargs[key])


class BasicTaskBuilder(TaskBuilder):
    def __init__(self,
                 owner: dt_p2p.Node,
                 task_definition: TaskDefinition,
                 dir_manager: DirManager) -> None:
        super().__init__()
        self.task_definition = task_definition
        self.root_path = dir_manager.root_path
        self.dir_manager = dir_manager
        self.owner = owner

    @classmethod
    def build_definition(cls, task_type: TaskTypeInfo, dictionary,
                         minimal=False):
        td = task_type.definition()
        apply(td, dictionary)
        td.task_type = task_type.name
        td.timeout = string_to_timeout(dictionary['timeout'])
        td.subtask_timeout = string_to_timeout(dictionary['subtask_timeout'])
        td.max_price = \
            int(decimal.Decimal(dictionary['bid']) * denoms.ether)
        return td


class ExtraDataBuilder(object):
    def __init__(self, header, subtask_id, subtask_data,
                    short_desc, performance, docker_images=None):
        self.header = header
        self.subtask_id = subtask_id
        self.subtask_data = subtask_data
        self.short_desc = short_desc
        self.performance = performance
        self.docker_images = docker_images

    def get_result(self):
        ctd = golem_messages.message.ComputeTaskDef()
        ctd['task_id'] = self.header.task_id
        ctd['subtask_id'] = self.subtask_id
        ctd['extra_data'] = self.subtask_data
        ctd['short_description'] = self.short_desc
        ctd['performance'] = self.performance
        if self.docker_images:
            ctd['docker_images'] = [di.to_dict() for di in self.docker_images]
        ctd['deadline'] = min(timeout_to_deadline(self.header.subtask_timeout),
                            self.header.deadline)
        return Task.ExtraData(ctd=ctd)


class DockerTask(Task):
    ENVIRONMENT_CLASS=DockerEnvironment

    def __init__(self,
                 owner: dt_p2p.Node,
                 task_definition: TaskDefinition,
                 dir_manager: DirManager) -> None:
        self.environment = self.ENVIRONMENT_CLASS()

        if task_definition.docker_images:
            self.docker_images = task_definition.docker_images
        elif isinstance(self.environment, DockerEnvironment):
            self.docker_images = self.environment.docker_images
        else:
            self.docker_images = None

        th = dt_tasks.TaskHeader(
            min_version=str(gconst.GOLEM_MIN_VERSION),
            task_id=task_definition.task_id,
            environment=self.environment.get_id(),
            task_owner=owner,
            deadline=timeout_to_deadline(task_definition.timeout),
            subtask_timeout=task_definition.subtask_timeout,
            subtasks_count=task_definition.subtasks_count,
            resource_size=1024,
            estimated_memory=task_definition.estimated_memory,
            max_price=task_definition.max_price,
            concent_enabled=task_definition.concent_enabled,
            timestamp=int(time.time())
        )
        super().__init__(th, task_definition)


class GLambdaTaskTypeInfo(TaskTypeInfo):
    def __init__(self):
        super().__init__(
            "GLambda",
            TaskDefinition,
            TaskDefaults(),
            Options,
            GLambdaTaskBuilder
        )


class GLambdaTaskBuilder(BasicTaskBuilder):
    def build(self) -> 'Task':
        return GLambdaTask(self.owner,
                             self.task_definition,
                             self.dir_manager,
                             self.task_definition.extra_data['method'],
                             self.task_definition.extra_data['args']
                        )


class GLambdaBenchmarkTaskBuilder(GLambdaTaskBuilder):
    def build(self) -> 'Task':
        mock_obj = mock.MagicMock()
        return mock_obj


class GLambdaTask(DockerTask):

    class BasicAcceptStrategy(object):
        def accept(self, client):
            return True

    ENVIRONMENT_CLASS = GLambdaTaskEnvironment

    def __init__(self,
                 owner: dt_p2p.Node,
                 task_definition: TaskDefinition,
                 dir_manager: DirManager,
                 method,
                 args):
        super().__init__(owner, task_definition, dir_manager)
        self.dir_manager = dir_manager
        self.method = method
        self.args = args
        self.finished = False
        self.output_path = dir_manager.get_task_output_dir(task_definition.task_id)
        self.results = None

        # State tracking structure helps to determine when
        # the task has been finished
        self.dispatched_subtasks = {}
        self.progress = 0.0

    def initialize(self, dir_manager):
        pass

    def create_subtask_id(self) -> str:
        return idgenerator.generate_new_id_from_id(self.header.task_id)

    def query_extra_data(self, perf_index: float, num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> 'ExtraData':
        subtask_id = self.create_subtask_id()

        subtask_data = {
                'method': self.method,
                'args': self.args,
                'script_filepath': '/golem/scripts/job.py'
        }

        subtask_builder = ExtraDataBuilder(self.header, subtask_id, subtask_data,
                                           self.short_extra_data_repr(subtask_data),
                                           perf_index, self.docker_images)

        subtask = subtask_builder.get_result()
        self.dispatched_subtasks[subtask_id] = subtask

        return subtask

    def query_extra_data_for_test_task(self) -> golem_messages.message.ComputeTaskDef:  # noqa pylint:disable=line-too-long
        pass

    def short_extra_data_repr(self, extra_data: Task.ExtraData) -> str:
        return 'glambda task'

    def needs_computation(self) -> bool:
        return not self.dispatched_subtasks

    def finished_computation(self) -> bool:
        return self.finished and not self.dispatched_subtasks

    def computation_finished(self, subtask_id, task_result,
                             verification_finished=None):
        try:
            outdir_content = os.listdir(
                os.path.join(
                    self.dir_manager.get_task_temporary_dir(self.task_definition.task_id),
                    subtask_id
                )
            )

            for obj in outdir_content:
                shutil.move(
                    os.path.join(
                        self.dir_manager.get_task_temporary_dir(self.task_definition.task_id),
                        subtask_id,
                        obj),
                    self.dir_manager.get_task_output_dir(self.task_definition.task_id,
                                                                 os.path.basename(obj))
                )

            del self.dispatched_subtasks[subtask_id]

            if True:
                # Do some verification with the result data here
                self.progress = 1.0
                self.finished = True
        except BaseException as e:
            logger.exception('')
        # Verification is always positive in this case
        try:
            if verification_finished:
                verification_finished()
        except Exception as e:
            logger.exception('')

    def computation_failed(self, subtask_id):
        self.finished = True
        self.progress = 1.0
        del self.dispatched_subtasks[subtask_id]

    def verify_subtask(self, subtask_id):
        return True

    def verify_task(self):
        return self.finished_computation()

    def get_total_tasks(self) -> int:
        return 1

    def get_active_tasks(self) -> int:
        return 0 if self.finished else 1 

    def get_tasks_left(self) -> int:
        return 0 if self.finished else 1

    def restart(self):
        raise NotImplementedError()

    def restart_subtask(self, subtask_id):
        raise NotImplementedError()

    def abort(self):
        raise NotImplementedError()

    def get_progress(self) -> float:
        return 1.0 if self.finished_computation() else 0.0

    def get_resources(self) -> list:
        return self.task_definition.resources

    def update_task_state(self, task_state: TaskState):
        return  # Implement in derived class

    def get_trust_mod(self, subtask_id) -> int:
        return 1.0

    def add_resources(self, resources: set):
        raise NotImplementedError()

    def copy_subtask_results(
            self, subtask_id: int, old_subtask_info: dict, results: List[str]) \
            -> None:
        raise NotImplementedError()

    def should_accept_client(self, node_id):
        if self.needs_computation():
            return AcceptClientVerdict.ACCEPTED
        elif self.finished_computation():
            return AcceptClientVerdict.ACCEPTED
        else:
            return AcceptClientVerdict.SHOULD_WAIT

    def get_stdout(self, subtask_id) -> str:
        return ""

    def get_stderr(self, subtask_id) -> str:
        return ""

    def get_results(self, subtask_id) -> List:
        return self.results

    def result_incoming(self, subtask_id):
        pass

    def get_output_names(self) -> List:
        return [self.output_path]

    def get_output_states(self) -> List:
        return []

    def to_dictionary(self):
        return {
            'id': to_unicode(self.header.task_id),
            'name': to_unicode(self.task_definition.name),
            'type': to_unicode(self.task_definition.task_type),
            'subtasks_count': self.get_total_tasks(),
            'progress': self.get_progress()
        }

    def accept_client(self, node_id):
        verdict = self.should_accept_client(node_id)

        if verdict == AcceptClientVerdict.ACCEPTED:
            client = TaskClient(node_id)
            client.start()
        return verdict
