import time
from unittest import TestCase

from mock import patch

from golem.vm.memorychecker import MemoryChecker


class TestMemoryChecker(TestCase):

    @patch("golem.vm.memorychecker.psutil")
    def test_memory(self, psutil_mock):
        psutil_mock.virtual_memory.return_value.used = 1200000
        mc = MemoryChecker()
        assert isinstance(mc, MemoryChecker)
        mc.start()
        psutil_mock.virtual_memory.return_value.used = 1200050
        time.sleep(0.6)
        psutil_mock.virtual_memory.return_value.used = 1100030
        time.sleep(0.6)
        psutil_mock.virtual_memory.return_value.used = 1200030
        time.sleep(0.6)
        mm = mc.stop()
        mc.join(60.0)
        assert mm == 50
        assert mc.max_mem == 1200050
        assert mc.min_mem == 1100030
