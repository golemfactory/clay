from os import path

from apps.core.task.coretaskstate import (TaskDefinition,
                                          CoreTaskDefaults,
                                          Options)
from apps.dummy.dummyenvironment import DummyTaskEnvironment


class DummyTaskDefaults(CoreTaskDefaults):
    """ Suggested default values for dummy task"""
    def __init__(self):
        super(DummyTaskDefaults, self).__init__()

        self.shared_data_size = 36
        self.subtask_data_size = 2048
        self.result_size = 256
        self.difficulty = 0x00ffffff
        self.shared_data_file = "in.data"
        self.out_file_basename = "out"
        self.default_subtasks = 5
        self.options = DummyTaskOptions()

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

        self.shared_data_size = 0 # size of data shared by all subtasks in bytes
        self.subtask_data_size = 0 # size of subtask-specific data in bytes
        self.result_size = 0 # size of subtask result in bytes

        # The difficulty is a 4 byte int; 0x00000001 is the greatest and 0xffffffff
        # the least difficulty. For example difficulty = 0x003fffff requires
        # 0xffffffff / 0x003fffff = 1024 hash computations on average.
        self.difficulty = 0x0

        self.shared_data_file = ""
        self.out_file_basename = ""

        if defaults:
            self.set_defaults(defaults)


    #TODO move it somewhere to the base class (or not?)
    def set_defaults(self, defaults):
        self.shared_data_size = defaults.shared_data_size
        self.subtask_data_size = defaults.subtask_data_size
        self.result_size = defaults.result_size
        self.difficulty = defaults.difficulty
        self.shared_data_file = defaults.shared_data_file
        self.out_file_basename = defaults.out_file_basename
        self.default_subtasks = defaults.default_subtasks
        self.options = defaults.options


class DummyTaskOptions(Options):
    def __init__(self):
        super(DummyTaskOptions, self).__init__()
        self.environment = DummyTaskEnvironment() #TODO it shoudn't be there
        self.hash_type = "sha256" # TODO I will use it later