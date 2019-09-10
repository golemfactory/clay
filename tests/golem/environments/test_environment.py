from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.testutils import DatabaseFixture

from golem.environments.environment import Environment
from golem.model import Performance
from golem.testutils import PEP8MixIn


class EnvTest(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["golem/environments/environment.py"]

    def setUp(self):
        super().setUp()
        self.env = Environment()

    def test_get_performance(self):
        # given
        perf_value = 6666.6
        perf = Performance(environment_id=Environment.get_id(),
                           value=perf_value)
        perf.save()

        # then
        self.assertEqual(self.env.get_performance().performance, perf_value)

    def test_run_default_benchmark(self):
        assert Environment.get_performance().performance == 0.0
        assert Environment.run_default_benchmark(save=True).performance > 0.0
        assert Environment.get_performance().performance > 0.0

    def test_get_min_accepted_performance_default(self):
        self.assertEqual(MinPerformanceMultiplier.get(), 0.0)
        self.assertEqual(self.env.get_min_accepted_performance(), 0.0)

    def test_get_min_accepted_performance(self):
        # given
        p = Performance(environment_id=Environment.get_id(),
                        min_accepted_step=100)
        p.save()
        MinPerformanceMultiplier.set(3.141)

        # then
        self.assertEqual(MinPerformanceMultiplier.get(), 3.141)
        self.assertEqual(self.env.get_min_accepted_performance(), 314.1)
