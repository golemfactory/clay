from time import sleep as originalsleep
from unittest import TestCase
from unittest.mock import patch

from golem.vm.memorychecker import MemoryChecker, MemoryCheckerThread


class TestMemoryChecker(TestCase):

    @patch('time.sleep', return_value=None)  # speed up tests
    @patch("golem.vm.memorychecker.psutil")
    def test_memory(self, psutil_mock, _):
        psutil_mock.virtual_memory.return_value.used = 1200000
        with MemoryChecker() as mc:
            assert isinstance(mc._thread, MemoryCheckerThread)
            psutil_mock.virtual_memory.return_value.used = 1200050
            originalsleep(0.01)
            psutil_mock.virtual_memory.return_value.used = 1100030
            originalsleep(0.01)
            psutil_mock.virtual_memory.return_value.used = 1200030
            originalsleep(0.01)
            assert mc.estm_mem == 50
            assert mc._thread.max_mem == 1200050
            assert mc._thread.min_mem == 1100030
