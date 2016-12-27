from os import path, remove

from golem.task.taskstate import TaskState


class GNRTaskDefinition(object):

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

        self.max_price = 0

        self.verification_options = None
        self.options = GNROptions
        self.docker_images = None

    def is_valid(self):
        if not path.exists(self.main_program_file):
            return False, u"Main program file does not exist: {}".format(self.main_program_file)
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
            return False, u"Output file {} is not properly set: {}".format(output_file, err)


advanceVerificationTypes = ['forAll', 'forFirst', 'random']


class AdvanceVerificationOptions(object):
    def __init__(self):
        self.type = 'forFirst'


class TaskDesc(object):
    def __init__(self, definition_class=GNRTaskDefinition, state_class=TaskState):
        self.definition = definition_class()
        self.task_state = state_class()

    def has_multiple_outputs(self, num_outputs=1):
        return len(self.task_state.outputs) > num_outputs


class GNROptions(object):
    def __init__(self):
        self.name = ''
