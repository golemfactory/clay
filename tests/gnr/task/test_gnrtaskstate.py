from unittest import TestCase

from gnr.gnrtaskstate import GNRTaskState


class TestGNRTaskState(TestCase):
    def test_init(self):
        gts = GNRTaskState()
        self.assertIsInstance(gts, GNRTaskState)
