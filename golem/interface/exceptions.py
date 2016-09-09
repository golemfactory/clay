import time
import traceback


class CommandException(Exception):
    pass


class InterruptException(CommandException):
    pass


class ParsingException(CommandException):

    def __init__(self, message, parser=None):
        super(ParsingException, self).__init__(message)
        self.parser = parser

    def __repr__(self):
        return u"{}".format(self.message)


class ExecutionException(CommandException):

    def __init__(self, message, command, started, include_stack=False):
        self.message = message
        self.command = command
        self.started = started
        self.include_stack = include_stack

    def __repr__(self):
        base = u"[{} - {}] ERROR: {}\n{}\n".format(self.started, time.time(),
                                                   self.message, self.command)

        if self.include_stack:
            return base + traceback.format_stack()
        return base

