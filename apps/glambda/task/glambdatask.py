from copy import copy
import decimal
import json
import logging
import os
import time
import shutil
from typing import List, Optional, Dict, Any

import mock
from ethereum.utils import denoms

import golem_messages
from golem_messages import idgenerator

from apps.core.task.coretask import CoreTask, CoreTaskBuilder, CoreTaskTypeInfo
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
                                TaskTypeInfo, \
                                AcceptClientVerdict
from golem.task.taskclient import TaskClient
from golem.task.taskstate import SubtaskStatus
from golem.verificator.verifier import SubtaskVerificationState

logger = logging.getLogger(__name__)


def apply(obj, *initial_data, **kwargs):
    for dictionary in initial_data:
        for key in dictionary:
            setattr(obj, key, dictionary[key])
    for key in kwargs:
        setattr(obj, key, kwargs[key])


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


class GLambdaTaskTypeInfo(TaskTypeInfo):
    def __init__(self):
        super().__init__(
            "GLambda",
            TaskDefinition,
            Options,
            GLambdaTaskBuilder
        )


class GLambdaTask(CoreTask):

    ENVIRONMENT_CLASS = GLambdaTaskEnvironment
    MAX_PENDING_CLIENT_RESULTS=1

    def __init__(self,
                 task_definition: TaskDefinition,
                 owner: dt_p2p.Node,
                 max_pending_client_results=MAX_PENDING_CLIENT_RESULTS,
                 resource_size=None,
                 root_path=None,
                 total_tasks=1,
                 method=None,
                 args=None,
                 dir_manager=None):
        super(GLambdaTask, self).__init__(task_definition, owner, max_pending_client_results,
            resource_size, root_path, total_tasks)
        self.method = method
        self.args = args
        self.results = None
        self.dir_manager = dir_manager
        self.output_path = dir_manager.get_task_output_dir(task_definition.task_id)

    def query_extra_data(self, perf_index: float,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None):
        start_task = self._get_next_task()
        subtask_id = self.create_subtask_id()

        subtask_data = {
                'method': self.method,
                'args': self.args,
                'script_filepath': '/golem/scripts/job.py'
        }

        subtask_builder = ExtraDataBuilder(self.header, subtask_id, subtask_data,
                                           self.short_extra_data_repr(subtask_data),
                                           perf_index, self.docker_images)

        logger.debug(
            'Created new subtask for task. '
            'task_id=%s, subtask_id=%s, node_id=%s',
            self.header.task_id,
            subtask_id,
            (node_id or '')
        )

        self.subtasks_given[subtask_id] = {
            'header': self.header,
            'subtask_id': subtask_id,
            'subtask_data': subtask_data,
            'performance': perf_index,
            'docker_images': self.docker_images
        }
        self.subtasks_given[subtask_id]['subtask_id'] = subtask_id
        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.starting
        self.subtasks_given[subtask_id]['start_task'] = start_task
        self.subtasks_given[subtask_id]['node_id'] = node_id
        self.subtasks_given[subtask_id]['subtask_timeout'] = \
            self.header.subtask_timeout
        self.subtasks_given[subtask_id]['tmp_dir'] = self.tmp_dir

        subtask = subtask_builder.get_result()

        return subtask

    def _get_next_task(self):
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

    def query_extra_data_for_test_task(self):
        pass

    def short_extra_data_repr(self, extra_data: Task.ExtraData) -> str:
        return 'glambda task'

    def computation_finished(self, subtask_id, task_result,
                             verification_finished=None):
        if not self.should_accept(subtask_id):
            logger.info("Not accepting results for %s", subtask_id)
            return

        self.subtasks_given[subtask_id]['status'] = SubtaskStatus.verifying
        self.num_tasks_received += 1

        if True:
            verdict = SubtaskVerificationState.VERIFIED

        try:
            if verdict == SubtaskVerificationState.VERIFIED:
                self.accept_results(subtask_id, None)
            # TODO Add support for different verification states. issue #2422
            else:
                self.computation_failed(subtask_id)
        except Exception as exc:
            logger.warning("Failed during accepting results %s", exc)

        verification_finished()
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

        except BaseException as e:
            logger.exception('')

    def get_results(self, subtask_id):
        return self.results

    def get_output_names(self) -> List:
        return [self.output_path]


class GLambdaTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = GLambdaTask

    def __init__(self,
                 owner: dt_p2p.Node,
                 task_definition: TaskDefinition,
                 dir_manager: DirManager) -> None:
        super(CoreTaskBuilder, self).__init__()
        self.task_definition = task_definition
        self.root_path = dir_manager.root_path
        self.dir_manager = dir_manager
        self.owner = owner
        self.environment = None

    def build(self):
        # pylint:disable=abstract-class-instantiated
        task = self.TASK_CLASS(**self.get_task_kwargs())

        task.initialize(self.dir_manager)
        return task

    def get_task_kwargs(self, **kwargs):
        kwargs['total_tasks'] = 1
        kwargs["task_definition"] = self.task_definition
        kwargs["owner"] = self.owner
        kwargs["root_path"] = self.root_path
        kwargs["method"] = self.task_definition.extra_data['method']
        kwargs["args"] = self.task_definition.extra_data['args']
        kwargs["dir_manager"] = self.dir_manager
        return kwargs

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo, dictionary):
        definition = task_type.definition()
        definition.task_type = task_type.name
        definition.compute_on = dictionary.get('compute_on', 'cpu')
        if 'resources' in dictionary:
            definition.resources = set(dictionary['resources'])
        definition.subtasks_count = int(dictionary['subtasks_count'])
        definition.extra_data = dictionary['extra_data']
        return definition

    @classmethod
    def build_definition(cls,  # type: ignore
                         task_type: CoreTaskTypeInfo,
                         dictionary: Dict[str, Any],
                         minimal=False):
        # dictionary comes from the GUI
        if not minimal:
            definition = cls.build_full_definition(task_type, dictionary)
        else:
            definition = cls.build_minimal_definition(task_type, dictionary)

        definition.add_to_resources()
        return definition

    @classmethod
    def build_full_definition(cls,
                              task_type: CoreTaskTypeInfo,
                              dictionary: Dict[str, Any]):
        definition = cls.build_minimal_definition(task_type, dictionary)
        definition.name = dictionary['name']
        definition.max_price = \
            int(decimal.Decimal(dictionary['bid']) * denoms.ether)

        definition.timeout = string_to_timeout(dictionary['timeout'])
        definition.subtask_timeout = string_to_timeout(
            dictionary['subtask_timeout'],
        )
        definition.estimated_memory = dictionary.get('estimated_memory', 0)

        return definition

    # TODO: Backward compatibility only. The rendering tasks should
    # move to overriding their own TaskDefinitions instead of
    # overriding `build_dictionary. Issue #2424`
    @staticmethod
    def build_dictionary(definition: TaskDefinition) -> dict:
        return definition.to_dict()


class GLambdaBenchmarkTaskBuilder(GLambdaTaskBuilder):
    def build(self) -> 'Task':
        mock_obj = mock.MagicMock()
        return mock_obj
