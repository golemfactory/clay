from time import sleep as originalsleep
from unittest import TestCase
from unittest.mock import patch

from golem.vm.memorychecker import MemoryChecker


class TestMemoryChecker(TestCase):

    @patch('time.sleep', return_value=None)  # speed up tests
    @patch("golem.vm.memorychecker.psutil")
    def test_memory(self, psutil_mock, _):
        psutil_mock.virtual_memory.return_value.used = 1200000
        mc = MemoryChecker()
        assert isinstance(mc, MemoryChecker)
        mc.start()
        psutil_mock.virtual_memory.return_value.used = 1200050
        originalsleep(0.01)
        psutil_mock.virtual_memory.return_value.used = 1100030
        originalsleep(0.01)
        psutil_mock.virtual_memory.return_value.used = 1200030
        originalsleep(0.01)
        mm = mc.stop()
        mc.join(60.0)
        assert mm == 50
        assert mc.max_mem == 1200050
        assert mc.min_mem == 1100030
