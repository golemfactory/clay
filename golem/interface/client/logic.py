import logging

logger = logging.getLogger('golem.interface')


class AppLogic(object):

    def __init__(self):
        self.node_name = None
        self.datadir = None
        self.dir_manager = None
        self.task_types = {}

    def get_builder(self, task_state):
        task_type = task_state.definition.task_type
        return self.task_types[task_type].task_builder_type(self.node_name, task_state.definition,
                                                            self.datadir, self.dir_manager)

    def register_new_task_type(self, task_type):
        if task_type.name not in self.task_types:
            self.task_types[task_type.name] = task_type
        else:
            logger.error("Trying to register a task that was already registered {}".format(task_type))
