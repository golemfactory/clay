import argparse
import shlex
import sys
import time
from collections import namedtuple
from copy import deepcopy
from typing import Text, Dict, Callable, List, Optional

from twisted.internet.defer import TimeoutError

from golem.interface.command import CommandHelper, CommandStorage, command, \
    Argument
from golem.interface.exceptions import ExecutionException, ParsingException, \
    CommandException
from golem.interface.formatters import CommandFormatter, CommandJSONFormatter


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


def _ask_for_confirmation(question: str) -> bool:
    text = input(f'{question} (y/n) ')
    return True if text == 'y' else False


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
        return self._create_return_message(args, started, result), output

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

    def _create_return_message(
            self,
            args: List[str],
            started: float,
            result: Optional[str]
    ) -> str:

        def _fill_messages_to_print_with_return_messages():
            _add(['settings', 'set', 'min_price'],
                 f'Minimal price set to: {args[-1]}.', True)
            _add(['settings', 'set', 'max_price'],
                 f'Maximum price set to: {args[-1]}.', True)
            _add(['concent', 'switch', 'turn'],
                 f'Concent switch turned {args[-1]}.')
            _add(['envs', 'disable'], f'Env {args[-1]} disabled.')
            _add(['envs', 'enable'], f'Env {args[-1]} enabled.')
            _add(['envs', 'perf_mult_set'],
                 f'Envs perf_mult_set to {args[-1]}.')
            _add(['network', 'block'], f'{args[-1]} blocked.')
            _add(['network', 'connect'],
                 f'Connected with: Ip: {args[-2]}. Port: {args[-1]}.')
            _add(['tasks', 'create'], f'Task with id {result} '
                 f'was created. To confirm run golemcli task show.')
            _add(['settings', 'set', 'node_name'],
                 f'Node name changed to: {args[-1]}.', True)
            _add(['settings', 'set', 'accept_tasks', '1'],
                 f'Your node will accept tasks.', True)
            _add(['settings', 'set', 'accept_tasks', '0'],
                 f'Your node will not '
                 f'accept tasks (acting as requestor only).', True)
            _add(['settings', 'set', 'getting_tasks_interval'],
                 f'Getting tasks interval set to: {args[-1]} seconds.', True)
            _add(['settings', 'set', 'getting_peers_interval'],
                 f'Getting peers interval set to: {args[-1]} seconds.', True)
            _add(['settings', 'set', 'task_session_timeout'],
                 f'Task session timeout set to: {args[-1]} seconds.', True)
            _add(['settings', 'set', 'p2p_session_timeout'],
                 f'p2p session timeout set to: {args[-1]} seconds.', True)
            _add(['settings', 'set', 'requesting_trust'],
                 f'Requesting_trust set to: {args[-1]}.', True)
            _add(['settings', 'set', 'computing_trust'],
                 f'Computing trust set to: {args[-1]} GNT.', True)
            _add(['settings', 'set', 'use_ipv6', '1'],
                 f'Using ipv6 set to: True.', True)
            _add(['settings', 'set', 'use_ipv6', '0'],
                 f'Using ipv6 set to: False.', True)
            _add(['settings', 'set', 'opt_peer_num'],
                 f'Number of peers to keep set to: {args[-1]}.', True)
            _add(['settings', 'set', 'send_pings', '1'],
                 f'Send pings set to: True.', True)
            _add(['settings', 'set', 'send_pings', '0'],
                 f'Send pings set to: False.', True)
            _add(['settings', 'set', 'pings_interval'],
                 f'Pings interval set to: {args[-1]} seconds.', True)
            _add(['settings', 'set', 'max_memory_size'],
                 f'Maximal memory size set to: {args[-1]}.', True)
            _add(['settings', 'set', 'max_memory_size'],
                 f'Maximal memory size set to: {args[-1]}.', True)
            _add(['settings', 'set', 'num_cores'],
                 f'Number of CPU cores to use set to: {args[-1]}.', True)
            _add(['settings', 'set', 'enable_talkbacks', '0'],
                 f'Talkback enabled: False')
            _add(['settings', 'set', 'enable_talkbacks', '1'],
                 f'Talkback enabled: True')
            if 'account' and 'withdraw' in args:
                _add(['account', 'withdraw'],
                     f'Sent {args[-2]} GNT to: {args[-3]}. Gas fee: {args[-1]} '
                     f'WEI. Transaction hash (check on etherscan.io): {result}')
            return self.messages_to_print

        def _add(keys: list, values: str, add_cli_hint=False):
            hint = ' To confirm run golemcli settings show.'
            values = values + hint if add_cli_hint else values
            self.messages_to_print[' '.join(map(str, keys))] = values

        self.messages_to_print: Dict[str, str] = dict()  # pylint: disable=attribute-defined-outside-init
        _fill_messages_to_print_with_return_messages()
        time_message = f' Completed in {time.time() - started:.3f} s.'
        for key, value in self.messages_to_print.items():
            if key in ' '.join(map(str, args)):
                return value + time_message

        Mes = namedtuple('Mes', 'list_of_keys confirmation question')

        messages_with_confirmation = [
            Mes(list_of_keys=' '.join(map(str, ['tasks', 'abort'])),
                confirmation=f'Task {args[-1]} aborted. To confirm run golemcli tasks show.',  # noqa pylint: disable=line-too-long
                question=f'Are you sure? Confirm aborting {args[-1]} task'),
            Mes(list_of_keys=' '.join(map(str, ['tasks', 'purge'])),
                confirmation=f'All tasks were purged. To confirm run golemcli tasks show.',  # noqa pylint: disable=line-too-long
                question=f'Are you sure? Confirm purging all tasks'),
            Mes(list_of_keys=' '.join(map(str, ['tasks', 'restart_subtasks', 'id'])),  # noqa pylint: disable=line-too-long
                confirmation=f'All subtasks of a {args[-1]} task were restarted',  # noqa pylint: disable=line-too-long
                question=f'Are you sure? Confirm restarting all task {args[-1]} subtasks'),  # noqa pylint: disable=line-too-long
            Mes(list_of_keys=' '.join(map(str, ['tasks', 'restart_subtasks', 'subtask_ids'])),  # noqa pylint: disable=line-too-long
                confirmation=f'Subtask with {args[-1]} was restarted',
                question=f'Are you sure? Confirm restarting subtask with {args[-1]} id'),  # noqa pylint: disable=line-too-long
            Mes(list_of_keys=' '.join(map(str, ['tasks', 'restart_subtasks', 'force'])),  # noqa pylint: disable=line-too-long
                confirmation=f'Subtask with {args[-1]} was restarted',
                question=f'Are you sure? Confirm restarting subtasks with {args[-1]} id'),  # noqa pylint: disable=line-too-long
            Mes(list_of_keys=' '.join(map(str, ['tasks', 'restart'])),
                confirmation=f'Task {args[-1]} was restarted as a new task with id {result}',  # noqa pylint: disable=line-too-long
                question=f'Are you sure? Confirm restarting {args[-1]}')]

        for element in messages_with_confirmation:
            if element[0] in ' '.join(map(str, args)):
                if _ask_for_confirmation(element[2]) is True:  # pylint:disable=no-else-return
                    return element[1] + time_message
                else:
                    return "Command aborted"

        return result if result is not None else "Unexpected return message"
