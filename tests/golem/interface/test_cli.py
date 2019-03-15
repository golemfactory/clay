import argparse
import time
import unittest
from unittest.mock import patch, Mock

from io import StringIO

import pytest
from twisted.internet import defer
from twisted.internet.error import ReactorNotRunning

from golem.interface.cli import (
    CLI, _exit, _help, _debug, ArgumentParser, disable_withdraw,
)
from golem.interface.command import (
    group, doc, argument, identifier, name, command, CommandHelper,
    storage_context,
)
from golem.interface.exceptions import ParsingException, CommandException


def _nop(*a, **kw):
    pass


def _raise(*a, **kw):
    raise Exception()


def _raise_sys_exit(*a, **kw):
    raise SystemExit()


class MockReactor(Mock):

    def __init__(self, *args, **kwargs):
        super(MockReactor, self).__init__(*args, **kwargs)

        self.running = True
        self.do_raise = True
        self.exc_class = ReactorNotRunning

    def callFromThread(self, *_):
        if self.do_raise:
            raise self.exc_class()


class MockStdout(Mock):
    data = ''

    def write(self, data):
        self.data += data


class TestCLI(unittest.TestCase):

    __input = 'builtins.input'

    class MockFormatter(Mock):

        def supports(self, *args, **kwargs):
            return True

    class MockClient(object):
        return_value = None

        def __deferred_return_value(self):
            deferred = defer.Deferred()
            deferred.callback(self.return_value)
            return deferred

        def __getattribute__(self, name):
            if name.startswith('_') or name == 'return_value':
                return object.__getattribute__(self, name)
            return lambda *args, **kwargs: self.return_value

    @patch('sys.stdout', new_callable=StringIO)
    @patch('golem.interface.cli.CLI.process',
           side_effect=lambda x: (' '.join(x), Mock()))
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_execute(self, _, _process, _out):

        client = self.MockClient()
        cli = CLI(client=client, formatters=[self.MockFormatter()])

        with patch(self.__input, return_value='', create=True):
            cli.execute()

        _process.assert_called_with(['help'])
        self.assertFalse(_out.getvalue())

        _process.called = False

        cmd = 'invalid_command --invalid-flag'
        with patch(self.__input, return_value=cmd, create=True):
            cli.execute()

        self.assertTrue(_process.called)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.interface.cli.CLI.process', side_effect=_raise)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_execute_exception(self, _, _process, _exit, _out):

        client = self.MockClient()
        cli = CLI(client=client, formatters=[self.MockFormatter()])

        cmd = 'invalid_command --invalid-flag'
        with patch(self.__input, return_value=cmd, create=True):
            with self.assertRaises(Exception):
                cli.execute()

            self.assertTrue(_process.called)
            self.assertFalse(_exit.called)
            self.assertFalse(_out.getvalue())

    @patch('sys.stdout', new_callable=MockStdout)
    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.interface.cli.CLI.process', side_effect=_raise_sys_exit)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_execute_exit(self, _, _process, _exit, _out):

        client = self.MockClient()
        cli = CLI(client=client)

        cmd = 'invalid_command --invalid-flag'
        with patch(self.__input, return_value=cmd, create=True):
            cli.execute()
            self.assertTrue(_process.called)
            self.assertFalse(_exit.called)
            self.assertFalse(_out.data)

    @patch('golem.interface.cli.CLI.process', side_effect=_raise_sys_exit)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_interactive(self, _, _process):
        client = self.MockClient()
        cli = CLI(client=client)

        with patch(self.__input, return_value='exit', create=True):
            cli.execute(interactive=True)
            self.assertTrue(_process.called)

    @patch('builtins.input', create=True)
    @patch('golem.interface.cli._exit', side_effect=_nop)
    def test_execute_interactive(self, _exit, _ri):

        with storage_context():

            @group("commands")
            class MockClass(object):

                def command(self):
                    pass

                def exit(self):
                    raise SystemExit()

            client = self.MockClient()
            cli = CLI(client=client)

            cli.execute(['commands', 'exit'], interactive=True)
            self.assertFalse(_exit.called)

    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_process(self, *_):

        with storage_context():

            @group("commands")
            class MockClass(object):

                def command(self):
                    pass

            client = self.MockClient()
            cli = CLI(client=client)

            with patch('sys.stderr', new_callable=StringIO) as err:
                cli.process(['commands', 'command'])
                self.assertTrue(not err.getvalue())

    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_process_errors(self, config_logging, cli_exit):

        exceptions = [
            ParsingException, CommandException, defer.TimeoutError, Exception,
        ]

        with storage_context():

            @group("commands", help="command group")
            class MockClass(object):
                exc_class = None

                @doc("Some help")
                def command(self):
                    raise self.exc_class()

                def command_2(self):
                    raise Exception("error")

            client = self.MockClient()
            cli = CLI(client=client)

            for exc_class in exceptions:

                MockClass.exc_class = exc_class
                result, _ = cli.process(['commands', 'command'])

                with patch('sys.stderr', new_callable=MockStdout) as out:
                    cli.execute(['commands', 'command_2'])
                    self.assertIsNotNone(out.data)

    def test_args(self):

        with storage_context():

            client = self.MockClient()
            cli = CLI(client=client)

            expected = ['test', 'string with spaces', '--flag', 'value']

            cmd = 'test "string with spaces" --flag "value"'
            with patch(self.__input, return_value=cmd, create=True):
                self.assertEqual(cli._read_arguments(interactive=True),
                                 expected)

    def test_build(self):

        with storage_context():

            @group("mock")
            class MockClass(object):

                @name('mock_help')
                @doc("Help string")
                def help_method(self):
                    pass

                @argument("--test-flag", "-tf", optional=True)
                def arg_method(self, test_flag):
                    pass

                @identifier("some_id")
                def id_method(self, some_id):
                    pass

                @name("renamed_method")
                def method(self):
                    pass

                def method_2(self):
                    pass

                def _ignored_method(self):
                    pass

                @staticmethod
                def static_method():
                    pass

            @command("outer", root=True)
            def root():
                pass

            @command("outer_2", parent=MockClass)
            def not_root():
                pass

            client = self.MockClient()
            cli = CLI(client=client)
            cli.build()

            def actions(_parser):
                return [action for action in _parser._actions
                        if isinstance(action, argparse._SubParsersAction)]

            def choices(_actions):
                result = {}
                for action in _actions:
                    for choice, subparser in list(action.choices.items()):
                        result[choice] = subparser
                return result

            cli_actions = actions(cli.parser)
            cli_choices = choices(cli_actions)

            self.assertEqual(len(cli_choices), 2)
            self.assertIn('mock', list(cli_choices.keys()))
            self.assertIn('outer', list(cli_choices.keys()))

            mock_actions = actions(cli_choices['mock'])
            mock_choices = choices(mock_actions)
            expected_choices = ['arg_method', 'method_2', 'mock_help',
                                'id_method', 'outer_2', 'renamed_method',
                                'static_method']

            self.assertEqual(len(mock_choices), len(expected_choices))
            self.assertTrue(all([c in list(mock_choices.keys())
                                 for c in expected_choices]))

            self.assertTrue(any([a.option_strings == ['--test-flag', '-tf'] and
                                 isinstance(a, argparse._StoreTrueAction)
                                 for a in mock_choices['arg_method']._actions]))

            string_actions = mock_choices['arg_method']._option_string_actions
            self.assertIn('--test-flag', string_actions)
            self.assertIn('-tf', string_actions)

            args = mock_choices['id_method']._positionals._actions
            self.assertTrue(any([a.dest == 'some_id' and
                                 a.help == 'Object id' and
                                 isinstance(a, argparse._StoreAction)
                                 for a in args]))

    def test_cli_formatter(self):
        """ Test for setting and getting formatter """
        from golem.interface.formatters import (
            CommandFormatter, CommandJSONFormatter
        )

        client = self.MockClient()
        cli = CLI(client=client)
        cli.add_formatter(CommandFormatter())
        cli.add_formatter(CommandJSONFormatter())
        assert cli.get_formatter(CommandJSONFormatter())
        assert cli.get_formatter(CommandFormatter())


class TestCLICommands(unittest.TestCase):

    @patch('logging.error')
    @patch('sys.exit')
    @patch('twisted.internet.reactor', create=True, new_callable=MockReactor)
    def test_exit(self, reactor, sys_exit, logging_error):
        self.assertIsNotNone(CommandHelper.get_interface(_exit))

        with patch('golem.interface.cli.CLI.shutdown') as shutdown:
            _exit()
            self.assertTrue(shutdown.called)

    def test_help(self):
        self.assertIsNotNone(CommandHelper.get_interface(_help))

        with self.assertRaises(ParsingException):
            _help()

    @patch('sys.stdout', new_callable=MockStdout)
    def test_debug(self, out):
        _debug()
        self.assertTrue(out.getvalue())


class TestArgumentParser(unittest.TestCase):

    def test_error(self):

        ap = ArgumentParser()

        try:
            raise Exception("test")
        except Exception as _:
            with self.assertRaises(ParsingException) as exc:
                ap.error("custom")
                self.assertNotEqual(exc.exception.message, "custom")
                self.assertIsInstance(exc.exception.message, ParsingException)

        with self.assertRaises(ParsingException) as exc:
            ap.error("custom")
            self.assertEqual(exc.exception.message, "custom")

    def test_exit(self):

        ap = ArgumentParser()
        with self.assertRaises(ParsingException):
            ap.exit()


class TestAdaptChildren(unittest.TestCase):
    def setUp(self):
        def foofun():
            pass

        def barfun():
            pass

        self.children = {
            'withdraw': foofun,
            'sth else': barfun,
        }

    def test_empty_remains_empty(self):
        result = disable_withdraw({})
        self.assertEqual(result, {})

    def test_no_adaptation_for_mainnet(self):
        from golem.config.environments.mainnet import EthereumConfig
        with patch('golem.config.active.EthereumConfig', EthereumConfig):
            result = disable_withdraw(self.children)
            self.assertEqual(result, self.children)

    def test_remove_withdraw_if_not_mainnet(self):
        from golem.config.environments.testnet import EthereumConfig
        with patch('golem.config.active.EthereumConfig', EthereumConfig):
            result = disable_withdraw(self.children)
            self.children.pop('withdraw')
            self.assertEqual(result, self.children)


class TestCreateReturnMessage:
    # pylint: disable=attribute-defined-outside-init

    @pytest.mark.parametrize(('args', 'expected'), [
        (['concent', 'switch', 'turn', 'off'], 'Concent switch turned off.'),
        (['envs', 'disable', 'BLENDER'], 'Env BLENDER disabled.'),
        (['envs', 'enable', 'BLENDER'], 'Env BLENDER enabled.'),
        (['envs', 'perf_mult_set', '1.3'], 'Envs perf_mult_set to 1.3.'),
        (['network', 'block', 'custom_id'], 'custom_id blocked.'),
        (['network', 'connect', '192.168.1.1', '80'], 'Connected with: Ip: 192.168.1.1. Port: 80'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'min_price', '0.02'], 'Minimal price set to: 0.02. To confirm run golemcli settings show.'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'max_price', '0.02'], 'Maximum price set to: 0.02. To confirm run golemcli settings show.'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'accept_tasks', '1'], 'Your node will accept tasks. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'accept_tasks', '0'],
         'Your node will not accept tasks (acting as requestor only). To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'use_ipv6', '0'], 'Using ipv6 set to: False. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'use_ipv6', '1'], 'Using ipv6 set to: True. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'send_pings', '1'], 'Send pings set to: True. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'send_pings', '0'], 'Send pings set to: False. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'enable_talkbacks', '0'], 'Talkback enabled: False'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'enable_talkbacks', '1'], 'Talkback enabled: True'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'getting_tasks_interval', '2'],
         'Getting tasks interval set to: 2 seconds. To confirm run golemcli settings show.'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'node_name', 'new_name'], 'Node name changed to: new_name. To confirm run golemcli settings show.'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'getting_peers_interval', '2'],
         'Getting peers interval set to: 2 seconds. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'task_session_timeout', '2'],
         'Task session timeout set to: 2 seconds. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'p2p_session_timeout', '2'],
         'p2p session timeout set to: 2 seconds. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'requesting_trust', '2'],
         'Requesting_trust set to: 2. To confirm run golemcli settings show'),
        (['settings', 'set', 'computing_trust', '2'], 'Computing trust set to: 2 GNT. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'opt_peer_num', '2'], 'Number of peers to keep set to: 2. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'pings_interval', '2'], 'Pings interval set to: 2 seconds. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'max_memory_size', '2'], 'Maximal memory size set to: 2. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
        (['settings', 'set', 'num_cores', '2'], 'Number of CPU cores to use set to: 2. To confirm run golemcli settings show'),  # noqa pylint: disable=line-too-long
    ])
    def test_create_return_message_returns_correct_message(
            self,
            args,
            expected,
    ):
        self.cli = CLI(client=Mock())
        return_message = self.cli._create_return_message(
            args, time.time(), None)
        assert expected in return_message

    @pytest.mark.parametrize(('args', 'expected', 'result'), [
        (['tasks', 'create'],
         'Task with id custom_task_id was created. To confirm run golemcli task show.',  # noqa pylint: disable=line-too-long
         'custom_task_id'),
        (['account', 'withdraw', 'address', 'gnt_amount', 'gas_fee'],
         'Sent gnt_amount GNT to: address. Gas fee: gas_fee WEI. Transaction hash (check on etherscan.io): tx_hash',
         'tx_hash'),
    ])
    def test_create_return_message_returns_correct_message_when_result_given(
            self,
            args,
            expected,
            result
    ):
        self.cli = CLI(client=Mock())
        return_message = self.cli._create_return_message(
            args, time.time(), result)
        assert expected in return_message

    @pytest.mark.parametrize(('args', 'expected'), [
        (['tasks', 'abort', 'custom_task_id'], 'Task custom_task_id aborted. To confirm run golemcli tasks show'),  # noqa pylint: disable=line-too-long
        (['tasks', 'purge'], 'All tasks were purged. To confirm run golemcli tasks show'),  # noqa pylint: disable=line-too-long
        (['tasks', 'restart_subtasks', 'id', 'custom_task_id'], 'All subtasks of a custom_task_id task were restarted'),  # noqa pylint: disable=line-too-long
        (['tasks', 'restart_subtasks', 'subtask_ids', 'custom_subtask_id'], 'Subtask with custom_subtask_id was restarted'),  # noqa pylint: disable=line-too-long
        (['tasks', 'restart_subtasks', 'force', 'custom_subtask_id'], 'Subtask with custom_subtask_id was restarted'),  # noqa pylint: disable=line-too-long
    ])
    def test_create_return_message_returns_correct_message_when_confirmation(
            self,
            args,
            expected,
    ):
        self.cli = CLI(client=Mock())

        with patch('golem.interface.cli._ask_for_confirmation',
                   return_value=True):
            return_message = self.cli._create_return_message(
                args, time.time(), None)
            assert expected in return_message

        with patch('golem.interface.cli._ask_for_confirmation',
                   return_value=False):
            return_message = self.cli._create_return_message(
                args, time.time(), None)
            assert return_message == 'Command aborted'
