import argparse
import shlex
import sys
import time
from copy import deepcopy
from typing import Text, Dict, Callable, Optional, List

from golem.interface.command import CommandHelper, CommandStorage, command, \
    Argument, INCLUDE_CALL_DURATION
from golem.interface.exceptions import ExecutionException, ParsingException, \
    CommandException, CommandCanceledException
from golem.interface.formatters import CommandFormatter, CommandJSONFormatter
from twisted.internet.defer import TimeoutError


@command(name="exit", help="Exit the interactive shell", root=True)
def _exit():
    CLI.shutdown()


@command(name="help", help="Display this help message", root=True)
def _help():
    message = \
"""To display command details type:
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


def disable_withdraw(
        children: Dict[Text, Callable]) -> Dict[Text, Callable]:
    """
    This function adapts children of an interface: if golemcli is not run on
    mainnet, there should be no option to `withdraw` for `golemcli account`
    """
    new_children = deepcopy(children)
    from golem.config.active import EthereumConfig
    if not EthereumConfig.WITHDRAWALS_ENABLED:
        if 'withdraw' in new_children:
            new_children.pop('withdraw')
    return new_children


def optionally_include_run_time(result, started, callback):
    duration_string = "Completed in {0:.2f} s".format(time.time() - started)
    if result is None:
        return duration_string
    # dirty hack: the original function is wrapped several times...
    if callback and len(callback.__closure__) > 1 and \
            hasattr(
                    callback.__closure__[0].cell_contents, INCLUDE_CALL_DURATION
            ):
        result = result + ' ' + duration_string
    return result


def process_hardcoded_settings_output(
        result: Optional[str],
        args: List[str],
        namespace: argparse.Namespace,
        started: float,
) -> Optional[str]:
    # pylint: disable=line-too-long, bad-continuation
    # 1. 'settings' and 'set' are not in args, different cmd was executed and
    # there is nothing to do
    # 2. If `namespace` doesn't have specific attributes, something must have
    # gone wrong and result should not be modified
    if 'settings' not in args or 'set' not in args \
            or not (hasattr(namespace, 'key') and hasattr(namespace, 'value')):
        return result

    output_map = {
        'node_name': lambda v: f'Node name changed to: {v} in '
                               f'{(time.time() - started):.2f} s.'
                               ' To confirm run `golemcli settings show`',
        'accept_tasks': lambda v: f'Your node will{" not" * (int(v) == 0)} accept'  # noqa
                                  f' tasks{" (acting as requestor only)" * (int(v) == 0)}.'  # noqa
                                  ' To confirm run `golemcli settings show`',
        'getting_tasks_interval': lambda v: f'Getting tasks interval set to: {v} seconds.'  # noqa
                                            ' To confirm run `golemcli settings show`',  # noqa
        'getting_peers_interval': lambda v: f'Getting peers interval set to: {v}.'  # noqa
                                            ' To confirm run `golemcli settings show`',  # noqa
        'task_session_timeout': lambda v: f'Task session timeout set to: {v}.'
                                          ' To confirm run `golemcli settings show`',  # noqa
        'p2p_session_timeout': lambda v: f'p2p session timeout set to: {v}.'
                                         ' To confirm run `golemcli settings show`',  # noqa
        'requesting_trust': lambda v: f'Requesting trust set to: {v}.'
                                      ' To confirm run `golemcli settings show`',  # noqa
        'computing_trust': lambda v: f'Computing trust set to: {v} GNT.'
                                     ' To confirm run `golemcli settings show`',
        'min_price': lambda v: f'Minimal price set to: {v} GNT.'
                               ' To confirm run `golemcli settings show`',
        'max_price': lambda v: f'Maximum price set to: {v} GNT.'
                               ' To confirm run `golemcli settings show`',
        'use_ipv6': lambda v: f'Using ipv6 set to {bool(int(v))}.'
                              ' To confirm run `golemcli settings show`',
        'opt_peer_num': lambda v: f'Number of peers to keep set to {v}.'
                                  ' To confirm run `golemcli settings show`',
        'send_pings': lambda v: f'Send pings set to {bool(int(v))}.'
                                ' To confirm run `golemcli settings show`',
        'pings_interval': lambda v: f'Pings interval set to: {v}.'
                                    ' To confirm run `golemcli settings show`',
        'max_memory_size': lambda v: f'Maximal memory size set to: {v}.'
                                     ' To confirm run `golemcli settings show`',
        'num_cores': lambda v: f'Number of CPU cores to use set to: {v}.'
                               ' To confirm run `golemcli settings show`',
        'enable_talkback': lambda v: f'Talkback enabled: {bool(int(v))}'
    }

    if namespace.key in output_map:
        return output_map[namespace.key](namespace.value)

    return result


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
            self.main_options = set({v.get('dest') or k for k, v in list(main_parser_options.items())})
        else:
            self.main_options = set()

        if self.client:
            self.register_client(self.client)

        if formatters:
            for formatter in formatters:
                self.add_formatter(formatter)
        else:
            self.add_formatter(CommandJSONFormatter())

        self.add_formatter(CommandFormatter(prettify=False))  # default

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
                    output.write("\n")
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

        callback = None
        namespace = None
        try:

            namespace = self.parser.parse_args(args)
            clean = self._clean_namespace(namespace)
            formatter = self.get_formatter(clean)
            callback = clean.__dict__.pop('callback')
            normalized = self._normalize_namespace(clean)
            result = callback(**normalized)

        except ParsingException as exc:
            parser = exc.parser or self.parser

            if exc:
                result = "{}\n\n{}".format(exc or "Invalid command", parser.format_help())
            else:
                result = parser.format_help()

        except CommandException as exc:
            result = "{}".format(exc)

        except TimeoutError:
            result = ExecutionException("Command timed out", " ".join(args), started)

        except CommandCanceledException:
            result = 'Command cancelled.'

        except Exception as exc:
            result = ExecutionException("Exception: {}".format(exc), " ".join(args), started)

        else:
            output = sys.stdout

        if not formatter:
            formatter = self.formatters[-1]

        try:
            result = formatter.format(result)
        except Exception as exc:
            result = repr(result)
            sys.stderr.write("Formatter error: {}".format(exc))

        result = process_hardcoded_settings_output(result, args, namespace,
                                                   started)
        result = optionally_include_run_time(result, started, callback)
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

        self.rearrange_action_groups()

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
        children = disable_withdraw(interface['children'])
        arguments = interface['arguments']
        is_callable = interface['callable']

        subparser = parser.add_parser(name=name,
                                      help=interface.get('help'),
                                      add_help=False,
                                      parents=[self.shared_parser],
                                      usage=argparse.SUPPRESS)

        if is_callable:
            subparser.set_defaults(callback=self._build_callback(parent, source))
        else:
            subparser.set_defaults(callback=subparser.format_help)
        if arguments:
            self._build_arguments(subparser, arguments)
        if children:
            self._build_children(subparser, elem, children, name)

    def _build_children(self, parser, parent, children, name):
        subparser = parser.add_subparsers(title=name, metavar=self.METAVAR,
                                          parser_class=ArgumentParser)
        for child in list(children.values()):
            self._build_parser(subparser, parent, child)

    @staticmethod
    def _build_callback(parent, elem):
        if parent:
            return CommandHelper.wrap_call(elem)
        return elem

    @staticmethod
    def _build_arguments(parser, arguments):
        for argument in arguments:
            if isinstance(argument, Argument):
                parser.add_argument(*argument.args, **argument.kwargs)

    @classmethod
    def _read_arguments(cls, interactive):
        if interactive:
            try:
                line = input('>> ')
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
        return {cls._normalize_key(k): v for k, v in list(namespace.__dict__.items())}

    @staticmethod
    def _normalize_key(key):
        return key.replace('-', '_')

    def rearrange_action_groups(self):
        for parser in self.subparsers.choices.values():
            action_groups = parser._action_groups  # pylint: disable=protected-access
            # If there are more action groups than just
            # 'positional arguments' and 'optional arguments'...
            if len(action_groups) > 2:
                # ... then move them to the beginning.
                parser._action_groups = action_groups[2:] + action_groups[:2]  # pylint: disable=protected-access
