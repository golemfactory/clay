import abc
import json
import pprint

from tabulate import tabulate

from golem.core.simpleserializer import to_dict
from golem.interface.command import CommandResult
from golem.interface.exceptions import CommandException


class _CommandResultFormatter(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, argument=None, help=None, prettify=True):
        self.argument = argument
        self.help = help
        self.prettify = prettify

    def supports(self, arg_dict):
        return self.argument and arg_dict.get(self.argument)

    def clear_argument(self, arg_dict):
        arg_dict.pop(self.argument, None)

    @abc.abstractmethod
    def format(self, result):
        pass

    @staticmethod
    def _initial_format(result):

        if result is None or result == '':
            return None, CommandResult.NONE

        elif isinstance(result, CommandResult):

            if result.type == CommandResult.TABULAR:
                return result.from_tabular(), CommandResult.TABULAR

            result = result.data

        return result, CommandResult.PLAIN


class CommandFormatter(_CommandResultFormatter):

    def __init__(self, argument=None, help=None, prettify=True):
        super(CommandFormatter, self).__init__(argument, help, prettify)

    def format(self, result):
        result, result_type = self._initial_format(result)

        if result_type != CommandResult.NONE:

            if result_type == CommandResult.TABULAR:
                return tabulate(result[1], headers=result[0], tablefmt="simple")

            elif isinstance(result, basestring):
                return result

            elif isinstance(result, CommandException):
                return repr(result)

            result = to_dict(result)

            if self.prettify:
                return pprint.pformat(result)
            return result


class CommandJSONFormatter(_CommandResultFormatter):

    ARGUMENT = 'json'
    HELP = 'Return results in JSON format'

    def __init__(self, prettify=True):
        super(CommandJSONFormatter, self).__init__(self.ARGUMENT, self.HELP, prettify=prettify)

    def format(self, result):
        result, result_type = self._initial_format(result)

        if result_type != CommandResult.NONE:

            if result_type == CommandResult.TABULAR:
                result = dict(headers=result[0], values=result[1])
            else:
                result = to_dict(result)

            if self.prettify:
                return json.dumps(result, indent=4, sort_keys=True)
            return json.dumps(result)
