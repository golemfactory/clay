import argparse
import sys
import time

from twisted.internet.defer import TimeoutError

from golem.interface.command import CommandHelper, CommandStorage, command
from golem.interface.exceptions import ExecutionException, ParsingException, HelpException
from golem.interface.formatters import CommandFormatter, CommandJSONFormatter


@command(name="exit", help="Exit the interactive shell")
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


@command(name="help", help="Display this help message")
def _help():
    raise HelpException()


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage()
        exc = sys.exc_info()[1]
        raise ParsingException(exc or message)

    def exit(self, status=0, message=None):
        pass


class CLI(object):

    PROG = 'Golem'
    DESCRIPTION = 'Command line interface help'
    METAVAR = ''

    def __init__(self, client, roots=None, processors=None, formatters=None):

        self.client = client
        self.roots = roots or CommandStorage.roots

        self.parser = None
        self.shared_parser = None
        self.subparsers = None
        self.processors = []
        self.formatters = []

        for root in self.roots:
            setattr(root, 'client', client)

        if processors:
            for processor in processors:
                self.add_processor(processor)

        if formatters:
            for formatter in formatters:
                self.add_formatter(formatter)

        self.add_formatter(CommandJSONFormatter())
        self.add_formatter(CommandFormatter())  # default

    def execute(self, args=None, interactive=False):

        if interactive:
            import readline
            readline.parse_and_bind("tab: complete")

        while True:
            if not args:
                line = raw_input('>> ')
                args = line.strip().split(' ')

            if args:
                try:
                    result = self.process(args)
                except SystemExit:
                    break

                if result is not None:
                    sys.stdout.write(result)
                    sys.stdout.write("\n")
                    sys.stdout.flush()

            args = None
            if not interactive:
                _exit(raise_exit=False)
                break

    def process(self, args):
        if not self.parser:
            self.build()

        formatter = None
        result = str()
        started = time.time()

        try:

            namespace = self.parser.parse_args(args)
            formatter = self.get_formatter(namespace)
            callback = namespace.__dict__.pop('callback')
            result = CommandHelper.wait_for(callback(**namespace.__dict__))

        except HelpException:
            self.parser.print_help()

        except ParsingException:
            self.parser.print_help()

        except TimeoutError:
            result = ExecutionException("Command timed out", ' '.join(args), started)

        except Exception as exc:
            result = ExecutionException(exc, ' '.join(args), started)

        finally:
            if not formatter:
                formatter = self.formatters[-1]

        for processor in self.processors:
            result = processor.process(result)

        return formatter.format(result, started)

    def build(self):
        self.shared_parser = ArgumentParser(add_help=False,
                                            prog=self.PROG,
                                            usage=argparse.SUPPRESS)

        for formatter in self.formatters:
            if formatter.argument:
                self.shared_parser.add_argument('--' + formatter.argument,
                                                action='store_true',
                                                default=False,
                                                help=formatter.help)

        self.parser = ArgumentParser(prog=self.PROG,
                                     description=self.DESCRIPTION,
                                     parents=[self.shared_parser],
                                     add_help=False,
                                     usage=argparse.SUPPRESS)

        self.subparsers = self.parser.add_subparsers(metavar=self.METAVAR)

        for root in self.roots:
            self._build_parser(self.subparsers, None, root)

    def add_processor(self, processor):
        if processor:
            self.processors.append(processor)

    def add_formatter(self, formatter):
        if formatter:
            self.formatters.append(formatter)

    def get_formatter(self, namespace):
        namespace_dict = namespace.__dict__
        formatter = None
        for f in self.formatters:
            if f.supports(namespace_dict):
                formatter = f
            f.remove_option(namespace_dict)
        return formatter or self.formatters[-1]

    def _build_parser(self, parser, parent, elem):

        interface = CommandHelper.get_interface(elem)

        name = interface['name']
        source = interface['source']
        children = interface['children']
        arguments = interface['arguments']
        is_callable = interface['callable']

        subparser = parser.add_parser(name=interface['name'],
                                      help=interface.get('help'),
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
            parser.add_argument(*argument[0], **argument[1])
