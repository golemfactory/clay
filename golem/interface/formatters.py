import json

FORMATTER_REPR_PROPERTY = '__formatter_repr__'


class CommandFormatter(object):

    def __init__(self, argument=None, help=None, use_pprint=True):
        self.argument = argument
        self.help = help

        if use_pprint:
            import pprint
            self.to_repr = lambda x: unicode(pprint.pformat(to_dict(x)))
        else:
            self.to_repr = lambda x: unicode(to_dict(x))

    def format(self, result, started):
        if result:
            return self.to_repr(result)

    def supports(self, option_dict):
        return self.argument and self.argument in option_dict and option_dict[self.argument]

    def remove_option(self, option_dict):
        option_dict.pop(self.argument, None)


class CommandJSONFormatter(CommandFormatter):

    ARGUMENT = 'json'
    HELP = 'return results in JSON format'

    def __init__(self):
        super(CommandJSONFormatter, self).__init__(self.ARGUMENT, self.HELP,
                                                   use_pprint=False)

    def format(self, result, started):
        return json.dumps(to_dict(result), indent=4, sort_keys=True)


def to_dict(obj, cls=None):

    if isinstance(obj, dict):
        return {k: to_dict(v, cls) for k, v in obj.iteritems()}

    elif hasattr(obj, "_ast"):
        return to_dict(obj._ast())

    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [to_dict(v, cls) for v in obj]

    elif hasattr(obj, "__dict__"):

        data = dict()
        for k, v in obj.__dict__.iteritems():
            if not callable(v) and not k.startswith('_'):
                data[k] = to_dict(v, cls)

        if cls is not None and hasattr(obj, "__class__"):
            data[cls] = obj.__class__.__name__

        return data

    return obj
