import sys
import unittest
from unittest.mock import patch

from golemcli import start


class TestGolemCLI(unittest.TestCase):

    @patch('golemcli.install_reactor')
    @patch('golem.interface.websockets.WebSocketCLI.execute')
    @patch('golem.core.common.config_logging')
    def test_golem_cli(self, *_):

        with patch.object(sys, 'argv', ["program"]):
            start()
        with patch.object(sys, 'argv', ["program", "-i"]):
            start()
        with patch.object(sys, 'argv', ["program", "--some_forwarded_flag"]):
            start()
