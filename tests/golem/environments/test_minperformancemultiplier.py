from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.tools.testwithdatabase import TestWithDatabase


class TestMinPerformanceMultiplier(TestWithDatabase):

    def setUp(self):
        super().setUp()
        self.min = MinPerformanceMultiplier.MIN
        self.max = MinPerformanceMultiplier.MAX

    def test_zero_when_not_set(self):
        self.assertEqual(0, MinPerformanceMultiplier.get())

    def test_min(self):
        MinPerformanceMultiplier.set(self.min)
        self.assertEqual(self.min, MinPerformanceMultiplier.get())

    def test_fractional(self):
        MinPerformanceMultiplier.set(3.1415)
        self.assertEqual(3.1415, MinPerformanceMultiplier.get())

    def test_max(self):
        MinPerformanceMultiplier.set(self.max)
        self.assertEqual(self.max, MinPerformanceMultiplier.get())

    def test_below_min(self):
        with self.assertRaisesRegex(Exception, 'must be within'):
            MinPerformanceMultiplier.set(self.min - 1)

    def test_above_max(self):
        with self.assertRaisesRegex(Exception, 'must be within'):
            MinPerformanceMultiplier.set(self.max + 2)
