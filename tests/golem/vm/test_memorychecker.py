from typing import Iterable
from unittest import TestCase
from unittest.mock import patch

from golem.vm.memorychecker import MemoryChecker, MemoryCheckerThread


class TestMemoryChecker(TestCase):

    @patch('golem.vm.memorychecker.MemoryCheckerThread')
    def test_memory_checker(self, mc_thread):
        with MemoryChecker() as memory_checker:
            mc_thread().start.assert_called_once()
            self.assertEqual(memory_checker.estm_mem, mc_thread().estm_mem)
            mc_thread.stop.assert_not_called()
        mc_thread().stop.assert_called_once()


# pylint: disable=no-value-for-parameter
class TestMemoryCheckerThread(TestCase):

    @patch('golem.vm.memorychecker.psutil.virtual_memory')
    def test_not_started(self, virtual_memory):
        virtual_memory().used = 2137
        mc_thread = MemoryCheckerThread()
        self.assertEqual(mc_thread.estm_mem, 0)

    @patch('golem.vm.memorychecker.time.sleep')
    @patch('golem.vm.memorychecker.psutil.virtual_memory')
    def _generic_test(  # pylint: disable=too-many-arguments
            self,
            virtual_memory,
            sleep,
            initial_mem_usage: int,
            mem_usage: Iterable[int],
            exp_estimation: Iterable[int]
    ) -> None:

        virtual_memory().used = initial_mem_usage
        mc_thread = MemoryCheckerThread()

        # We are using patched sleep() function to synchronize with the thread's
        # run() method. When the thread calls sleep() all instructions up to the
        # next yield will be executed.
        def _advance():
            for used, expected in zip(mem_usage, exp_estimation):
                virtual_memory().used = used
                yield
                self.assertEqual(mc_thread.estm_mem, expected)
            mc_thread.stop()
            yield

        advance = _advance()
        sleep.side_effect = lambda _: next(advance)

        # Just calling run() instead of actually starting the thread because
        # logic is the same but raising an exception in a different thread
        # wouldn't fail the test.
        mc_thread.run()

    def test_memory_usage_constant(self):
        self._generic_test(
            initial_mem_usage=1000,
            mem_usage=(1000, 1000, 1000),
            exp_estimation=(0, 0, 0)
        )

    def test_memory_usage_rising(self):
        self._generic_test(
            initial_mem_usage=1000,
            mem_usage=(2000, 3000, 4000),
            exp_estimation=(1000, 2000, 3000)
        )

    def test_memory_usage_sinking(self):
        self._generic_test(
            initial_mem_usage=4000,
            mem_usage=(4000, 3000, 2000),
            exp_estimation=(0, 1000, 2000)
        )

    def test_memory_usage_rising_then_sinking(self):
        self._generic_test(
            initial_mem_usage=2000,
            mem_usage=(2000, 3000, 2000, 1000),
            exp_estimation=(0, 1000, 1000, 1000)
        )

    def test_memory_usage_sinking_then_rising(self):
        self._generic_test(
            initial_mem_usage=3000,
            mem_usage=(2000, 3000, 4000, 5000),
            exp_estimation=(1000, 1000, 1000, 2000)
        )
