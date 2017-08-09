from copy import deepcopy
import os

from apps.core.task.coretaskstate import (TaskDefinition,
                                          CoreTaskDefaults,
                                          Options)
from apps.dummy.dummyenvironment import DummyTaskEnvironment


class DummyTaskDefaults(CoreTaskDefaults):
    """ Suggested default values for dummy task"""
    def __init__(self):
        super(DummyTaskDefaults, self).__init__()
        self.options = DummyTaskOptions()
        self.options.subtask_data_size = 2048
        self.options.result_size = 256
        self.options.difficulty = 0x00ffffff

        self.shared_data_size = 36
        self.shared_data_files = ["in.data"]
        self.out_file_basename = "out"
        self.default_subtasks = 5
        self.code_dir = "code_dir"

        @property
        def full_task_timeout(self):
            return self.default_subtasks * self.subtask_timeout

        @property
        def subtask_timeout(self):
            return 1200


class DummyTaskDefinition(TaskDefinition):

    #TODO put defaults switch in base class, create CoreTaskDefinition
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.options = DummyTaskOptions()

        # size of data shared by all subtasks in bytes
        self.shared_data_size = 0

        # subtask data
        self.shared_data_files = []
        # subtask code_dir
        self.code_dir = ""
        self.code_files = []

        self.shared_data_files = []
        self.out_file_basename = ""

        if defaults:
            self.set_defaults(defaults)


    def add_to_resources(self):
        super().add_to_resources()
        self.resources += list(self.shared_data_files)

        code_files = []
        for dirpath, dirnames, filenames in os.walk(self.code_dir):
            for name in filenames:
                code_files.append(os.path.join(dirpath, name))
        self.code_files = code_files

        self.resources += code_files

    #TODO move it somewhere to the base class (or not?)
    def set_defaults(self, defaults):
        self.shared_data_size = defaults.shared_data_size
        self.shared_data_files = deepcopy(defaults.shared_data_files)
        self.out_file_basename = defaults.out_file_basename
        self.default_subtasks = defaults.default_subtasks
        self.options = deepcopy(defaults.options)
        self.code_dir = defaults.code_dir

class DummyTaskOptions(Options):
    def __init__(self):
        super(DummyTaskOptions, self).__init__()
        self.environment = DummyTaskEnvironment() #TODO it shoudn't be there
        self.subtask_data_size = 0 # size of subtask-specific data in bytes
        self.result_size = 0 # size of subtask result in bytes

        # The difficulty is a 4 byte int; 0x00000001 is the greatest and 0xffffffff
        # the least difficulty. For example difficulty = 0x003fffff requires
        # 0xffffffff / 0x003fffff = 1024 hash computations on average.
        self.difficulty = 0