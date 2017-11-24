import logging
import time
from unittest import mock, TestCase

from golem_messages import message
from requests.exceptions import RequestException

from golem.core.variables import CONCENT_URL
from golem.network.concent.client import ConcentClient, ConcentRequestStatus, \
    ConcentClientService, ConcentRequest
from golem.network.concent.exceptions import ConcentUnavailableException, \
    ConcentServiceException, ConcentRequestException

logger = logging.getLogger(__name__)


mock_msg = message.MessageForceReportComputedTask('subtask_id')
mock_msg._raw = mock_msg.serialize(
    sign_func=lambda x: b'0' * message.Message.SIG_LEN,
    encrypt_func=lambda x: x
)

# Succesfull mock
mock_success = mock.MagicMock()
mock_success.status_code = 200
mock_success.content = mock_msg

# Succesfull empty mock
mock_empty = mock.MagicMock()
mock_empty.status_code = 200
mock_empty.content = ""

# Client error mock
mock_client_error = mock.MagicMock()
mock_client_error.status_code = 400
mock_client_error.content = mock_msg

# Server error mock
mock_server_error = mock.MagicMock()
mock_server_error.status_code = 500
mock_server_error.content = mock_msg


# Exception mock
def connection_error(*args, **kwargs):
    response = mock.MagicMock()
    response.status_code = 500
    response.content = b"ERROR"
    kwargs['response'] = response
    raise RequestException(args, kwargs)


class TestConcentClient(TestCase):

    @mock.patch('requests.post', return_value=mock_success)
    def test_message(self, mock_requests_post):

        client = ConcentClient()
        response = client.send(mock_msg)

        self.assertEqual(response, mock_msg)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg.raw)

    @mock.patch('requests.post', return_value=mock_empty)
    def test_message_empty(self, mock_requests_post):

        client = ConcentClient()
        response = client.send(mock_msg)

        self.assertEqual(response, None)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg.raw)

    @mock.patch('requests.post', return_value=mock_client_error)
    def test_message_client_error(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentRequestException):
            client.send(mock_msg)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg.raw)

    @mock.patch('requests.post', return_value=mock_server_error)
    def test_message_server_error(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentServiceException):
            client.send(mock_msg)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg.raw)

    @mock.patch('requests.post', side_effect=RequestException)
    def test_message_exception(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentUnavailableException):
            client.send(mock_msg)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg.raw)

    @mock.patch('requests.post', side_effect=connection_error)
    def test_message_exception_data(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentUnavailableException):
            client.send(mock_msg)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg.raw)

    @mock.patch('golem.network.concent.client.logger')
    @mock.patch('time.time', side_effect=[time.time(), (time.time()+(6*60)),
                                          time.time()])
    @mock.patch('requests.post', return_value=mock_server_error)
    def test_message_error_repeat_retry(self, mock_requests_post,
                                        mock_time, *_):

        client = ConcentClient()

        self.assertRaises(ConcentServiceException, client.send, mock_msg)
        self.assertEqual(mock_time.call_count, 0)
        self.assertRaises(ConcentServiceException, client.send, mock_msg)
        self.assertEqual(mock_time.call_count, 0)
        self.assertEqual(mock_requests_post.call_count, 2)


@mock.patch('twisted.internet.reactor', create=True)
@mock.patch('golem.network.concent.client.ConcentClientService.QUEUE_TIMEOUT',
            0.1)
@mock.patch('golem.network.concent.client.ConcentClient')
class TestConcentClientService(TestCase):

    def test_start_stop(self, *_):
        concent_service = ConcentClientService()
        concent_service._loop = mock.MagicMock()

        concent_service.start()
        time.sleep(1.)
        concent_service.stop()
        concent_service.join(timeout=3)

        assert concent_service._loop.called

    def test_submit(self, *_):
        concent_service = ConcentClientService()
        concent_service.submit(
            'key',
            message.MessageForceReportComputedTask('id'),
            delay=0
        )

        assert 'key' not in concent_service._delayed
        assert 'key' in concent_service._queued

        assert not concent_service.cancel('key')
        assert concent_service.result('key')

        assert 'key' not in concent_service._delayed
        assert 'key' not in concent_service._queued

    def test_delayed_submit(self, *_):
        concent_service = ConcentClientService()
        concent_service.submit(
            'key',
            message.MessageForceReportComputedTask('id'),
            delay=60
        )

        assert 'key' in concent_service._delayed
        assert 'key' not in concent_service._queued

        assert concent_service.cancel('key')
        assert not concent_service.result('key')

        assert 'key' not in concent_service._delayed
        assert 'key' not in concent_service._queued

    # FIXME: remove when 'enabled' property is dropped
    def test_disabled(self, *_):
        concent_service = ConcentClientService()
        concent_service.submit(
            'key',
            message.MessageForceReportComputedTask('id'),
            delay=0
        )

        concent_service._loop()
        assert not concent_service._client.send.called

    # FIXME: remove when 'enabled' property is dropped
    def test_enabled(self, *_):
        concent_service = ConcentClientService(enabled=True)
        concent_service.submit(
            'key',
            message.MessageForceReportComputedTask('id'),
            delay=0
        )

        concent_service._loop()
        assert concent_service._client.send.called

    @mock.patch('time.sleep')
    def test_loop_exception(self, sleep, *_):
        concent_service = ConcentClientService(enabled=True)
        concent_service.submit(
            'key',
            message.MessageForceReportComputedTask('id'),
            delay=0
        )

        def raise_exc(*_a, **_kw):
            raise ConcentRequestException()

        concent_service._client.send.side_effect = raise_exc
        concent_service._loop()
        assert sleep.called

        req = concent_service.result('key')
        assert req.status == ConcentRequestStatus.Error
        assert isinstance(req.content, ConcentRequestException)

        assert not concent_service._delayed
        assert not concent_service._queued

    @mock.patch.dict('golem.network.concent.constants.MSG_LIFETIMES', {
        message.MessageForceReportComputedTask: -10
    })
    def test_loop_request_timeout(self, *_):
        concent_service = ConcentClientService(enabled=True)
        concent_service.submit(
            'key',
            message.MessageForceReportComputedTask('id'),
            delay=0
        )

        concent_service._loop()
        req = concent_service.result('key')
        assert req.status == ConcentRequestStatus.TimedOut

    def test_loop(self, *_):
        concent_service = ConcentClientService(enabled=True)
        concent_service.submit(
            'key',
            message.MessageForceReportComputedTask('id'),
            delay=0
        )

        concent_service._loop()
        req = concent_service.result('key')
        assert req.status == ConcentRequestStatus.Success


class TestConcentRequest(TestCase):

    def test(self):
        key = ConcentRequest.build_key(
            'subtask_id',
            message.MessageForceReportComputedTask
        )
        msg = message.MessageForceReportComputedTask('id')
        lifetime = 10.5

        req = ConcentRequest(key, msg, lifetime)

        assert isinstance(key, str)
        assert req.key is key
        assert req.msg is msg
        assert req.url is None
        assert req.status == ConcentRequestStatus.Initial
        assert req.sent_ts is None
        assert req.deadline_ts > time.time()


class TestConcentRequestStatus(TestCase):

    def test_initial(self):
        status = ConcentRequestStatus.Initial
        assert not status.completed()
        assert not status.success()
        assert not status.error()

    def test_waiting(self):
        status = ConcentRequestStatus.Waiting
        assert not status.completed()
        assert not status.success()
        assert not status.error()

    def test_queued(self):
        status = ConcentRequestStatus.Queued
        assert not status.completed()
        assert not status.success()
        assert not status.error()

    def test_success(self):
        status = ConcentRequestStatus.Success
        assert status.completed()
        assert status.success()
        assert not status.error()

    def test_timed_out(self):
        status = ConcentRequestStatus.TimedOut
        assert status.completed()
        assert not status.success()
        assert status.error()

    def test_error(self):
        status = ConcentRequestStatus.Error
        assert status.completed()
        assert not status.success()
        assert status.error()
