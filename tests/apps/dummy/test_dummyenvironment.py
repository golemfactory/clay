from os import path

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.model import Performance
from golem.testutils import DatabaseFixture
from golem.tools.ci import ci_skip


@ci_skip
class TestDummyEnvironment(DatabaseFixture):
    def setUp(self):
        super().setUp()
        self.env = DummyTaskEnvironment()

    def test_get_performance(self):
        result = self.env.get_performance()
        assert result == 0.0

        perf = 1234.5
        p = Performance(environment_id=DummyTaskEnvironment.get_id(),
                        value=perf)
        p.save()
        result = self.env.get_performance()
        self.assertTrue(result == perf)

    def test_get_min_accepted_performance_default(self):
        self.assertEqual(MinPerformanceMultiplier.get(), 0.0)
        self.assertEqual(self.env.get_min_accepted_performance(), 0.0)

    def test_get_min_accepted_performance(self):
        p = Performance(environment_id=DummyTaskEnvironment.get_id(),
                        min_accepted_step=100)
        p.save()
        MinPerformanceMultiplier.set(3.141)
        self.assertEqual(MinPerformanceMultiplier.get(), 3.141)
        self.assertEqual(self.env.get_min_accepted_performance(), 314.1)

    def test_main_program_file(self):
        assert path.isfile(DummyTaskEnvironment().main_program_file)
