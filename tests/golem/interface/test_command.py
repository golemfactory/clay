import unittest

import pytest
from mock import patch
from twisted.internet.defer import Deferred, TimeoutError

from golem.core.deferred import sync_wait
from golem.interface.command import Argument, CommandResult, CommandHelper, \
    group, doc, command, CommandStorage, storage_context, CommandException, \
    ask_for_confirmation, format_with_call_arg
from golem.interface.exceptions import CommandCanceledException


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

            self.assertEqual(CommandStorage.roots,
                             [MockPreClass, MockClass, command_root])

            pre_class_children = CommandHelper.get_children(MockPreClass)
            pre_class_keys = sorted(pre_class_children.keys())

            class_children = CommandHelper.get_children(MockClass)
            class_keys = sorted(list(class_children.keys()))

            post_class_children = CommandHelper.get_children(MockSubClass)
            post_class_keys = sorted(list(post_class_children.keys()))

            for k in ['mock_2_renamed']:
                assert k in pre_class_keys
            for k in ['sub_commands', 'mock_1', 'renamed_mc']:
                assert k in class_keys
            for k in ['command_msc', 'command']:
                assert k in post_class_keys

        with self.assertRaises(TypeError):
            @group("commands", help="command group")
            def foo():
                pass


class TestAskForConfirmation:

    @pytest.fixture(autouse=True)
    def setUp(self):
        self.question = "Do you really what to now the truth?"
        self.output = "Earth's not flat"

    @pytest.mark.parametrize(
        'users_answer', ['', 'y', 'Y']
    )
    def test_confirmation(self, users_answer):

        @ask_for_confirmation(self.question)
        def _foo():
            return self.output

        with patch('builtins.input', return_value=users_answer) as mocked_input:
            assert _foo() == self.output
            mocked_input.assert_called_once_with(self.question + ' (Y/n)')

    @pytest.mark.parametrize(
        'users_answer', ['n', 'N']
    )
    def test_cancellation(self, users_answer):

        @ask_for_confirmation(self.question)
        def _bar():
            pass

        with patch('builtins.input', return_value=users_answer) as mocked_input:
            with pytest.raises(CommandCanceledException):
                _bar()
            mocked_input.assert_called_once_with(self.question + ' (Y/n)')

    def test_users_enters_invalid_answer(self):

        @ask_for_confirmation(self.question)
        def _baz():
            return self.output

        with patch('builtins.input',
                   side_effect=['a', 'no', 'yes', 'y']) as mocked_input:
            assert _baz() == self.output
            mocked_input.call_count = 3

    def test_customized_question(self):
        uid = 777
        question = "Do you want to delete user with id: {}?"

        @ask_for_confirmation(question,
                              parameters=['user_id'])
        def fun(user_id):
            return user_id + 1

        with patch('builtins.input', return_value='y') as mocked_input:
            assert fun(uid) == uid + 1  # sanity check
            mocked_input.assert_called_once_with(
                question.format(uid) + ' (Y/n)'
            )


class TestFormatWithCallArg:
    def test_that_question_is_unchanged_if_parameter_is_none(self):
        def _foo(_uid):
            pass
        question = 'Do you want do delete user: {}?'
        result = format_with_call_arg(question, None, _foo)
        assert result == question

    def test_that_question_is_changed_if_parameter_is_in_call_args(self):
        def _foo(_uid):
            pass

        question = 'Do you want do delete user: {}?'
        actual_parameter = 1
        result = format_with_call_arg(question, ['_uid'], _foo,
                                      actual_parameter)
        assert result == question.format(actual_parameter)

    def test_that_question_is_changed_if_parameter_is_in_call_kwargs(self):
        def _foo(_uid):
            pass
        question = 'Do you want do delete user: {}?'
        value = 1
        result = format_with_call_arg(question, ['_uid'], _foo, uid=value)
        assert result == question.format(value)
