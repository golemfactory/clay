import enum
from os import path, remove

from ethereum.utils import denoms

from golem.core.common import timeout_to_string
from golem.core.variables import PICKLED_VERSION
from golem.environments.environment import Environment
from golem.task.taskstate import TaskState


DEFAULT_TIMEOUT = 4 * 3600
DEFAULT_SUBTASK_TIMEOUT = 20 * 60


class RunVerification(enum.Enum):
    """
    Enabled: (default)
        Perform verification and act accordingly.
    Lenient:
        The verification should be performed and then in the event of negative
        verification result, the subtask itself should be marked as failed as
        usual and rescheduled, the provider should also be banned from
        performing any additional subtasks in this task and a failure should
        still be reported to the golem monitor. The provider should get a
        SubtaskResultsAccepted response and be issued a payment just as it
        would had the result been correct.
    Disabled:
        Completely disable verification for the given task and treat all
        results as valid without performing any verification.
    """
    def _generate_next_value_(name, *_):  # pylint:disable=no-self-argument
        return name

    enabled = enum.auto()
    lenient = enum.auto()
    disabled = enum.auto()


class TaskDefinition(object):
    """ Task description used in GUI and in save file format"""

    def __init__(self):
        self.task_id = ""
        self.timeout = DEFAULT_TIMEOUT
        self.subtask_timeout = DEFAULT_SUBTASK_TIMEOUT

        self.resources = set()
        self.estimated_memory = 0

        self.subtasks_count = 0
        self.output_file = ""
        self.task_type = None
        self.name = ""

        self.max_price = 0

        self.run_verification: RunVerification = RunVerification.enabled
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

        if pickled_version < 3:
            if 'run_verification' not in attributes:
                attributes['run_verification'] = RunVerification.enabled

        for key in attributes:
            setattr(self, key, attributes[key])

    def is_valid(self):
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

    def to_dict(self) -> dict:
        task_timeout = timeout_to_string(int(self.timeout))
        subtask_timeout = timeout_to_string(int(self.subtask_timeout))
        output_path = self.build_output_path()

        d = {
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

        if self.run_verification != RunVerification.enabled:
            d['x-run-verification'] = self.run_verification

        return d

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
