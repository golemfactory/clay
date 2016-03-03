import unittest

from golem.task.taskstate import SubtaskState


class TestSubtaskState(unittest.TestCase):

    def test_init(self):
        ss = SubtaskState()
        self.assertIsInstance(ss, SubtaskState)
        ss.results.append(1)
        ss2 = SubtaskState()
        ss2.results.append(2)
        self.assertEqual(ss.results, [1])
        self.assertEqual(ss2.results, [2])

