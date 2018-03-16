# pylint: disable=protected-access, no-self-use
import datetime
import logging
import time
from unittest import mock, TestCase
import urllib
import requests
from requests.exceptions import RequestException
from freezegun import freeze_time

import golem_messages
import golem_messages.cryptography
import golem_messages.exceptions
from golem_messages import message
from golem_messages.constants import (
    DEFAULT_MSG_LIFETIME, MSG_LIFETIMES
)

from golem import testutils
from golem.core import keysauth
from golem.core import variables
from golem.network.concent import client
from golem.network.concent import exceptions

from tests.factories import messages as msg_factories

logger = logging.getLogger(__name__)


class TestVerifyResponse(TestCase):
    def setUp(self):
        self.response = requests.Response()
        self.response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__

    def test_message_client_error(self):
        self.response.status_code = 400
        with self.assertRaises(exceptions.ConcentRequestError):
            client.verify_response(self.response)

    def test_message_server_error(self):
        self.response.status_code = 500
        with self.assertRaises(exceptions.ConcentServiceError):
            client.verify_response(self.response)

    def test_version_mismatch(self):
        self.response.headers['Concent-Golem-Messages-Version'] = 'dummy'
        with self.assertRaises(exceptions.ConcentVersionMismatchError):
            client.verify_response(self.response)


@mock.patch('requests.post')
class TestSendToConcent(TestCase):
    def setUp(self):
        self.msg = msg_factories.ForceReportComputedTask()
        node_keys = golem_messages.cryptography.ECCx(None)
        self.private_key = node_keys.raw_privkey
        self.public_key = node_keys.raw_pubkey

    def test_message(self, post_mock):
        response = requests.Response()
        response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__
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

    def test_request_exception(self, post_mock):
        post_mock.side_effect = RequestException
        with self.assertRaises(exceptions.ConcentUnavailableError):
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                public_key=self.public_key,
            )

        self.assertEqual(post_mock.call_count, 1)

    @mock.patch('golem.network.concent.client.verify_response')
    def test_verify_response(self, verify_mock, post_mock):
        response = requests.Response()
        post_mock.return_value = response
        client.send_to_concent(
            msg=self.msg,
            signing_key=self.private_key,
            public_key=self.public_key,
        )
        verify_mock.assert_called_once_with(response)

    @mock.patch('golem.network.concent.client.verify_response')
    def test_delayed_timestamp(self, *_):
        future = datetime.datetime.utcnow() + datetime.timedelta(days=5)
        # messages use integer timestamps
        future = future.replace(microsecond=0)
        # freezegun requires naive datetime, .timestamp() works only with aware
        future_aware = future.replace(tzinfo=datetime.timezone.utc)
        with freeze_time(future):
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                public_key=self.public_key,
            )
        self.assertEqual(
            self.msg.timestamp,
            future_aware.timestamp(),
        )


@mock.patch('requests.get')
class TestReceiveFromConcent(TestCase):
    def setUp(self):
        self.msg = msg_factories.ForceReportComputedTask()
        node_keys = golem_messages.cryptography.ECCx(None)
        self.private_key = node_keys.raw_privkey
        self.public_key = node_keys.raw_pubkey

    def test_empty_content(self, get_mock):
        response = requests.Response()
        response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__
        response._content = b''
        response.status_code = 200
        get_mock.return_value = response
        result = client.receive_from_concent(
            public_key=self.public_key,
        )
        self.assertIsNone(result)

    def test_content(self, get_mock):
        response = requests.Response()
        response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__
        response._content = content = object()
        response.status_code = 200
        get_mock.return_value = response
        result = client.receive_from_concent(
            public_key=self.public_key,
        )
        self.assertIs(result, content)

    def test_request_exception(self, get_mock):
        get_mock.side_effect = RequestException
        with self.assertRaises(exceptions.ConcentUnavailableError):
            client.receive_from_concent(
                public_key=self.public_key,
            )

        self.assertEqual(get_mock.call_count, 1)

    @mock.patch('golem.network.concent.client.verify_response')
    def test_verify_response(self, verify_mock, get_mock):
        response = requests.Response()
        get_mock.return_value = response
        client.receive_from_concent(
            public_key=self.public_key,
        )
        verify_mock.assert_called_once_with(response)


@mock.patch('twisted.internet.reactor', create=True)
@mock.patch('golem.network.concent.client.receive_from_concent')
@mock.patch('golem.network.concent.client.send_to_concent')
class TestConcentClientService(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        keys_auth = keysauth.KeysAuth(
            datadir=self.path,
            private_key_name='priv_key',
            password='password',
        )
        self.concent_service = client.ConcentClientService(
            keys_auth=keys_auth,
            enabled=True,
        )
        self.msg = message.ForceReportComputedTask()

    def tarDown(self):
        self.assertFalse(self.concent_service.isAlive())

    @mock.patch('golem.network.concent.client.ConcentClientService.receive')
    @mock.patch('golem.network.concent.client.ConcentClientService._loop')
    def test_start_stop(self, loop_mock, receive_mock, *_):
        self.concent_service.start()
        time.sleep(.5)
        self.concent_service.stop()
        self.concent_service.join(timeout=3)

        loop_mock.assert_called_once_with()
        receive_mock.assert_called_once_with()

    def test_submit(self, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=datetime.timedelta(),
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
            delay=datetime.timedelta(),
        )

        send_mock.side_effect = exceptions.ConcentRequestError
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
        delta = MSG_LIFETIMES.get(
            self.msg.__class__,
            DEFAULT_MSG_LIFETIME,
        )
        with freeze_time(datetime.datetime.now()) as frozen_time:
            self.concent_service.submit(
                'key',
                self.msg,
                delay=datetime.timedelta(),
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
            delay=datetime.timedelta(),
        )

        self.concent_service._loop()
        send_mock.assert_called_once_with(
            self.msg,
            self.concent_service.keys_auth._private_key,
            self.concent_service.keys_auth.public_key,
        )
        react_mock.assert_called_once_with(data, response_to=self.msg)

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_receive(self, react_mock, _send_mock, receive_mock, *_):
        receive_mock.return_value = content = object()
        self.concent_service.receive()
        receive_mock.assert_called_once_with(
            self.concent_service.keys_auth.public_key,
        )
        react_mock.assert_called_once_with(content)

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '._grace_sleep'
    )
    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_receive_concent_error(self,
                                   react_mock,
                                   sleep_mock,
                                   _send_mock,
                                   receive_mock,
                                   *_):
        receive_mock.side_effect = exceptions.ConcentError
        self.concent_service.receive()
        receive_mock.assert_called_once_with(mock.ANY)
        sleep_mock.assert_called_once_with()
        react_mock.assert_not_called()

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '._grace_sleep'
    )
    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_receive_exception(self,
                               react_mock,
                               sleep_mock,
                               _send_mock,
                               receive_mock,
                               *_):
        receive_mock.side_effect = Exception
        self.concent_service.receive()
        receive_mock.assert_called_once_with(mock.ANY)
        sleep_mock.assert_called_once_with()
        react_mock.assert_not_called()

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
            keys_auth=keysauth.KeysAuth(
                datadir=self.path,
                private_key_name='priv_key',
                password='password',
            ),
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
