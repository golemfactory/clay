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
        assert self.env.get_benchmark_result().performance == 0.0

        # given
        perf = 1234.5
        p = Performance(environment_id=DummyTaskEnvironment.get_id(),
                        value=perf)
        p.save()

        # then
        self.assertEqual(self.env.get_benchmark_result().performance, perf)

    def test_get_min_accepted_performance_default(self):
        self.assertEqual(MinPerformanceMultiplier.get(), 0.0)
        self.assertEqual(self.env.get_min_accepted_performance(), 0.0)

    def test_get_min_accepted_performance(self):
        # given
        p = Performance(environment_id=DummyTaskEnvironment.get_id(),
                        min_accepted_step=100)
        p.save()
        MinPerformanceMultiplier.set(3.141)

        # then
        self.assertEqual(MinPerformanceMultiplier.get(), 3.141)
        self.assertEqual(self.env.get_min_accepted_performance(), 314.1)
