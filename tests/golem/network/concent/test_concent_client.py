import datetime
import logging
import time
from unittest import mock, TestCase
import urllib

from freezegun import freeze_time
from golem_messages import message
import golem_messages.cryptography
import requests
from requests.exceptions import RequestException

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
        self.key = node_keys.raw_privkey

    def test_message(self, post_mock):
        response = requests.Response()
        response.status_code = 200
        post_mock.return_value = response

        client.send_to_concent(msg=self.msg, signing_key=self.key)
        api_send_url = urllib.parse.urljoin(
            variables.CONCENT_URL,
            '/api/v1/send/'
        )
        post_mock.assert_called_once_with(
            api_send_url,
            data=mock.ANY,
            headers=mock.ANY
        )

    def test_message_client_error(self, post_mock):
        response = requests.Response()
        response.status_code = 400
        post_mock.return_value = response

        with self.assertRaises(exceptions.ConcentRequestException):
            client.send_to_concent(msg=self.msg, signing_key=self.key)

        post_mock.assert_called_once()

    def test_message_server_error(self, post_mock):
        response = requests.Response()
        response.status_code = 500
        post_mock.return_value = response

        with self.assertRaises(exceptions.ConcentServiceException):
            client.send_to_concent(msg=self.msg, signing_key=self.key)

        post_mock.assert_called_once()

    def test_message_exception(self, post_mock):
        post_mock.side_effect = RequestException
        with self.assertRaises(exceptions.ConcentUnavailableException):
            client.send_to_concent(msg=self.msg, signing_key=self.key)

        post_mock.assert_called_once()


@mock.patch('twisted.internet.reactor', create=True)
@mock.patch('golem.network.concent.client.send_to_concent')
class TestConcentClientService(TestCase):
    def setUp(self):
        client.ConcentClientService.QUEUE_TIMEOUT = 0.1
        node_keys = golem_messages.cryptography.ECCx(None)
        self.concent_service = client.ConcentClientService(
            signing_key=node_keys.raw_privkey,
            enabled=True,
        )
        self.msg = message.ForceReportComputedTask()

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
        assert 'key' in self.concent_service._history

        assert not self.concent_service.cancel('key')
        assert self.concent_service.result('key')

        assert 'key' not in self.concent_service._delayed
        assert 'key' not in self.concent_service._history

    def test_delayed_submit(self, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=60
        )

        assert 'key' in self.concent_service._delayed
        assert 'key' not in self.concent_service._history

        assert self.concent_service.cancel('key')
        assert not self.concent_service.result('key')

        assert 'key' not in self.concent_service._delayed
        assert 'key' not in self.concent_service._history

    def test_loop_exception(self, send_mock, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=0
        )

        send_mock.side_effect = exceptions.ConcentRequestException
        with mock.patch("golem.network.concent.client.ConcentClientService._grace_sleep") as sleep_mock:  # noqa
            self.concent_service._loop()
            sleep_mock.assert_called_once_with()
        send_mock.assert_called_once_with(
            self.msg,
            self.concent_service.signing_key
        )

        req = self.concent_service.result('key')
        assert req.status == client.ConcentRequestStatus.Error
        assert isinstance(req.content, exceptions.ConcentRequestException)

        assert not self.concent_service._delayed
        assert not self.concent_service._history

    def test_loop_request_timeout(self, send_mock, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=0
        )
        delta = datetime.timedelta(seconds=constants.MSG_LIFETIMES.get(
            self.msg.__class__,
            constants.DEFAULT_MSG_LIFETIME,
        ))
        with freeze_time(datetime.datetime.now() + delta):

            self.concent_service._loop()
        req = self.concent_service.result('key')
        self.assertEqual(send_mock.call_count, 0)
        assert req.status == client.ConcentRequestStatus.TimedOut

    def test_loop(self, send_mock, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=0
        )

        self.concent_service._loop()
        req = self.concent_service.result('key')
        send_mock.assert_called_once_with(
            self.msg,
            self.concent_service.signing_key
        )
        assert req.status == client.ConcentRequestStatus.Success


class TestConcentRequestStatus(TestCase):

    def test_initial(self):
        status = client.ConcentRequestStatus.Initial
        assert not status.completed()
        assert not status.success()
        assert not status.error()

    def test_waiting(self):
        status = client.ConcentRequestStatus.Waiting
        assert not status.completed()
        assert not status.success()
        assert not status.error()

    def test_queued(self):
        status = client.ConcentRequestStatus.Queued
        assert not status.completed()
        assert not status.success()
        assert not status.error()

    def test_success(self):
        status = client.ConcentRequestStatus.Success
        assert status.completed()
        assert status.success()
        assert not status.error()

    def test_timed_out(self):
        status = client.ConcentRequestStatus.TimedOut
        assert status.completed()
        assert not status.success()
        assert status.error()

    def test_error(self):
        status = client.ConcentRequestStatus.Error
        assert status.completed()
        assert not status.success()
        assert status.error()
