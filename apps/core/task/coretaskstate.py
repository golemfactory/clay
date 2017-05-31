from os import path, remove

from golem.environments.environment import Environment
from golem.task.taskstate import TaskState


class Options(object):
    """ Task specific options """
    def __init__(self):
        self.environment = Environment()
        self.name = ''

    def add_to_resources(self, resources):
        pass

    def remove_from_resources(self, resources):
        pass


class CoreTaskDefaults(object):
    """ Suggested default values for task parameters """

    def __init__(self):
        self.output_format = ""
        self.main_program_file = ""
        self.min_subtasks = 1
        self.max_subtasks = 50
        self.default_subtasks = 20
        self.task_name = ""

    @property
    def full_task_timeout(self):
        return 4 * 3600

    @property
    def subtask_timeout(self):
        return 20 * 60


class TaskDefinition(object):
    """ Task description used in GUI and in save file format"""
    def __init__(self):
        self.task_id = ""
        self.full_task_timeout = 0
        self.subtask_timeout = 0

        self.resources = set()
        self.estimated_memory = 0

        self.total_subtasks = 0
        self.optimize_total = False
        self.main_program_file = ""
        self.output_file = ""
        self.task_type = None
        self.task_name = ""

        self.max_price = 0

        self.verification_options = None
        self.options = Options()
        self.docker_images = None

    def is_valid(self):
        if not path.exists(self.main_program_file):
            return False, u"Main program file does not exist: {}".format(
                self.main_program_file)
        return self._check_output_file(self.output_file)

    @staticmethod
    def _check_output_file(output_file):
        try:
            file_exist = path.exists(output_file)
            with open(output_file, 'a'):
                pass
            if not file_exist:
                remove(output_file)
                return True, None
            else:
                return True, u"File {} may be overwritten".format(output_file)
        except IOError:
            return False, u"Cannot open output file: {}".format(output_file)
        except (OSError, TypeError) as err:
            return False, u"Output file {} is not properly set: {}".format(
                output_file, err)

    def add_to_resources(self):
        self.options.add_to_resources(self.resources)

    def remove_from_resources(self):
        self.options.remove_from_resources(self.resources)

    def make_preset(self):
        """ Create preset that can be shared with different tasks
        :return dict:
        """
        return {
            "options": self.options,
            "total_subtasks": self.total_subtasks,
            "optimize_total": self.optimize_total,
            "verification_options": self.verification_options
        }

    def load_preset(self, preset):
        """ Apply options from preset to this task definition
        :param dict preset: Dictionary with shared options
        """
        self.options = preset["options"]
        self.total_subtasks = preset["total_subtasks"]
        self.optimize_total = preset["optimize_total"]
        self.verification_options = preset["verification_options"]


advanceVerificationTypes = ['forAll', 'forFirst', 'random']


class AdvanceVerificationOptions(object):
    def __init__(self):
        self.type = 'forFirst'


class TaskDesc(object):
    def __init__(self, definition_class=TaskDefinition, state_class=TaskState):
        self.definition = definition_class()
        self.task_state = state_class()

    def has_multiple_outputs(self, num_outputs=1):
        """
        Return False if this task has less outputs than <num_outputs>, True
        otherwise
        :param int num_outputs:
        """
        return len(self.task_state.outputs) >= num_outputs
