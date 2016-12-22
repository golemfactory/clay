import unittest

from mock import Mock
from twisted.internet.defer import Deferred, TimeoutError

from golem.interface.command import Argument, CommandResult, CommandHelper, group, doc, command, client_ctx, \
    CommandStorage, storage_context, CommandException


class TestArgument(unittest.TestCase):

    def test_simplify_flag(self):

        argument = Argument('--flag', optional=True)
        simplified = argument.simplify()
        kw = simplified.kwargs

        assert 'default' not in kw
        assert 'nargs' not in kw
        assert kw['action'] == 'store_true'

    def test_simply_arg(self):

        argument = Argument('arg', optional=True)
        simplified = argument.simplify()
        kw = simplified.kwargs

        assert 'default' in kw
        assert kw['nargs'] == '?'
        assert kw['default'] is None
        assert kw['action'] == 'store'

    def test_extend(self):

        argument = Argument('arg', optional=True)
        extended = Argument.extend(argument, 'narg', optional=False, default=7)

        assert len(extended.args) == 2
        assert len(extended.kwargs) == 2

        assert extended.kwargs['optional'] is False
        assert extended.kwargs['default'] == 7


class TestCommandResult(unittest.TestCase):

    def test_command_result(self):

        for data in ['result', '']:
            result = CommandResult(data)
            assert result.type is CommandResult.PLAIN
            with self.assertRaises(TypeError):
                result.from_tabular()

        result = CommandResult()
        assert result.type is CommandResult.NONE
        with self.assertRaises(TypeError):
            result.from_tabular()

        with self.assertRaises(CommandException):
            CommandResult(error=1)

    def test_tabular(self):

        headers = ['1', '2', '3']
        values = [
            ['d', 'b', 'f'],
            ['a', 'e', 'c'],
        ]

        tabular = CommandResult.to_tabular(headers, values)

        assert tabular.data == (headers, values)
        assert tabular.type == CommandResult.TABULAR
        assert tabular.from_tabular() == (headers, values)

        tabular = CommandResult.to_tabular(headers, values, sort='4')

        assert tabular.from_tabular()[1] == values

        tabular = CommandResult.to_tabular(headers, values, sort='1')

        assert tabular.from_tabular()[1] != values
        assert tabular.from_tabular()[1] == [
            ['a', 'e', 'c'],
            ['d', 'b', 'f'],
        ]

        tabular = CommandResult.to_tabular(headers, values, sort='2')

        assert tabular.from_tabular()[1] == values

        tabular = CommandResult.to_tabular(headers, values, sort='3')

        assert tabular.from_tabular()[1] != values
        assert tabular.from_tabular()[1] == [
            ['a', 'e', 'c'],
            ['d', 'b', 'f'],
        ]

        CommandResult.type = CommandResult.NONE
        with self.assertRaises(TypeError):
            CommandResult.from_tabular()
        CommandResult.type = CommandResult.TABULAR


class TestCommandHelper(unittest.TestCase):

    def test_wait_for_deferred(self):

        assert CommandHelper.wait_for('1234') == '1234'

        deferred = Deferred()
        deferred.result = '5678'
        deferred.called = True

        assert CommandHelper.wait_for(deferred) == '5678'

        with self.assertRaises(TimeoutError):
            deferred_2 = Deferred()
            CommandHelper.wait_for(deferred_2, timeout=0)

    def test_structure(self):

        with storage_context():

            @group("pre_commands")
            class MockPreClass(object):
                pass

            @group("commands", help="command group")
            class MockClass(object):
                property = None

                def __init__(self):
                    pass

                @doc("Some help")
                def mock_1(self):
                    pass

                @command(name='mock_2_renamed', parent=MockPreClass)
                def mock_2(self):
                    pass

            @group("sub_commands", parent=MockClass)
            class MockSubClass(object):
                def command(self):
                    pass

            @command(name='renamed_mc', parent=MockClass)
            def command_mc():
                pass

            @command(parent=MockSubClass)
            def command_msc():
                pass

            @command(root=True)
            def command_root():
                pass

            assert CommandStorage.roots == [MockPreClass, MockClass, command_root]
            assert CommandHelper.get_children(MockPreClass).keys() == ['mock_2_renamed']
            assert CommandHelper.get_children(MockClass).keys() == ['sub_commands', 'mock_1', 'renamed_mc']
            assert CommandHelper.get_children(MockSubClass).keys() == ['command_msc', 'command']



