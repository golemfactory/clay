from golem.environments.performancemultiplier import PerformanceMultiplier
from golem.tools.testwithdatabase import TestWithDatabase


class TestPerformanceMultiplier(TestWithDatabase):

    def test_zero_when_not_set(self):
        self.assertEqual(0, PerformanceMultiplier.get_percent())

    def test_are_terms_accepted_old_version(self):
        multiplier = 3.1415
        PerformanceMultiplier.set_percent(multiplier)
        self.assertEqual(multiplier, PerformanceMultiplier.get_percent())

    def test_zero(self):
        PerformanceMultiplier.set_percent(0)
        self.assertEqual(0, PerformanceMultiplier.get_percent())

    def test_thousand(self):
        PerformanceMultiplier.set_percent(1000)
        self.assertEqual(1000, PerformanceMultiplier.get_percent())

    def test_negative(self):
        with self.assertRaises(Exception, msg='performance multiplier (-1) must'
                                              ' be within [0, '
                                              '1000] inclusive.'):
            PerformanceMultiplier.set_percent(-1)

    def test_above_thousad(self):
        with self.assertRaises(Exception, msg='performance multiplier (1000.2)'
                                              ' must be within [0, '
                                              '1000] inclusive.'):
            PerformanceMultiplier.set_percent(1000.2)
