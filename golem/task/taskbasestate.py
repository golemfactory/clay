from typing import Type

from golem.environments.environment import Environment


class TaskDefaults(object):
    pass


class TaskDefinition(object):
    pass


class Options(object):
    """ Task specific options """

    def __init__(self):
        self.environment = Environment()
        self.name = ''

    def add_to_resources(self, resources):
        pass

    def remove_from_resources(self, resources):
        pass


class TaskTypeInfo(object):
    """ Information about task that allows to define and build a new task"""

    def __init__(self,
                 name: str,
                 definition: Type[TaskDefinition],
                 defaults: TaskDefaults,
                 options: Type[Options],
                 task_builder_type: 'Type[TaskBuilder]'):
        self.name = name
        self.defaults = defaults
        self.options = options
        self.definition = definition
        self.task_builder_type = task_builder_type
