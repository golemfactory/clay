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


def mock_sign(*_):
    return b'0' * message.Message.SIG_LEN


def mock_encrypt(source):
    return source


mock_msg = message.ForceReportComputedTask('subtask_id')
mock_msg_data = mock_msg.serialize(
    sign_func=mock_sign,
    encrypt_func=mock_encrypt
)

# Succesfull mock
mock_success = mock.MagicMock()
mock_success.status_code = 200
mock_success.content = mock_msg_data

# Succesfull empty mock
mock_empty = mock.MagicMock()
mock_empty.status_code = 200
mock_empty.content = ""

# Client error mock
mock_client_error = mock.MagicMock()
mock_client_error.status_code = 400
mock_client_error.content = mock_msg_data

# Server error mock
mock_server_error = mock.MagicMock()
mock_server_error.status_code = 500
mock_server_error.content = mock_msg_data


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
        response = client.send(data=mock_msg_data)

        self.assertEqual(response, mock_msg_data)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg_data)

    @mock.patch('requests.post', return_value=mock_empty)
    def test_message_empty(self, mock_requests_post):

        client = ConcentClient()
        response = client.send(data=mock_msg_data)

        self.assertEqual(response, None)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg_data)

    @mock.patch('requests.post', return_value=mock_client_error)
    def test_message_client_error(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentRequestException):
            client.send(data=mock_msg_data)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg_data)

    @mock.patch('requests.post', return_value=mock_server_error)
    def test_message_server_error(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentServiceException):
            client.send(data=mock_msg_data)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg_data)

    @mock.patch('requests.post', side_effect=RequestException)
    def test_message_exception(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentUnavailableException):
            client.send(data=mock_msg_data)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg_data)

    @mock.patch('requests.post', side_effect=connection_error)
    def test_message_exception_data(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentUnavailableException):
            client.send(data=mock_msg_data)

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_msg_data)

    @mock.patch('golem.network.concent.client.logger')
    @mock.patch('time.time', side_effect=[time.time(), (time.time()+(6*60)),
                                          time.time()])
    @mock.patch('requests.post', return_value=mock_server_error)
    def test_message_error_repeat_retry(self, mock_requests_post,
                                        mock_time, *_):

        client = ConcentClient()

        self.assertRaises(ConcentServiceException, client.send, mock_msg_data)
        self.assertEqual(mock_time.call_count, 0)
        self.assertRaises(ConcentServiceException, client.send, mock_msg_data)
        self.assertEqual(mock_time.call_count, 0)
        self.assertEqual(mock_requests_post.call_count, 2)


@mock.patch('twisted.internet.reactor', create=True)
@mock.patch('golem.network.concent.client.ConcentClientService.QUEUE_TIMEOUT',
            0.1)
@mock.patch('golem.network.concent.client.ConcentClient')
class TestConcentClientService(TestCase):

    def test_start_stop(self, *_):
        concent_service = ConcentClientService(enabled=False)
        concent_service._loop = mock.MagicMock()

        concent_service.start()
        time.sleep(1.)
        concent_service.stop()
        concent_service.join(timeout=3)

        assert concent_service._loop.called

    def test_submit(self, *_):
        concent_service = ConcentClientService(enabled=False)
        msg = message.ForceReportComputedTask('id')

        concent_service.submit(
            'key',
            msg.serialize(mock_sign),
            msg.__class__,
            delay=0
        )

        assert 'key' not in concent_service._delayed
        assert 'key' in concent_service._history

        assert not concent_service.cancel('key')
        assert concent_service.result('key')

        assert 'key' not in concent_service._delayed
        assert 'key' not in concent_service._history

    def test_delayed_submit(self, *_):
        concent_service = ConcentClientService(enabled=False)
        msg = message.ForceReportComputedTask('id')

        concent_service.submit(
            'key',
            msg.serialize(mock_sign),
            msg.__class__,
            delay=60
        )

        assert 'key' in concent_service._delayed
        assert 'key' not in concent_service._history

        assert concent_service.cancel('key')
        assert not concent_service.result('key')

        assert 'key' not in concent_service._delayed
        assert 'key' not in concent_service._history

    # FIXME: remove when 'enabled' property is dropped
    def test_disabled(self, *_):
        concent_service = ConcentClientService(enabled=False)
        msg = message.ForceReportComputedTask('id')

        concent_service.submit(
            'key',
            msg.serialize(mock_sign),
            msg.__class__,
            delay=0
        )

        concent_service._loop()
        assert not concent_service._client.send.called

    # FIXME: remove when 'enabled' property is dropped
    def test_enabled(self, *_):
        concent_service = ConcentClientService(enabled=True)
        msg = message.ForceReportComputedTask('id')

        concent_service.submit(
            'key',
            msg.serialize(mock_sign),
            msg.__class__,
            delay=0
        )

        concent_service._loop()
        assert concent_service._client.send.called

    @mock.patch('time.sleep')
    def test_loop_exception(self, sleep, *_):
        concent_service = ConcentClientService(enabled=True)
        msg = message.ForceReportComputedTask('id')

        concent_service.submit(
            'key',
            msg.serialize(mock_sign),
            msg.__class__,
            delay=0
        )

        def raise_exc(*_a, **_kw):
            raise ConcentRequestException()

        concent_service._client.send.side_effect = raise_exc
        concent_service._loop()
        assert concent_service._client.send.called
        assert sleep.called

        req = concent_service.result('key')
        assert req.status == ConcentRequestStatus.Error
        assert isinstance(req.content, ConcentRequestException)

        assert not concent_service._delayed
        assert not concent_service._history

    @mock.patch.dict('golem.network.concent.constants.MSG_LIFETIMES', {
        message.ForceReportComputedTask: -10
    })
    def test_loop_request_timeout(self, *_):
        concent_service = ConcentClientService(enabled=True)
        msg = message.ForceReportComputedTask('id')

        concent_service.submit(
            'key',
            msg.serialize(mock_sign),
            msg.__class__,
            delay=0
        )

        concent_service._loop()
        req = concent_service.result('key')
        assert not concent_service._client.send.called
        assert req.status == ConcentRequestStatus.TimedOut

    def test_loop(self, *_):
        concent_service = ConcentClientService(enabled=True)
        msg = message.ForceReportComputedTask('id')

        concent_service.submit(
            'key',
            msg.serialize(mock_sign),
            msg.__class__,
            delay=0
        )

        concent_service._loop()
        req = concent_service.result('key')
        assert concent_service._client.send.called
        assert req.status == ConcentRequestStatus.Success


class TestConcentRequest(TestCase):

    def test(self):
        key = ConcentRequest.build_key(
            'subtask_id',
            message.ForceReportComputedTask
        )

        msg = message.ForceReportComputedTask('id')
        msg_data = msg.serialize(mock_sign)
        msg_cls = msg.__class__

        lifetime = 10.5

        req = ConcentRequest(key, msg_data, msg_cls, lifetime)

        assert isinstance(key, str)
        assert req.key is key
        assert req.msg_data is msg_data
        assert req.msg_cls is msg_cls
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
