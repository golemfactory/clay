# TODO: move all test-related code somewhere to `tests` #4193
import psutil


class KillLeftoverChildrenTestMixin:
    _children_on_start = None

    @ staticmethod
    def _get_process_children():
        p = psutil.Process()
        return set([c.pid for c in p.children(recursive=True)])

    def setUp(self):
        super().setUp()
        self._children_on_start = self._get_process_children()

    def tearDown(self):
        super().tearDown()

        # in case any new child processes are still alive here, terminate them
        nkotb = self._get_process_children() - self._children_on_start
        for k in nkotb:
            try:
                p = psutil.Process(k)
                p.kill()
            except psutil.Error:
                pass
