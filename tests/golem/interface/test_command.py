import unittest

from twisted.internet.defer import Deferred, TimeoutError

from golem.core.deferred import sync_wait
from golem.interface.command import Argument, CommandResult, CommandHelper, \
    group, doc, command, CommandStorage, storage_context, CommandException


class TestArgument(unittest.TestCase):

    def test_simplify_flag(self):

        argument = Argument('--flag', optional=True)
        simplified = argument.simplify()
        kw = simplified.kwargs

        self.assertNotIn('default', kw)
        self.assertNotIn('nargs', kw)
        self.assertEqual(kw['action'], 'store_true')

    def test_simply_arg(self):

        argument = Argument('arg', optional=True)
        simplified = argument.simplify()
        kw = simplified.kwargs

        self.assertIn('default', kw)
        self.assertEqual(kw['nargs'], '?')
        self.assertIsNone(kw['default'])
        self.assertEqual(kw['action'], 'store')

    def test_extend(self):

        argument = Argument('arg', optional=True)
        extended = Argument.extend(argument, 'narg', optional=False, default=7)

        self.assertEqual(len(extended.args), 2)
        self.assertEqual(len(extended.kwargs), 2)

        self.assertFalse(extended.kwargs['optional'])
        self.assertEqual(extended.kwargs['default'], 7)


class TestCommandResult(unittest.TestCase):

    def test_command_result(self):

        for data in ['result', '']:
            result = CommandResult(data)
            self.assertIs(result.type, CommandResult.PLAIN)
            with self.assertRaises(TypeError):
                result.from_tabular()

        result = CommandResult()
        self.assertIs(result.type, CommandResult.NONE)
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

        self.assertEqual(tabular.data, (headers, values))
        self.assertEqual(tabular.type, CommandResult.TABULAR)
        self.assertEqual(tabular.from_tabular(), (headers, values))

        tabular = CommandResult.to_tabular(headers, values, sort='4')

        self.assertEqual(tabular.from_tabular()[1], values)

        tabular = CommandResult.to_tabular(headers, values, sort='1')

        self.assertNotEqual(tabular.from_tabular()[1], values)
        self.assertEqual(tabular.from_tabular()[1], [
            ['a', 'e', 'c'],
            ['d', 'b', 'f'],
        ])

        tabular = CommandResult.to_tabular(headers, values, sort='2')

        self.assertEqual(tabular.from_tabular()[1], values)

        tabular = CommandResult.to_tabular(headers, values, sort='3')

        self.assertNotEqual(tabular.from_tabular()[1], values)
        self.assertEqual(tabular.from_tabular()[1], [
            ['a', 'e', 'c'],
            ['d', 'b', 'f'],
        ])

        CommandResult.type = CommandResult.NONE
        with self.assertRaises(TypeError):
            CommandResult.from_tabular()
        CommandResult.type = CommandResult.TABULAR


class TestCommandHelper(unittest.TestCase):

    def test_wait_for_deferred(self):

        self.assertEqual(sync_wait('1234'), '1234')

        deferred = Deferred()
        deferred.result = '5678'
        deferred.called = True

        self.assertEqual(sync_wait(deferred), '5678')

        with self.assertRaises(TimeoutError):
            deferred_2 = Deferred()
            sync_wait(deferred_2, timeout=0)

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

            self.assertEqual(CommandStorage.roots, [MockPreClass, MockClass,
                                                    command_root])
            self.assertEqual(CommandHelper.get_children(MockPreClass).keys(),
                             ['mock_2_renamed'])
            self.assertEqual(CommandHelper.get_children(MockClass).keys(),
                             ['sub_commands', 'mock_1', 'renamed_mc'])
            self.assertEqual(CommandHelper.get_children(MockSubClass).keys(),
                             ['command_msc', 'command'])

        with self.assertRaises(TypeError):
            @group("commands", help="command group")
            def foo():
                pass
