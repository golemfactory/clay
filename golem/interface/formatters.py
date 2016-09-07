import json

import time


class CommandFormatter(object):

    def __init__(self, argument=None, help=None, use_pprint=True):
        self.argument = argument
        self.help = help

        if use_pprint:
            import pprint
            self.to_repr = pprint.pformat
        else:
            self.to_repr = lambda x: unicode(x)

    def format(self, result, started):
        return self.to_repr(result)

    def supports(self, option_dict):
        return self.argument and self.argument in option_dict and option_dict[self.argument]

    def remove_option(self, option_dict):
        option_dict.pop(self.argument, None)

    @staticmethod
    def _command_time(started):
        return time.time() - started


class CommandJSONFormatter(CommandFormatter):
    ARGUMENT = 'json'
    HELP = 'return results in JSON format'

    def __init__(self):
        super(CommandJSONFormatter, self).__init__(self.ARGUMENT, self.HELP,
                                                   use_pprint=False)

    def format(self, result, started):
        return json.dumps(result, indent=4, sort_keys=True)
