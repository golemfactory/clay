# pylint: disable=protected-access, no-self-use
import datetime
import logging
import time
from unittest import mock, TestCase
import urllib

from freezegun import freeze_time
from golem_messages import message
import golem_messages.cryptography
import golem_messages.exceptions
import requests
from requests.exceptions import RequestException

from golem import testutils
from golem.core import keysauth
from golem.core import variables
from golem.network.concent import client
from golem.network.concent import constants
from golem.network.concent import exceptions

logger = logging.getLogger(__name__)


@mock.patch('requests.post')
class TestSendToConcent(TestCase):
    def setUp(self):
        self.msg = message.ForceReportComputedTask()
        self.msg.task_to_compute = message.TaskToCompute()
        node_keys = golem_messages.cryptography.ECCx(None)
        self.private_key = node_keys.raw_privkey
        self.public_key = node_keys.raw_pubkey

    def test_message(self, post_mock):
        response = requests.Response()
        response.status_code = 200
        post_mock.return_value = response

        client.send_to_concent(
            msg=self.msg,
            signing_key=self.private_key,
            public_key=self.public_key,
        )
        api_send_url = urllib.parse.urljoin(
            variables.CONCENT_URL,
            '/api/v1/send/'
        )
        post_mock.assert_called_once_with(
            api_send_url,
            data=mock.ANY,
            headers=mock.ANY
        )

    def test_none(self, post_mock):
        response = requests.Response()
        response.status_code = 200
        post_mock.return_value = response

        client.send_to_concent(
            msg=None,
            signing_key=self.private_key,
            public_key=self.public_key,
        )
        api_send_url = urllib.parse.urljoin(
            variables.CONCENT_URL,
            '/api/v1/send/'
        )
        post_mock.assert_called_once_with(
            api_send_url,
            data=b'',
            headers=mock.ANY
        )

    def test_message_client_error(self, post_mock):
        response = requests.Response()
        response.status_code = 400
        post_mock.return_value = response

        with self.assertRaises(exceptions.ConcentRequestException):
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                public_key=self.public_key,
            )

        self.assertEqual(post_mock.call_count, 1)

    def test_message_server_error(self, post_mock):
        response = requests.Response()
        response.status_code = 500
        post_mock.return_value = response

        with self.assertRaises(exceptions.ConcentServiceException):
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                public_key=self.public_key,
            )

        self.assertEqual(post_mock.call_count, 1)

    def test_message_exception(self, post_mock):
        post_mock.side_effect = RequestException
        with self.assertRaises(exceptions.ConcentUnavailableException):
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                public_key=self.public_key,
            )

        self.assertEqual(post_mock.call_count, 1)


@mock.patch('twisted.internet.reactor', create=True)
@mock.patch('golem.network.concent.client.send_to_concent')
class TestConcentClientService(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        keys_auth = keysauth.EllipticalKeysAuth(datadir=self.path)
        self.concent_service = client.ConcentClientService(
            keys_auth=keys_auth,
            enabled=True,
        )
        self.msg = message.ForceReportComputedTask()

    def tarDown(self):
        self.assertFalse(self.concent_service.isAlive())

    @mock.patch('golem.network.concent.client.ConcentClientService._loop')
    def test_start_stop(self, loop_mock, *_):
        self.concent_service.start()
        time.sleep(.5)
        self.concent_service.stop()
        self.concent_service.join(timeout=3)

        loop_mock.assert_called_once_with()

    def test_submit(self, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=0
        )

        assert 'key' not in self.concent_service._delayed

        assert not self.concent_service.cancel('key')

        assert 'key' not in self.concent_service._delayed

    def test_delayed_submit(self, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=datetime.timedelta(seconds=60)
        )

        assert 'key' in self.concent_service._delayed

        assert self.concent_service.cancel('key')

        assert 'key' not in self.concent_service._delayed

    def test_loop_exception(self, send_mock, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=0
        )

        send_mock.side_effect = exceptions.ConcentRequestException
        mock_path = ("golem.network.concent.client.ConcentClientService"
                     "._grace_sleep")
        with mock.patch(mock_path) as sleep_mock:
            self.concent_service._loop()
            sleep_mock.assert_called_once_with()
        send_mock.assert_called_once_with(
            self.msg,
            self.concent_service.keys_auth._private_key,
            self.concent_service.keys_auth.public_key,
        )

        assert not self.concent_service._delayed

    def test_loop_request_timeout(self, send_mock, *_):
        self.assertFalse(self.concent_service.isAlive())
        delta = constants.MSG_LIFETIMES.get(
            self.msg.__class__,
            constants.DEFAULT_MSG_LIFETIME,
        )
        with freeze_time(datetime.datetime.now()) as frozen_time:
            self.concent_service.submit(
                'key',
                self.msg,
                delay=0
            )

            self.assertEqual(send_mock.call_count, 0)
            frozen_time.tick(delta=delta)
            frozen_time.tick()  # on second more
            self.concent_service._loop()
            self.assertEqual(send_mock.call_count, 0)

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_loop(self, react_mock, send_mock, *_):
        data = object()
        send_mock.return_value = data
        self.concent_service.submit(
            'key',
            self.msg,
            delay=0
        )

        self.concent_service._loop()
        send_mock.assert_called_once_with(
            self.msg,
            self.concent_service.keys_auth._private_key,
            self.concent_service.keys_auth.public_key,
        )
        react_mock.assert_called_once_with(data)

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_ping(self, react_mock, send_mock, *_):
        data = object()
        constants.PING_TIMEOUT = 0
        send_mock.return_value = data
        self.assertTrue(self.concent_service._queue.empty())
        self.concent_service._loop()
        send_mock.assert_called_once_with(
            None,
            self.concent_service.keys_auth._private_key,
            self.concent_service.keys_auth.public_key,
        )
        react_mock.assert_called_once_with(data)

    def test_react_to_concent_message_none(self, *_):
        result = self.concent_service.react_to_concent_message(None)
        self.assertIsNone(result)

    @mock.patch(
        'golem_messages.load',
        side_effect=golem_messages.exceptions.MessageError,
    )
    def test_react_to_concent_message_error(self, load_mock, *_):
        self.concent_service.received_messages.put = mock.Mock()
        data = object()
        result = self.concent_service.react_to_concent_message(data)
        self.assertIsNone(result)
        self.assertEqual(
            self.concent_service.received_messages.put.call_count,
            0,
        )
        load_mock.assert_called_once_with(
            data,
            self.concent_service.keys_auth._private_key,
            variables.CONCENT_PUBKEY,
        )

    @mock.patch('golem_messages.load')
    def test_react_to_concent_message(self, load_mock, *_):
        self.concent_service.received_messages.put = mock.Mock()
        data = object()
        load_mock.return_value = msg = mock.Mock()
        result = self.concent_service.react_to_concent_message(data)
        self.assertIsNone(result)
        self.concent_service.received_messages.put.assert_called_once_with(msg)
        load_mock.assert_called_once_with(
            data,
            self.concent_service.keys_auth._private_key,
            variables.CONCENT_PUBKEY,
        )


class ConcentCallLaterTestCase(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        self.concent_service = client.ConcentClientService(
            keys_auth=keysauth.EllipticalKeysAuth(datadir=self.path),
            enabled=True,
        )
        self.msg = message.ForceReportComputedTask()

    def test_submit(self):
        # Shouldn't fail
        self.concent_service.submit(
            'key',
            self.msg,
            datetime.timedelta(seconds=1)
        )
