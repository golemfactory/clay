import sys
import unittest
import unittest.mock as mock

from golemcli import start


def _nop(*a, **kw):
    pass


class TestGolemCLI(unittest.TestCase):

    @mock.patch('golem.interface.websockets.WebSocketCLI.execute', side_effect=_nop)
    @mock.patch('golem.core.common.config_logging', side_effect=_nop)
    def test_golem_cli(self, *_):

        with mock.patch.object(sys, 'argv', ["program"]):
            start()
        with mock.patch.object(sys, 'argv', ["program", "-i"]):
            start()
        with mock.patch.object(sys, 'argv', ["program", "--some_forwarded_flag"]):
            start()
