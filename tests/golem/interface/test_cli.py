import unittest
from contextlib import contextmanager
from io import StringIO

from mock import patch, Mock
from twisted.internet.defer import Deferred, TimeoutError

from golem.interface.cli import CLI
from golem.interface.command import group, doc, argument, identifier, name, command, CommandStorage, \
    CommandHelper
from golem.interface.exceptions import InterruptException, ParsingException, CommandException


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
            if name.startswith('_') or name in ['return_value']:
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

    @patch('sys.stdout', new_callable=StringIO)
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
            assert not _out.getvalue()

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
    def test_process_errors(self, *_):

        exceptions = [
            [InterruptException, False],
            [ParsingException, True],
            [CommandException, True],
            [TimeoutError, True],
            [Exception, True],
        ]

        @group("commands", help="command group")
        class MockClass(object):
            exc_class = None

            @doc("Some help")
            def command(self):
                raise self.exc_class()

        client = self.MockClient()
        cli = CLI(client=client)

        for exc_class, assert_stderr in exceptions:
            with _cmd_storage_context():

                MockClass.exc_class = exc_class
                result, _ = cli.process(['commands', 'command'])

                if assert_stderr:
                    assert result
                else:
                    assert result.startswith('Completed')

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

