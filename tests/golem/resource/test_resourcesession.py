from golem import testutils
from golem.network.transport import message
from golem.resource import resourcesession
import mock
import time
import unittest

class ResourceSessionTestCase(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/resource/resourcesession.py',]

    def setUp(self):
        self.connection = mock.MagicMock()
        self.instance = resourcesession.ResourceSession(self.connection)

    def test_connection_dropped(self):
        """.dropped() method from BasicSession interface."""
        resource_server = self.connection.server
        with mock.patch('golem.network.transport.session.BasicSafeSession.dropped') as m:
            self.instance.dropped()
            m.assert_called_once_with(self.instance)
            resource_server.remove_session.assert_called_once_with(self.instance)

    def test_encryption(self):
        """.encrypt() method from SafeSession interface."""

        test_data = 'test data: %s' % (time.time(),)

        # without resource_server
        self.instance.resource_server = None
        self.assertEquals(test_data, self.instance.encrypt(test_data))

        # with resource server
        self.instance.resource_server = resource_server = self.connection.server
        self.instance.encrypt(test_data)
        resource_server.encrypt.assert_called_once_with(test_data, self.instance.key_id)

    def test_decryption(self):
        """.decrypt() method from SafeSession interface."""

        test_data = 'test data: %s' % (time.time(),)
        decrypted_test_data = 'dcr test data: %s' % (time.time(),)

        # without resource_server
        self.instance.resource_server = None
        self.assertEquals(test_data, self.instance.decrypt(test_data))

        # with resource server
        self.instance.resource_server = resource_server = self.connection.server
        resource_server.decrypt.return_value = decrypted_test_data

        self.assertEquals(self.instance.decrypt(test_data), decrypted_test_data)

        resource_server.decrypt.side_effect = AssertionError('test')
        self.assertEquals(self.instance.decrypt(test_data), test_data)

        resource_server.decrypt.side_effect = Exception('test')
        with self.assertRaises(Exception):
            self.instance.decrypt(test_data)

    def test_signing(self):
        """.sign() method from SafeSession interface."""
        test_signature = 'test sig: %s' % (time.time(),)
        msg = mock.MagicMock()
        short_hash = object()
        msg.get_short_hash.return_value = short_hash
        self.connection.server.sign.return_value = test_signature
        self.instance.sign(msg)
        self.assertEquals(msg.sig, test_signature)
        msg.get_short_hash.assert_called_once_with()

    def test_sign_verification(self):
        """.verify() method from SafeSession interface."""
        test_signature = 'test sig: %s' % (time.time(),)
        msg = mock.MagicMock()
        msg.sig = test_signature
        short_hash = object()
        msg.get_short_hash.return_value = short_hash
        self.instance.verify(msg)
        self.connection.server.verify_sig.assert_called_once_with(test_signature, short_hash, self.instance.key_id)

    @mock.patch('golem.network.transport.session.BasicSafeSession.send')
    def test_sending(self, super_send_mock):
        """Message sending."""
        # connection unverified
        msg = queued_msg = object()
        self.instance.send(msg)
        self.assertEquals([msg], self.instance.msgs_to_send)
        self.assertEquals(super_send_mock.call_count, 0)

        msg = object()
        self.instance.send(msg, send_unverified=True)
        self.assertNotIn(msg, self.instance.msgs_to_send)
        super_send_mock.assert_called_once_with(self.instance, msg, send_unverified=True)
        super_send_mock.reset_mock()

        # connection verified
        msg = message.MessageRandVal(self.instance.rand_val, "")
        msg.encrypted = True
        self.instance.interpret(msg)
        self.assertTrue(self.instance.verified)
        super_send_mock.assert_called_once_with(self.instance, queued_msg, send_unverified=False)
        super_send_mock.reset_mock()

        msg = object()
        self.instance.send(msg)
        super_send_mock.assert_called_once_with(self.instance, msg, send_unverified=False)

    def test_full_data_received(self):
        """Reaction to full data received."""
        # without confirmation
        self.instance.file_name = file_name = 'dummytest.name'
        self.instance.confirmation = False
        self.instance.dropped = mock.MagicMock()

        self.instance.full_data_received()

        self.instance.resource_server._download_success.assert_called_once_with(
            file_name,
            self.instance.address,
            self.instance.port)
        self.instance.dropped.assert_called_once_with()
        self.assertIsNone(self.instance.file_name)

        # with confirmation, without copies
        def confirmation_without_copies():
            self.instance.file_name = file_name = 'dummytest.name'
            self.instance.confirmation = True
            self.instance.send = mock.MagicMock()

            self.instance.full_data_received()

            self.instance.send.assert_called_once_with(mock.ANY)
            mock_args, mock_kwargs = self.instance.send.call_args
            msg = mock_args[0]
            self.assertIsInstance(msg, message.MessageHasResource)
            self.assertEquals(msg.resource, file_name)
            self.assertFalse(self.instance.confirmation)
            self.assertEquals(self.instance.copies, 0)
            self.assertIsNone(self.instance.file_name)
            return file_name
        confirmation_without_copies()

        # wtih confirmation, with copies
        self.instance.copies = copies = 10
        file_name = confirmation_without_copies()
        self.instance.resource_server.add_resource_to_send.assert_called_once_with(file_name, copies)

    def test_send_pass_throughs(self):
        """Simple pass-through methods."""
        self.instance.send = mock.MagicMock()

        # .send_pull_resource()
        resource = object()
        self.instance.send_pull_resource(resource)
        self.instance.send.assert_called_once_with(mock.ANY)
        mock_args, mock_kwargs = self.instance.send.call_args
        msg = mock_args[0]
        self.assertIsInstance(msg, message.MessagePullResource)
        self.assertEquals(msg.resource, resource)
        self.instance.send.reset_mock()

        # .send_hello()
        resource = object()
        client_key_id = object()
        self.instance.resource_server.get_key_id = mock.MagicMock(return_value=client_key_id)

        self.instance.send_hello()

        self.instance.send.assert_called_once_with(mock.ANY, send_unverified=True)
        mock_args, mock_kwargs = self.instance.send.call_args
        msg = mock_args[0]

        expected = {
            u'CHALLENGE': None,
            u'CLIENT_KEY_ID': client_key_id,
            u'CLI_VER': 0,
            u'DIFFICULTY': 0,
            u'METADATA': None,
            u'NODE_INFO': None,
            u'NODE_NAME': None,
            u'PORT': 0,
            u'PROTO_ID': 0,
            u'RAND_VAL': self.instance.rand_val,
            u'SOLVE_CHALLENGE': False,
        }

        self.assertEquals(msg.dict_repr(), expected)
