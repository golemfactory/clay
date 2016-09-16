import argparse
import sys
import time

from twisted.internet.defer import TimeoutError

from golem.interface.command import CommandHelper, CommandStorage, command, Argument
from golem.interface.exceptions import ExecutionException, ParsingException, CommandException
from golem.interface.formatters import CommandFormatter, CommandJSONFormatter


@command(name="exit", help="Exit the interactive shell", root=True)
def _exit(raise_exit=True):
    from twisted.internet import reactor
    from twisted.internet.error import ReactorNotRunning

    try:
        if reactor.running:
            reactor.callFromThread(reactor.stop)
        if raise_exit:
            sys.exit(0)
    except ReactorNotRunning:
        pass
    except Exception as exc:
        import logging
        logging.error("Shutdown error: {}".format(exc))


@command(name="help", help="Display this help message", root=True)
def _help():
    message = \
u"""To display command details type:
    command -h"""
    raise ParsingException(message)


@command(name="debug", help="Display CLI command tree", root=True)
def _debug():
    CommandStorage.debug()


class ArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        self.print_usage()
        exc = sys.exc_info()[1]
        raise ParsingException(exc or message, self)

    def exit(self, status=0, message=None):
        pass


class CLI(object):

    PROG = 'Golem'
    DESCRIPTION = None
    METAVAR = ''

    def __init__(self, client, roots=None, formatters=None):

        self.client = client
        self.roots = roots or CommandStorage.roots

        self.parser = None
        self.shared_parser = None
        self.subparsers = None
        self.formatters = []

        for root in self.roots:
            setattr(root, 'client', client)

        if formatters:
            for formatter in formatters:
                self.add_formatter(formatter)
        else:
            self.add_formatter(CommandJSONFormatter())

        self.add_formatter(CommandFormatter())  # default

    def execute(self, args=None, interactive=False):

        if interactive:
            import readline
            readline.parse_and_bind("tab: complete")

        while True:
            if not args:
                line = raw_input('>> ')
                if line:
                    args = line.strip().split(' ')
                else:
                    args = None

            if args:
                try:
                    result, output = self.process(args)
                    sys.stdout.write(result)
                except SystemExit:
                    break
                else:
                    output.write(result)
                    output.write(u"\n")
                    output.flush()

            args = None
            if not interactive:
                _exit(raise_exit=False)
                break

    def process(self, args):

        if not self.parser:
            self.build()

        formatter = None
        output = sys.stderr
        started = time.time()

        try:

            namespace = self.parser.parse_args(args)
            formatter = self.get_formatter(namespace)
            callback = namespace.__dict__.pop('callback')
            normalized = self._normalize_namespace(namespace)
            result = callback(**normalized)

        except ParsingException as exc:
            parser = exc.parser or self.parser
            result = u"{}\n\n{}".format(exc, parser.format_help())

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

        result = formatter.format(result)
        if result is None:
            return u"Completed in {}s".format(time.time() - started), output
        return result, output

    def build(self):
        self.shared_parser = ArgumentParser(add_help=False,
                                            prog=self.PROG,
                                            usage=argparse.SUPPRESS)
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
    def _normalize_namespace(cls, namespace):
        return {cls._normalize_key(k): v for k, v in namespace.__dict__.iteritems()}

    @staticmethod
    def _normalize_key(key):
        return key.replace('-', '_')
