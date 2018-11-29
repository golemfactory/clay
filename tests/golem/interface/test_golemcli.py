import sys
import unittest
from unittest.mock import patch, mock_open

from portalocker import LockException

from golemcli import start


@patch('golemcli.install_reactor')
@patch('golem.interface.websockets.WebSocketCLI.execute')
@patch('golem.core.common.config_logging')
@patch('golem.rpc.cert.CertificateManager.get_secret')
class TestGolemCLI(unittest.TestCase):
    def test_golem_cli(self, *_):

        with patch.object(sys, 'argv', ["program"]):
            start()
        with patch.object(sys, 'argv', ["program", "-i"]):
            start()
        with patch.object(sys, 'argv', ["program", "--some_forwarded_flag"]):
            start()

    @patch('golemcli.is_app_running', side_effect=[True, True])
    @patch('golemcli.logger')
    def test_check_golem_running(self, logger, *_):
        with patch.object(sys, 'argv', ['program', '-m']):
            start()
            args, kwargs = logger.warning.call_args
            self.assertIn('removing', args[0])

        with patch.object(sys, 'argv', ['program']):
            start()
            args, kwargs = logger.warning.call_args
            self.assertIn('adding', args[0])

    @patch('builtins.open', mock_open())
    @patch('os.path.isfile', side_effect=[True])
    @patch('portalocker.Lock.acquire')
    @patch('golemcli.logger')
    def test_is_app_running_negative(self, logger, *_):
        with patch.object(sys, 'argv', ['program']):
            start()
            logger.warning.assert_not_called()

    @patch('builtins.open', mock_open())
    @patch('os.path.isfile', side_effect=[True])
    @patch('portalocker.Lock.acquire', side_effect=LockException)
    @patch('golemcli.logger')
    def test_is_app_running_positive(self, logger, *_):
        with patch.object(sys, 'argv', ['program']):
            start()
            logger.warning.assert_called()
