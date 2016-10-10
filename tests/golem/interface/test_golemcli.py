import unittest

import sys
from mock import patch

from golemcli import start


def _nop(*a, **kw):
    pass


class TestGolemCLI(unittest.TestCase):

    @patch('golem.interface.websockets.WebSocketCLI.execute', side_effect=_nop)
    @patch('golem.core.common.config_logging', side_effect=_nop)
    def test_golem_cli(self, *_):

        with patch.object(sys, 'argv', ["program"]):
            start()
        with patch.object(sys, 'argv', ["program", "-i"]):
            start()
        with patch.object(sys, 'argv', ["program", "--some_forwarded_flag"]):
            start()
