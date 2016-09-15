import time
import traceback

import datetime


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

    def __init__(self, message, command, started):
        self.message = message
        self.command = command
        self.started = started

    def __repr__(self):
        return u"[{}] ERROR: {}".format(self.time_str(time.time()), self.message)

    @staticmethod
    def time_str(timestamp):
        if timestamp:
            return datetime.datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')
        return ""
