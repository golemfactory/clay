import decimal
import logging
import os
import random
import shutil
import stat

from copy import copy
from typing import Type, Optional, Dict, Any
from ethereum.utils import denoms

import enforce
from golem_messages.message import ComputeTaskDef

from apps.core.task.coretask import (CoreTask,
                                     CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.shell.shellenvironment import ShellTaskEnvironment
from apps.shell.task.shelltaskstate import ShellTaskDefaults, ShellTaskOptions
from apps.shell.task.shelltaskstate import ShellTaskDefinition
from apps.shell.task.verifier import ShellTaskVerifier
from golem.core.common import HandleKeyError, timeout_to_deadline, to_unicode, \
    string_to_timeout
from golem.task.taskbase import Task
from golem.task.taskclient import TaskClient
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.shell")


def copytree(src, dst, symlinks = False, ignore = None):
    if not os.path.exists(dst):
        os.makedirs(dst)
        shutil.copystat(src, dst)
    lst = os.listdir(src)
    if ignore:
        excl = ignore(src, lst)
        lst = [x for x in lst if x not in excl]
    for item in lst:
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if symlinks and os.path.islink(s):
            if os.path.lexists(d):
                os.remove(d)
            os.symlink(os.readlink(s), d)
            try:
                st = os.lstat(s)
                mode = stat.S_IMODE(st.st_mode)
                os.lchmod(d, mode)
            except:
                pass # lchmod not available
        elif os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


class ShellTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "Shell",
            ShellTaskDefinition,
            ShellTaskDefaults(),
            ShellTaskOptions,
            ShellTaskBuilder
        )


@enforce.runtime_validation(group="shell")
class ShellTask(CoreTask):
    ENVIRONMENT_CLASS = ShellTaskEnvironment
    VERIFIER_CLASS = ShellTaskVerifier

    def __init__(self,
                 total_tasks: int,
                 task_definition: ShellTaskDefinition,
                 root_path=None,
                 owner=None):
        super().__init__(
            owner=owner,
            task_definition=task_definition,
            root_path=root_path,
            total_tasks=total_tasks
        )

    def short_extra_data_repr(self, extra_data):
        return "Shelltask extra_data: {}".format(extra_data)

    def _extra_data(self, perf_index=0.0) -> ComputeTaskDef:
        subtask_id = self.create_subtask_id()

        extra_data = dict()

        if hasattr(self.task_definition, 'environment'):
            extra_data['environment'] = self.task_definition.environment

        return self._new_compute_task_def(subtask_id,
                                          extra_data,
                                          perf_index=perf_index)

    def query_extra_data(self,
                         perf_index: float,
                         num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        logger.debug("Query extra data on shelltask")

        ctd = self._extra_data(perf_index)
        sid = ctd['subtask_id']

        #FIXME Is this necessary?
        self.subtasks_given[sid] = copy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["shared_data_files"] = \
            self.task_definition.shared_data_files
        self.subtasks_given[sid]["subtask_id"] = sid

        return self.ExtraData(ctd=ctd)

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        node_id = self.subtasks_given[subtask_id]['node_id']
        TaskClient.assert_exists(node_id, self.counting_nodes).accept()
        self.num_tasks_received += 1

        output_dir = os.path.join(self.tmp_dir, subtask_id)
        # Copying GOLEM_OUTPUT to task_definition.root_dir
        content = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if not f.endswith(".log")]
        for src in content:
            t = os.path.join(self.task_definition.root_dir, os.path.basename(src))
            if os.path.isdir(src):
                copytree(src, t)
            elif os.path.isfile(src):
                shutil.copy2(src, t)
            else:
                logger.error("Ignoring output: {}".format(t))

    def interpret_task_results(self, subtask_id, task_results, result_type: int,
                               sort=True):
        self.stdout[subtask_id] = ""
        self.stderr[subtask_id] = ""
        self.results[subtask_id] = task_results
        if sort:
            self.results[subtask_id].sort()

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        exd = self._extra_data()
        return exd


class ShellTaskBuilder(CoreTaskBuilder):
    TASK_CLASS = ShellTask

    def build(self):
        # pylint:disable=abstract-class-instantiated
        task = self.TASK_CLASS(**self.get_task_kwargs())

        task.initialize(self.dir_manager)
        return task

    @classmethod
    def build_minimal_definition(cls, task_type: ShellTaskTypeInfo, dictionary):
        definition = task_type.definition()
        definition.task_type = task_type.name

        definition.root_dir = dictionary['root_dir']
        assert os.path.exists(definition.root_dir)

        definition.resources = set(dictionary['resources'])
        definition.resources = [r.replace("${ROOT_DIR}", definition.root_dir) \
                                for r in definition.resources]

        if 'environment' in dictionary:
            definition.environment = dictionary['environment']
        for r in definition.resources:
            assert os.path.exists(r)

        definition.total_subtasks = 1
        return definition

    @classmethod
    def build_definition(cls,  # type: ignore
                         task_type: ShellTaskTypeInfo,
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
                              task_type: ShellTaskTypeInfo,
                              dictionary: Dict[str, Any]):
        definition = cls.build_minimal_definition(task_type, dictionary)
        definition.task_name = dictionary['name']
        definition.max_price = \
            int(decimal.Decimal(dictionary['bid']) * denoms.ether)

        definition.full_task_timeout = string_to_timeout(
            dictionary['timeout'])
        definition.subtask_timeout = definition.full_task_timeout
        definition.estimated_memory = dictionary.get('estimated_memory', 0)

        return definition

    @staticmethod
    def build_dictionary(definition: ShellTaskDefinition) -> dict:
        return definition.to_dict()

    @classmethod
    def get_output_path(cls, dictionary, definition):
        return dictionary['root_dir']

# comment that line to enable type checking
enforce.config({'groups': {'set': {'shell': False}}})