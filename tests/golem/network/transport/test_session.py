import unittest
import unittest.mock as mock

import golem_messages
from golem_messages import message
import semantic_version

from golem.network.transport import session


gm_version = semantic_version.Version(golem_messages.__version__)


class GolemMessagesVersionTestCase(unittest.TestCase):
    def test_golem_messages_version_higher_minor(self):
        with self.assertRaises(session.IncompatibleGolemMessages):
            session.check_golem_messages_version_compatible(
                str(gm_version.next_minor()),
            )

    def test_golem_messages_version_higher_patch(self):
        # Shouldn't raise
        session.check_golem_messages_version_compatible(
            str(gm_version.next_patch()),
        )

    def test_golem_messages_version_equal(self):
        # Shouldn't raise
        session.check_golem_messages_version_compatible(
            str(gm_version),
        )

    def test_golem_messages_version_lower_patch(self):
        # Shouldn't raise
        with mock.patch.object(golem_messages, '__version__', new='1.1.1'):
            session.check_golem_messages_version_compatible(
                '1.1.2',
            )

    def test_golem_messages_version_lower_minor(self):
        with self.assertRaises(session.IncompatibleGolemMessages):
            with mock.patch.object(golem_messages, '__version__', new='1.1.1'):
                session.check_golem_messages_version_compatible(
                    '1.0.9',
                )

    def test_golem_messages_version_None(self):
        with self.assertRaises(session.IncompatibleGolemMessages):
            with mock.patch.object(golem_messages, '__version__', new='1.1.1'):
                session.check_golem_messages_version_compatible(
                    None,
                )

    def test_golem_messages_version_invalid(self):
        with self.assertRaises(session.IncompatibleGolemMessages):
            with mock.patch.object(golem_messages, '__version__', new='1.1.1'):
                session.check_golem_messages_version_compatible(
                    ('Czy to bajka, czy nie bajka,'
                     'Myślcie sobie, jak tam chcecie.'),
                )


class BasicSessionTestCase(unittest.TestCase):
    def setUp(self):
        self.instance = session.BasicSession(mock.MagicMock())

    def hello(self, version=str(gm_version)):
        msg = message.Hello(
            **dict((key, None) for key in message.Hello.__slots__),
        )
        msg.golem_messages_version = version
        self.instance.interpret(msg)

    @mock.patch('golem.network.transport.session.BasicSession.disconnect')
    @mock.patch('golem.network.transport.session.check_golem_messages_version_compatible')  # noqa
    def test_golem_messages_ok(self, check_mock, disconnect_mock):
        version = object()
        self.hello(version)
        check_mock.assert_called_once_with(version)
        disconnect_mock.assert_not_called()

    @mock.patch('golem.network.transport.session.BasicSession.disconnect')
    @mock.patch('golem.network.transport.session.check_golem_messages_version_compatible',  # noqa
                side_effect=session.IncompatibleGolemMessages)
    def test_golem_messages_failed(self, check_mock, disconnect_mock):
        self.hello()
        disconnect_mock.assert_called_once_with(
            message.Disconnect.REASON.BadProtocol,
        )
