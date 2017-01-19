from golem.resource import resourcesession
import mock
import time
import unittest

class ResourceSessionTestCase(unittest.TestCase):
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
        test_signature = 'test sig: %s' % (time.time(),)
        msg = mock.MagicMock()
        msg.sig = test_signature
        short_hash = object()
        msg.get_short_hash.return_value = short_hash
        self.instance.verify(msg)
        self.connection.server.verify_sig.assert_called_once_with(test_signature, short_hash, self.instance.key_id)

    @mock.patch('golem.network.transport.session.BasicSafeSession.send')
    def test_sending(self, super_send_mock):
        # connection unverified
        msg = object()
        self.instance.send(msg)
        self.assertEquals([msg], self.instance.msgs_to_send)
        self.assertEquals(super_send_mock.call_count, 0)

        # connection verified
