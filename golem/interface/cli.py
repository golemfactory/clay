import argparse

import time

import sys
import types

from golem.interface.command import CommandHelper, CommandStorage
from golem.interface.exceptions import ExecutionException, ParsingException
from golem.interface.formatters import CommandFormatter, CommandJSONFormatter


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        exc = sys.exc_info()[1]
        raise ParsingException(exc or message)


class CLI(object):

    DESCRIPTION = 'Golem command line interface'
    METAVAR = ''

    def __init__(self, client, roots=None):

        self.client = client
        self.roots = roots or CommandStorage.roots

        for root in self.roots:
            setattr(root, 'client', client)

        CommandStorage.debug()

        self.parser = None
        self.shared_parser = None
        self.subparsers = None
        self.processors = []
        self.formatters = []

        self.default_formatter = CommandFormatter()
        self.add_formatter(self.default_formatter)
        self.add_formatter(CommandJSONFormatter())

    def execute(self, args=None, interactive=False):
        while True:

            if not args:
                sys.stdout.write(">> ")
                sys.stdout.flush()
                args = sys.stdin.readline().strip().split(' ')

            if args:
                sys.stdout.write(self.process(args))
                sys.stdout.write("\n")
                sys.stdout.flush()

            args = None
            if not interactive:
                break

    def process(self, args):
        if not self.parser:
            self.build()

        formatter = None
        started = time.time()

        try:

            namespace = self.parser.parse_args(args)
            print namespace.__dict__
            formatter = self.get_formatter(namespace)
            callback = namespace.__dict__.pop('callback')
            result = CommandHelper.wait_for(callback(**namespace.__dict__))

        except ParsingException as exc:
            result = exc

        except Exception as exc:
            result = ExecutionException(exc, ' '.join(args), started)

        finally:
            if not formatter:
                formatter = self.default_formatter

        for processor in self.processors:
            result = processor.process(result)
        return formatter.format(result, started)

    def build(self):
        self.shared_parser = ArgumentParser(add_help=False)

        for formatter in self.formatters:
            if formatter.argument:
                self.shared_parser.add_argument('--' + formatter.argument,
                                                action='store_true',
                                                default=False,
                                                help=formatter.help)

        self.parser = ArgumentParser(description=self.DESCRIPTION,
                                     parents=[self.shared_parser])
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
        return formatter or self.default_formatter

    def _build_parser(self, parser, parent, elem):

        interface = CommandHelper.get_interface(elem)

        name = interface['name']
        source = interface['source']
        children = interface['children']
        arguments = interface['arguments']
        is_callable = interface['callable']

        subparser = parser.add_parser(name=interface['name'], help=interface.get('help'),
                                      parents=[self.shared_parser])

        if is_callable:
            subparser.set_defaults(callback=self._build_callback(parent, source))
        if arguments:
            self._build_arguments(subparser, arguments)
        if children:
            self._build_children(subparser, elem, children, name)

    def _build_children(self, parser, parent, children, name):
        subparser = parser.add_subparsers(title=name, metavar=self.METAVAR)
        for child in children.values():
            self._build_parser(subparser, parent, child)

    @staticmethod
    def _build_callback(parent, elem):
        if parent:
            def wrapper(*args, **kwargs):
                elem(parent.instance, *args, **kwargs)
            method = wrapper
        else:
            method = elem
        return lambda *a, **kw: method(*a, **kw)

    @staticmethod
    def _build_arguments(parser, arguments):
        for argument in arguments:
            parser.add_argument(*argument[0], **argument[1])
