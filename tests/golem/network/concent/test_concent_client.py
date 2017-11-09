import logging
import time
from unittest import mock, TestCase

from requests.exceptions import RequestException

from golem.core.variables import CONCENT_URL
from golem.network.concent.client import ConcentClient, \
    ConcentUnavailableException, ConcentGraceException

logger = logging.getLogger(__name__)

mock_message = "Hello World"

# Succesfull mock
mock_success = mock.MagicMock()
mock_success.status_code = 200
mock_success.text = mock_message

# Succesfull empty mock
mock_empty = mock.MagicMock()
mock_empty.status_code = 200
mock_empty.text = ""

# Error mock
mock_error = mock.MagicMock()
mock_error.status_code = 500
mock_error.text = mock_message


# Exception mock
def connection_error():
    raise RequestException


mock_request_error = mock.MagicMock(side_effect=connection_error)
mock_request_error.response = mock.MagicMock()
mock_request_error.response.status_code = 500
mock_request_error.response.text = "ERROR"


class TestConcentClient(TestCase):

    @mock.patch('requests.post', return_value=mock_success)
    def test_message(self, mock_requests_post):

        client = ConcentClient()
        response = client.message(mock_message)

        self.assertEqual(response, mock_message)
        self.assertTrue(client.is_available())

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_message)

    @mock.patch('requests.post', return_value=mock_empty)
    def test_message_empty(self, mock_requests_post):

        client = ConcentClient()
        response = client.message(mock_message)

        self.assertEqual(response, None)
        self.assertTrue(client.is_available())

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_message)

    @mock.patch('requests.post', return_value=mock_error)
    def test_message_error(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentUnavailableException):
            client.message(mock_message)

        self.assertFalse(client.is_available())

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_message)

    @mock.patch('requests.post', side_effect=RequestException())
    def test_message_exception(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentUnavailableException):
            client.message(mock_message)

        self.assertFalse(client.is_available())

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_message)

    @mock.patch('requests.post', return_value=mock_request_error)
    def test_message_exception_data(self, mock_requests_post):

        client = ConcentClient()

        with self.assertRaises(ConcentUnavailableException):
            client.message(mock_message)

        self.assertFalse(client.is_available())

        mock_requests_post.assert_called_with(CONCENT_URL, data=mock_message)

    @mock.patch('requests.post', return_value=mock_error)
    def test_message_error_repeat(self, mock_requests_post):

        client = ConcentClient()

        self.assertRaises(ConcentUnavailableException, client.message,
                          mock_message)
        self.assertRaises(ConcentGraceException, client.message, mock_message)

        self.assertTrue(mock_requests_post.called_once)

    @mock.patch('golem.network.concent.client.logger')
    @mock.patch('time.time', side_effect=[time.time(), (time.time()+(6*60)),
                                          time.time()])
    @mock.patch('requests.post', return_value=mock_error)
    def test_message_error_repeat_retry(self, mock_requests_post,
                                        mock_time, mock_logger):

        client = ConcentClient()

        self.assertRaises(ConcentUnavailableException, client.message,
                          mock_message)
        self.assertEqual(mock_time.call_count, 1)
        self.assertRaises(ConcentUnavailableException, client.message,
                          mock_message)

        self.assertEqual(mock_time.call_count, 3)
        self.assertEqual(mock_requests_post.call_count, 2)
