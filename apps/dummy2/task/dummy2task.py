import logging
import os
from copy import copy
from typing import Optional
import string
import itertools
import math
import random
import hashlib
import functools

import enforce
from golem_messages.message import ComputeTaskDef

from apps.core.task.coretask import (CoreTask, CoreTaskBuilder,
                                     CoreTaskTypeInfo)
from apps.dummy2.dummy2environment import Dummy2TaskEnvironment
from apps.dummy2.task.dummy2taskstate import Dummy2TaskDefaults
from apps.dummy2.task.dummy2taskstate import Dummy2TaskOptions
from apps.dummy2.task.dummy2taskstate import Dummy2TaskDefinition
from apps.dummy2.task.verifier import Dummy2TaskVerifier
from golem.core.fileshelper import has_ext
from golem.core.common import get_golem_path
from golem.task.taskbase import Task
from golem.task.taskclient import TaskClient
from golem.task.taskstate import SubtaskStatus

logger = logging.getLogger("apps.dummy2")
APP_DIR = os.path.join(get_golem_path(), 'apps', 'dummy2')
MERGE_TIMEOUT = 7200


def get_artificial_passwds(permutations_generator, steps):

    permutations_count = sum(1 for _ in permutations_generator())
    step = int(math.ceil(permutations_count / steps))

    indexes = set()

    # Choosing random indexes from problem space. That should yield
    # an average of 10 artificial passwords per subtask
    for i in range(10 * steps):
        indexes.add(random.randint(0, permutations_count - 1))

    permutations = permutations_generator()

    retdict = {}
    for i, permutation in enumerate(permutations):
        if i in indexes:
            passwd = ''.join(permutation)
            sha = hashlib.sha256()
            sha.update(passwd.encode())
            retdict[passwd] = (int(i / step), sha.hexdigest())

    return retdict


class Dummy2TaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__("Dummy2", Dummy2TaskDefinition, Dummy2TaskDefaults(),
                         Dummy2TaskOptions, Dummy2TaskBuilder)


# pylint: disable=too-many-instance-attributes
@enforce.runtime_validation(group="dummy2")
class Dummy2Task(CoreTask):
    """
    For a given password length and hash (sha256) this task will try to guess
    the corresponding password. It will do so by comparing each charset's
    permutation hash with the original one. The task will be split into
    subtasks, each working on it's assigned permutation's range (linear).
    To ensure subtask computation authenticity each subtask will be given not
    one but multiple hashes. These hashes will correspond to passwords randomly
    picked from problem space. This allows to inject real hash into the subtask
    without the provider knowing which one it really is, stopping him from
    returning early (e.g. when finding all the artificial hashes). This way
    forces provider to return full set of passwords assigned to his subtask.

    Attributes:
        artificial_passwds
            helper Dict{password: Tuple(bucket_index, sha256_hexdigest)},
            bucket_index helps to find all artificial passwords corresponding
            to the given subtask
        hashes_merged
            shuffled list of hashes containing both artificial hashes and the
            original problem hash
        password_length
            original problem password length
        password_hash
            original problem password hash
        real_password
            original problem password (to be determined, set by verifier class)

    Input data file:
    password_length sha256_hex_digest

    Corner cases:
    Not finding a password results in a silent finish. That could happen if
    password uses different character set.

    Corresponding task JSON:
        {
            "resources":[
                "/home/user/in.txt"
            ],
            "taskName":"dummy2.dummy2",
            "name":"dummy2",
            "type":"Dummy2",
            "timeout":"0:20:00",
            "subtasks": 1,
            "subtask_timeout":"0:05:00",
            "bid":1,
            "options":{
                "output_path":".",
                "output_file":"./dummy_password.txt"
            },
            "estimated_memory": 2147483648
        }

    TODO: Benchmark
    """

    ENVIRONMENT_CLASS = Dummy2TaskEnvironment
    VERIFIER_CLASS = Dummy2TaskVerifier

    RESULT_EXT = ".result"
    TESTING_CHAR = "a"

    def __init__(self,
                 total_tasks: int,
                 task_definition: Dummy2TaskDefinition,
                 root_path=None,
                 owner=None) -> None:
        super().__init__(
            owner=owner,
            task_definition=task_definition,
            root_path=root_path,
            total_tasks=total_tasks)
        self.collected_file_names = {}  # type: ignore
        self.merge_timeout = MERGE_TIMEOUT
        shared_data = open(
            self.task_definition.shared_data_files[0],  # type: ignore
            'r').read()
        passwd_length, passwd_hash = shared_data.split()
        self.password_length = int(passwd_length)
        self.password_hash = passwd_hash
        self.real_password = None
        self.charset = string.ascii_lowercase + \
            string.ascii_uppercase + string.digits + string.punctuation
        self.artificial_passwds = get_artificial_passwds(
            functools.partial(self.get_charset_permutations,
                              self.password_length), total_tasks)
        self.hashes_merged = \
            [item[1] for item in self.artificial_passwds.values()] +\
            [passwd_hash]
        random.shuffle(self.hashes_merged)

        if task_definition.docker_images is None:
            task_definition.docker_images = self.environment.docker_images

    def finished_computation(self):
        return self.real_password or self.num_tasks_received == self.total_tasks

    def short_extra_data_repr(self, extra_data):
        return "Dummy2task extra_data: {}".format(extra_data)

    def _extra_data(self, perf_index=0.0, start_task=1) -> ComputeTaskDef:
        subtask_id = self.create_subtask_id()

        subtask_string = "{}\n{}\n{}\n{}\n".format(
            self.password_length, start_task - 1, self.total_tasks,
            len(self.hashes_merged))
        for h in self.hashes_merged:
            subtask_string += "{}\n".format(h)

        extra_data = {
            "data_files": [],
            "subtask_data": subtask_string,
            "difficulty": self.task_definition.options.difficulty,
            "result_size": self.task_definition.result_size,  # type: ignore
            "result_file": self.__get_result_file_name(subtask_id),
            "subtask_data_size": 0,
            "start_task": start_task,
        }

        return self._new_compute_task_def(
            subtask_id, extra_data, perf_index=perf_index)

    def _get_next_task(self):
        if self.last_task != self.total_tasks:
            self.last_task += 1
            start_task = self.last_task
            return start_task
        else:
            for sub in self.subtasks_given.values():
                if sub['status'] in [
                        SubtaskStatus.failure, SubtaskStatus.restarted
                ]:
                    sub['status'] = SubtaskStatus.resent
                    start_task = sub['start_task']
                    self.num_failed_subtasks -= 1
                    return start_task
        return None

    def get_charset_permutations(self, size):
        return itertools.product(self.charset, repeat=size)

    def get_passwds_for_bucket(self, bucket_num=0):
        passwds = []
        for k, v in self.artificial_passwds.items():
            if v[0] == bucket_num:
                passwds.append(k)
        return passwds

    def query_extra_data(self,
                         perf_index: float,
                         num_cores: int = 1,
                         node_id: Optional[str] = None,
                         node_name: Optional[str] = None) -> Task.ExtraData:
        logger.debug("Query extra data on dummy2task")

        start_task = self._get_next_task()
        ctd = self._extra_data(perf_index, start_task)
        sid = ctd['subtask_id']

        self.subtasks_given[sid] = copy(ctd['extra_data'])
        self.subtasks_given[sid]["status"] = SubtaskStatus.starting
        self.subtasks_given[sid]["perf"] = perf_index
        self.subtasks_given[sid]["parent_task"] = self
        self.subtasks_given[sid]["node_id"] = node_id
        self.subtasks_given[sid]["result_extension"] = self.RESULT_EXT
        self.subtasks_given[sid]["shared_data_files"] = \
            self.task_definition.shared_data_files  # type: ignore
        self.subtasks_given[sid]["subtask_id"] = sid

        return self.ExtraData(ctd=ctd)

    def accept_results(self, subtask_id, result_files):
        super().accept_results(subtask_id, result_files)
        node_id = self.subtasks_given[subtask_id]['node_id']
        TaskClient.assert_exists(node_id, self.counting_nodes).accept()
        num_start = self.subtasks_given[subtask_id]['start_task']
        for f in result_files:
            if has_ext(f, self.RESULT_EXT):
                self.collected_file_names[num_start] = f

        self.num_tasks_received += 1

        # TODO For now we do nothing if password has not been found
        # One possible scenario would be to write an error message to output
        # file
        if self.finished_computation() and self.real_password:
            with open(self.task_definition.output_file, 'w') as f:
                f.write(self.real_password)

    def __get_result_file_name(self, subtask_id: str) -> str:
        return "{}{}{}"\
            .format(self.task_definition.out_file_basename,  # type: ignore
                    subtask_id[0:6], self.RESULT_EXT)

    def query_extra_data_for_test_task(self) -> ComputeTaskDef:
        exd = self._extra_data()
        return exd


class Dummy2TaskBuilder(CoreTaskBuilder):
    TASK_CLASS = Dummy2Task  # type: ignore

    @classmethod
    def build_dictionary(cls, definition: Dummy2TaskDefinition):  # type: ignore
        dictionary = super().build_dictionary(definition)
        opts = dictionary['options']

        opts["subtask_data_size"] = int(definition.options.subtask_data_size)
        opts["difficulty"] = int(definition.options.difficulty)

        return dictionary

    @classmethod
    def build_full_definition(cls,  # type: ignore
                              task_type: Dummy2TaskTypeInfo,
                              dictionary):
        # dictionary comes from GUI
        opts = dictionary["options"]

        definition = super().build_full_definition(task_type, dictionary)

        sbs = opts.get("subtask_data_size",
                       definition.options.subtask_data_size)
        difficulty = opts.get("difficulty", definition.options.difficulty)

        sbs = int(sbs)
        # difficulty comes in hex string from GUI
        if isinstance(difficulty, str):
            difficulty = int(difficulty, 16)

        if sbs <= 0:
            raise Exception("Subtask data size should be greater than 0")
        if difficulty < 0:
            raise Exception("Difficulty should be greater than 0")

        definition.options.difficulty = difficulty
        definition.options.subtask_data_size = sbs

        return definition


class Dummy2TaskMod(Dummy2Task):
    # pylint: disable=unused-argument
    # pylint: disable=arguments-differ
    def query_extra_data(self, *args, **kwargs):
        ctd = self.query_extra_data_for_test_task()
        return self.ExtraData(ctd=ctd)


class Dummy2TaskBuilderMod(Dummy2TaskBuilder):
    TASK_CLASS = Dummy2TaskMod


# comment that line to enable type checking
enforce.config({'groups': {'set': {'dummy2': False}}})
