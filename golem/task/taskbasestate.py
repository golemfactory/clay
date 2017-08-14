from golem.environments.environment import Environment


class TaskTypeInfo(object):
    pass

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