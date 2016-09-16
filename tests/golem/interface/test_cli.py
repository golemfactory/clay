import unittest
from contextlib import contextmanager
from io import StringIO

from mock import patch, Mock, mock
from twisted.internet.defer import Deferred, TimeoutError
from twisted.internet.error import ReactorNotRunning

from golem.interface.cli import CLI, _exit, _help, _debug, ArgumentParser
from golem.interface.command import group, doc, argument, identifier, name, command, CommandStorage, \
    CommandHelper
from golem.interface.exceptions import ParsingException, CommandException


def _nop(*a, **kw):
    pass


def _raise(*a, **kw):
    raise Exception()


def _raise_sys_exit(*a, **kw):
    raise SystemExit()


@contextmanager
def _cmd_storage_context():
    roots = CommandStorage.roots
    CommandStorage.roots = []
    yield
    CommandStorage.roots = roots


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
    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.interface.cli.CLI.process', side_effect=lambda x: (u' '.join(x), Mock()))
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_execute(self, _, _process, _exit, _out):

        client = self.MockClient()
        cli = CLI(client=client, formatters=[self.MockFormatter()])

        with patch(self.__raw_input, return_value=''):
            cli.execute()

        assert not _process.called
        assert not _out.getvalue()
        assert _exit.called

        _process.called = False
        _exit.called = False

        with patch(self.__raw_input, return_value='invalid_command --invalid-flag'):
            cli.execute()

        assert _process.called
        assert _exit.called

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

            assert _process.called
            assert not _exit.called
            assert not _out.getvalue()

    @patch('sys.stdout', new_callable=MockStdout)
    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.interface.cli.CLI.process', side_effect=_raise_sys_exit)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_execute_exit(self, _, _process, _exit, _out):

        client = self.MockClient()
        cli = CLI(client=client)

        with patch(self.__raw_input, return_value='invalid_command --invalid-flag'):
            cli.execute()
            assert _process.called
            assert not _exit.called
            assert not _out.data

    @patch('__builtin__.raw_input')
    @patch('golem.interface.cli._exit', side_effect=_nop)
    def test_execute_interactive(self, _exit, _ri):

        with _cmd_storage_context():

            @group("commands")
            class MockClass(object):
                def command(self):
                    pass

                def exit(self):
                    raise SystemExit()

            client = self.MockClient()
            cli = CLI(client=client)

            cli.execute(['commands', 'exit'], interactive=True)
            assert not _exit.called

    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_process(self, *_):

        with _cmd_storage_context():

            @group("commands")
            class MockClass(object):
                def command(self):
                    pass

            client = self.MockClient()
            cli = CLI(client=client)

            with patch('sys.stderr', new_callable=StringIO) as err:
                cli.process(['commands', 'command'])
                assert not err.getvalue()

    @patch('golem.interface.cli._exit', side_effect=_nop)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_process_errors(self, config_logging, cli_exit):

        exceptions = [
            ParsingException, CommandException, TimeoutError, Exception,
        ]

        with _cmd_storage_context():

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
                    assert out.data

    def test_build(self):

        with _cmd_storage_context():

            @group("mock")
            class MockClass(object):

                @doc("Command help")
                def help_method(self):
                    pass

                @argument("--test-flag", "--tf", optional=True)
                def arg_method(self, test_flag):
                    pass

                @identifier("some_id")
                def id_method(self, some_id):
                    pass

                @name("renamed_method")
                def this_is_not_the_name_of_method(self):
                    pass

                def auto_picked_up_method(self):
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

            assert cli.roots
            assert len(cli.roots) == 2

            cls_interface = CommandHelper.get_interface(MockClass)
            cls_instance = CommandHelper.get_instance(MockClass)

            assert cls_interface
            assert cls_instance

            cls_children = CommandHelper.get_children(MockClass)

            assert cls_children is cls_interface['children']
            assert cls_children
            assert len(cls_children) == 5

            cli.build()

            assert cli.shared_parser
            assert cli.parser
            assert cli.subparsers
            assert cli.parser._subparsers
            # help, json, subparsers
            assert len(cli.parser._subparsers._actions) == 3


class TestCLICommands(unittest.TestCase):

    @patch('logging.error')
    @patch('sys.exit')
    @patch('twisted.internet.reactor', create=True, new_callable=MockReactor)
    def test_exit(self, reactor, sys_exit, logging_error):

        assert CommandHelper.get_interface(_exit)

        _exit()
        assert not sys_exit.called
        assert not logging_error.called

        reactor.exc_class = Exception

        _exit()
        assert not sys_exit.called
        assert logging_error.called

        reactor.running = False
        logging_error.called = False

        _exit()
        assert sys_exit.called
        assert not logging_error.called

        sys_exit.called = False

        _exit(raise_exit=False)
        assert not sys_exit.called
        assert not logging_error.called

    def test_help(self):
        assert CommandHelper.get_interface(_help)

        with self.assertRaises(ParsingException):
            _help()

    @patch('sys.stdout', new_callable=MockStdout)
    def test_debug(self, out):
        assert CommandHelper.get_interface(_debug)

        _debug()

        assert out.getvalue()


class TestArgumentParser(unittest.TestCase):

    def test_error(self):

        ap = ArgumentParser()

        try:
            raise Exception("test")
        except Exception as _:
            with self.assertRaises(ParsingException) as exc:
                ap.error("custom")
                assert exc.exception.message != "custom"
                assert isinstance(exc.exception.message, ParsingException)

        with self.assertRaises(ParsingException) as exc:
            ap.error("custom")
            assert exc.exception.message == "custom"

    def test_exit(self):

        ap = ArgumentParser()

        try:
            ap.exit()
        except BaseException:
            self.fail("No exception should be thrown")


