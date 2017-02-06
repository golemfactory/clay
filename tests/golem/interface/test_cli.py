import argparse
import unittest
from io import StringIO

from golem.interface.cli import CLI, _exit, _help, _debug, ArgumentParser
from golem.interface.command import group, doc, argument, identifier, name, command, CommandHelper, storage_context
from golem.interface.exceptions import ParsingException, CommandException
from mock import patch, Mock, mock
from twisted.internet.defer import Deferred, TimeoutError
from twisted.internet.error import ReactorNotRunning


def _nop(*a, **kw):
    pass


def _raise(*a, **kw):
    raise Exception()


def _raise_sys_exit(*a, **kw):
    raise SystemExit()


class MockReactor(mock.Mock):

    def __init__(self, *args, **kwargs):
        super(MockReactor, self).__init__(*args, **kwargs)

        self.running = True
        self.do_raise = True
        self.exc_class = ReactorNotRunning

    def callFromThread(self, *_):
        if self.do_raise:
            raise self.exc_class()


class MockStdout(mock.Mock):
    data = ''

    def write(self, data):
        self.data += data


class TestCLI(unittest.TestCase):

    __raw_input = '__builtin__.raw_input'

    class MockFormatter(Mock):
        def supports(self, *args, **kwargs):
            return True

    class MockClient(object):
        return_value = None

        def __deferred_return_value(self):
            deferred = Deferred()
            deferred.callback(self.return_value)
            return deferred

        def __getattribute__(self, name):
            if name.startswith('_') or name == 'return_value':
                return object.__getattribute__(self, name)
            return lambda *args, **kwargs: self.return_value

    @patch('sys.stdout', new_callable=StringIO)
    @patch('golem.interface.cli.CLI.process', side_effect=lambda x: (u' '.join(x), Mock()))
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_execute(self, _, _process, _out):

        client = self.MockClient()
        cli = CLI(client=client, formatters=[self.MockFormatter()])

        with patch(self.__raw_input, return_value=''):
            cli.execute()

        _process.assert_called_with(['help'])
        self.assertFalse(_out.getvalue())

        _process.called = False

        with patch(self.__raw_input, return_value='invalid_command --invalid-flag'):
            cli.execute()

        self.assertTrue(_process.called)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.interface.cli.CLI.process', side_effect=_raise)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_execute_exception(self, _, _process, _exit, _out):

        client = self.MockClient()
        cli = CLI(client=client, formatters=[self.MockFormatter()])

        with patch(self.__raw_input, return_value='invalid_command --invalid-flag'):
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

        with patch(self.__raw_input, return_value='invalid_command --invalid-flag'):
            cli.execute()
            self.assertTrue(_process.called)
            self.assertFalse(_exit.called)
            self.assertFalse(_out.data)

    @patch('golem.interface.cli.CLI.process', side_effect=_raise_sys_exit)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_interactive(self, _, _process):
        client = self.MockClient()
        cli = CLI(client=client)

        with patch(self.__raw_input, return_value='exit'):
            cli.execute(interactive=True)
            self.assertTrue(_process.called)

    @patch('__builtin__.raw_input')
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
            ParsingException, CommandException, TimeoutError, Exception,
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

            with patch(self.__raw_input, return_value='test "string with spaces" --flag "value"'):
                self.assertEqual(cli._read_arguments(interactive=True), expected)

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
                def static_ignored_method():
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
                    for choice, subparser in action.choices.items():
                        result[choice] = subparser
                return result

            cli_actions = actions(cli.parser)
            cli_choices = choices(cli_actions)

            self.assertEqual(len(cli_choices), 2)
            self.assertIn('mock', cli_choices.keys())
            self.assertIn('outer', cli_choices.keys())

            mock_actions = actions(cli_choices['mock'])
            mock_choices = choices(mock_actions)
            expected_choices = ['arg_method', 'method_2', 'mock_help', 'id_method', 'outer_2', 'renamed_method']

            self.assertEqual(len(mock_choices), len(expected_choices))
            self.assertTrue(all([c in mock_choices.keys() for c in expected_choices]))

            self.assertTrue(any([a.option_strings == ['--test-flag', '-tf'] and
                                 isinstance(a, argparse._StoreTrueAction)
                                 for a in mock_choices['arg_method']._actions]))

            string_actions = mock_choices['arg_method']._option_string_actions
            self.assertIn('--test-flag', string_actions)
            self.assertIn('-tf', string_actions)

            self.assertTrue(any([a.dest == 'some_id' and
                                 a.help == 'Object id' and
                                 isinstance(a, argparse._StoreAction)
                                 for a in mock_choices['id_method']._positionals._actions]))

    def test_cli_formatter(self):
        """ Test for setting and getting formatter """
        from golem.interface.formatters import CommandFormatter, CommandJSONFormatter
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
