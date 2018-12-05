from os import path, remove

from ethereum.utils import denoms

from golem.core.common import timeout_to_string
from golem.core.variables import PICKLED_VERSION
from golem.environments.environment import Environment
from golem.task.taskstate import TaskState


class TaskDefaults(object):
    """ Suggested default values for task parameters """

    def __init__(self):
        self.output_format = ""
        self.main_program_file = ""
        self.min_subtasks = 1
        self.max_subtasks = 50
        self.default_subtasks = 20
        self.name = ""

    @property
    def timeout(self):
        return 4 * 3600

    @property
    def subtask_timeout(self):
        return 20 * 60


class TaskDefinition(object):
    """ Task description used in GUI and in save file format"""

    def __init__(self):
        self.task_id = ""
        self.timeout = 0
        self.subtask_timeout = 0

        self.resources = set()
        self.estimated_memory = 0

        self.subtasks_count = 0
        self.optimize_total = False
        self.main_program_file = ""
        self.output_file = ""
        self.task_type = None
        self.name = ""

        self.max_price = 0

        self.verification_options = None
        self.options = Options()
        self.docker_images = None
        self.compute_on = "cpu"

        self.concent_enabled: bool = False

    def __getstate__(self):
        return PICKLED_VERSION, self.__dict__

    def __setstate__(self, state):
        # FIXME Move to sqlite
        if not isinstance(state, tuple):
            pickled_version, attributes = 0, state
        else:
            pickled_version, attributes = state
            if not isinstance(pickled_version, int):
                pickled_version = 1

        if pickled_version < 1:
            # Defaults for attributes that could be missing in pickles
            # from 0.17.1  #3405
            migration_defaults = (
                ('compute_on', 'cpu'),
                ('concent_enabled', False),
            )
            for key, default_value in migration_defaults:
                if key not in attributes:
                    attributes[key] = default_value

        if pickled_version < 2:
            if 'name' not in attributes:
                attributes['name'] = attributes.pop('task_name')
            if 'subtasks_count' not in attributes:
                attributes['subtasks_count'] = attributes.pop('total_subtasks')
            if 'timeout' not in attributes:
                attributes['timeout'] = attributes.pop('full_task_timeout')

        for key in attributes:
            setattr(self, key, attributes[key])

    def is_valid(self):
        if not path.exists(self.main_program_file):
            return False, "Main program file does not exist: {}".format(
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
            return True, "File {} may be overwritten".format(output_file)
        except IOError:
            return False, "Cannot open output file: {}".format(output_file)
        except TypeError as err:
            return False, "Output file {} is not properly set: {}".format(
                output_file, err)

    def add_to_resources(self):
        pass

    def remove_from_resources(self):
        pass

    def make_preset(self):
        """ Create preset that can be shared with different tasks
        :return dict:
        """
        return {
            "options": self.options,
            "subtasks_count": self.subtasks_count,
            "optimize_total": self.optimize_total,
            "verification_options": self.verification_options
        }

    def load_preset(self, preset):
        """ Apply options from preset to this task definition
        :param dict preset: Dictionary with shared options
        """
        self.options = preset["options"]
        self.subtasks_count = preset["subtasks_count"]
        self.optimize_total = preset["optimize_total"]
        self.verification_options = preset["verification_options"]

    def to_dict(self) -> dict:
        task_timeout = timeout_to_string(self.timeout)
        subtask_timeout = timeout_to_string(self.subtask_timeout)
        output_path = self.build_output_path()

        return {
            'id': self.task_id,
            'type': self.task_type,
            'compute_on': self.compute_on,
            'name': self.name,
            'timeout': task_timeout,
            'subtask_timeout': subtask_timeout,
            'subtasks_count': self.subtasks_count,
            'bid': float(self.max_price) / denoms.ether,
            'resources': list(self.resources),
            'options': {
                'output_path': output_path
            },
            'concent_enabled': self.concent_enabled,
        }

    def build_output_path(self) -> str:
        return self.output_file.rsplit(path.sep, 1)[0]


advanceVerificationTypes = ['forAll', 'forFirst', 'random']


class AdvanceVerificationOptions(object):
    def __init__(self):
        self.type = 'forFirst'


class TaskDesc(object):
    def __init__(self,
                 definition_class=TaskDefinition,
                 state_class=TaskState):
        self.definition = definition_class()
        self.task_state = state_class()

    def has_multiple_outputs(self, num_outputs=1):
        """
        Return False if this task has less outputs than <num_outputs>, True
        otherwise
        :param int num_outputs:
        """
        return len(self.task_state.outputs) >= num_outputs


class Options(object):
    """ Task specific options """

    def __init__(self):
        self.environment = Environment()
        self.name = ''
