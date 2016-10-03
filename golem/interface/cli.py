import argparse
import shlex
import sys
import time

from golem.interface.command import CommandHelper, CommandStorage, command, Argument
from golem.interface.exceptions import ExecutionException, ParsingException, CommandException
from golem.interface.formatters import CommandFormatter, CommandJSONFormatter
from twisted.internet.defer import TimeoutError


@command(name="exit", help="Exit the interactive shell", root=True)
def _exit():
    CLI.shutdown()


@command(name="help", help="Display this help message", root=True)
def _help():
    message = \
u"""To display command details type:
    command -h"""
    raise ParsingException(message)


# @command(name="debug", help="Display CLI command tree", root=True)
def _debug():
    CommandStorage.debug()


class ArgumentParser(argparse.ArgumentParser):

    def print_help(self, file=None):
        pass

    def error(self, message):
        exc = sys.exc_info()[1]
        raise ParsingException(exc or message, self)

    def exit(self, status=0, message=None):
        raise ParsingException(message, self)


class CLI(object):

    PROG = 'Golem'
    DESCRIPTION = None
    METAVAR = ''

    working = False

    def __init__(self, client=None, roots=None, formatters=None, main_parser=None, main_parser_options=None):

        self.client = client
        self.roots = roots or CommandStorage.roots

        self.parser = None
        self.shared_parser = None
        self.subparsers = None
        self.formatters = []

        self.main_parser = main_parser

        if main_parser_options:
            self.main_options = set({v.get('dest') or k for k, v in main_parser_options.items()})
        else:
            self.main_options = set()

        if self.client:
            self.register_client(self.client)

        if formatters:
            for formatter in formatters:
                self.add_formatter(formatter)
        else:
            self.add_formatter(CommandJSONFormatter())

        self.add_formatter(CommandFormatter())  # default

    def register_client(self, client):
        for root in self.roots:
            setattr(root, 'client', client)

    @classmethod
    def shutdown(cls):
        cls.working = False

    def execute(self, args=None, interactive=False):
        cls = self.__class__

        if interactive:
            import readline
            readline.parse_and_bind("tab: complete")

        cls.working = True
        while cls.working:

            if not args:
                args = self._read_arguments(interactive)

            if args:
                try:
                    result, output = self.process(args)
                except SystemExit:
                    cls.working = False
                else:
                    output.write(result)
                    output.write(u"\n")
                    output.flush()

            args = None
            if not interactive:
                cls.working = False

    def process(self, args):

        if not self.parser:
            self.build()

        formatter = None
        output = sys.stderr
        started = time.time()

        try:

            namespace = self.parser.parse_args(args)
            clean = self._clean_namespace(namespace)
            formatter = self.get_formatter(clean)
            callback = clean.__dict__.pop('callback')
            normalized = self._normalize_namespace(clean)
            result = callback(**normalized)

        except ParsingException as exc:
            parser = exc.parser or self.parser

            if exc.message:
                result = u"{}\n\n{}".format(exc or u"Invalid command", parser.format_help())
            else:
                result = parser.format_help()

        except CommandException as exc:
            result = u"{}".format(exc)

        except TimeoutError:
            result = ExecutionException(u"Command timed out", u" ".join(args), started)

        except Exception as exc:
            result = ExecutionException(u"Exception: {}".format(exc), u" ".join(args), started)

        else:
            output = sys.stdout

        if not formatter:
            formatter = self.formatters[-1]

        try:
            result = formatter.format(result)
        except Exception as exc:
            result = repr(result)
            sys.stderr.write("Formatter error: {}".format(exc))

        if result is None:
            return u"Completed in {}s".format(time.time() - started), output
        return result, output

    def build(self):

        if self.main_parser:
            shared_kw = {'parents': [self.main_parser]}
        else:
            shared_kw = {}

        self.shared_parser = ArgumentParser(add_help=False,
                                            prog=self.PROG,
                                            usage=argparse.SUPPRESS,
                                            **shared_kw)

        self.shared_parser.add_argument("-h", "--help",
                                        action="help",
                                        help="Display command's help message")

        for formatter in self.formatters:
            if formatter.argument:
                self.shared_parser.add_argument('--' + formatter.argument,
                                                action='store_true',
                                                default=False,
                                                help=formatter.help)

        self.parser = ArgumentParser(add_help=False,
                                     prog=self.PROG,
                                     description=self.DESCRIPTION,
                                     parents=[self.shared_parser],
                                     usage=argparse.SUPPRESS)

        self.subparsers = self.parser.add_subparsers(metavar=self.METAVAR)

        for root in self.roots:
            self._build_parser(self.subparsers, None, root)

    def add_formatter(self, formatter):
        if formatter:
            self.formatters.append(formatter)

    def get_formatter(self, namespace):
        namespace_dict = namespace.__dict__
        formatter = None
        for f in self.formatters:
            if f.supports(namespace_dict):
                formatter = f
            f.clear_argument(namespace_dict)
        return formatter or self.formatters[-1]

    def _build_parser(self, parser, parent, elem):

        interface = CommandHelper.get_interface(elem)

        name = interface['name']
        source = interface['source']
        children = interface['children']
        arguments = interface['arguments']
        is_callable = interface['callable']

        subparser = parser.add_parser(name=name,
                                      help=interface.get('help'),
                                      add_help=False,
                                      parents=[self.shared_parser],
                                      usage=argparse.SUPPRESS)

        if is_callable:
            subparser.set_defaults(callback=self._build_callback(parent, source))
        if arguments:
            self._build_arguments(subparser, arguments)
        if children:
            self._build_children(subparser, elem, children, name)

    def _build_children(self, parser, parent, children, name):
        subparser = parser.add_subparsers(title=name, metavar=self.METAVAR,
                                          parser_class=ArgumentParser)
        for child in children.values():
            self._build_parser(subparser, parent, child)

    @staticmethod
    def _build_callback(parent, elem):
        if parent:
            method = CommandHelper.wrap_call(elem)
        else:
            method = elem

        return lambda *a, **kw: method(*a, **kw)

    @staticmethod
    def _build_arguments(parser, arguments):
        for argument in arguments:
            if isinstance(argument, Argument):
                parser.add_argument(*argument.args, **argument.kwargs)

    @classmethod
    def _read_arguments(cls, interactive):
        if interactive:
            try:
                line = raw_input('>> ')
            except ValueError:
                cls.working = False
            else:
                if line:
                    return shlex.split(line)
        else:
            return ['help']

    def _clean_namespace(self, namespace):
        clean = argparse.Namespace(**namespace.__dict__)
        for key in self.main_options:
            clean.__dict__.pop(key, None)
        return clean

    @classmethod
    def _normalize_namespace(cls, namespace):
        return {cls._normalize_key(k): v for k, v in namespace.__dict__.iteritems()}

    @staticmethod
    def _normalize_key(key):
        return key.replace('-', '_')
