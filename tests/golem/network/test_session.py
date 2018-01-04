import unittest
import unittest.mock as mock

import golem_messages
from golem_messages import message
import semantic_version

from golem.network.transport.session import BasicSession


gm_version = semantic_version.Version(golem_messages.__version__)


class BasicSessionTestCase(unittest.TestCase):
    def setUp(self):
        self.instance = BasicSession(mock.MagicMock())

    @mock.patch('golem.network.transport.session.BasicSession.dropped')
    def test_golem_messages_version_higher_minor(self, dropped_mock):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = str(gm_version.next_minor())
        self.instance.interpret(msg)
        dropped_mock.assert_called_once_with()

    @mock.patch('golem.network.transport.session.BasicSession.dropped')
    def test_golem_messages_version_higher_patch(self, dropped_mock):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = str(gm_version.next_patch())
        self.instance.interpret(msg)
        dropped_mock.assert_not_called()

    @mock.patch('golem.network.transport.session.BasicSession.dropped')
    def test_golem_messages_version_equal(self, dropped_mock):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = str(gm_version)
        self.instance.interpret(msg)
        dropped_mock.assert_not_called()

    @mock.patch('golem.network.transport.session.BasicSession.dropped')
    def test_golem_messages_version_lower_patch(self, dropped_mock):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = '1.1.2'
        with mock.patch.object(golem_messages, '__version__', new='1.1.1'):
            self.instance.interpret(msg)
        dropped_mock.assert_not_called()

    @mock.patch('golem.network.transport.session.BasicSession.dropped')
    def test_golem_messages_version_lower_minor(self, dropped_mock):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = '1.0.9'
        with mock.patch.object(golem_messages, '__version__', new='1.1.1'):
            self.instance.interpret(msg)
        dropped_mock.assert_called_once_with()

    @mock.patch('golem.network.transport.session.BasicSession.dropped')
    def test_golem_messages_version_None(self, dropped_mock):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = None
        self.instance.interpret(msg)
        dropped_mock.assert_called_once_with()

    @mock.patch('golem.network.transport.session.BasicSession.dropped')
    def test_golem_messages_version_invalid(self, dropped_mock):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = ('Czy to bajka, czy nie bajka,'
                                      'Myślcie sobie, jak tam chcecie.')
        self.instance.interpret(msg)
        dropped_mock.assert_called_once_with()
