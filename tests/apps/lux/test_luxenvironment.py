from os import path

from apps.lux.luxenvironment import LuxRenderEnvironment
from golem.environments.minperformancemultiplier import MinPerformanceMultiplier

from golem.model import Performance
from golem.testutils import DatabaseFixture, PEP8MixIn
from golem.tools.ci import ci_skip


@ci_skip
class TestLuxRenderEnvironment(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["apps/lux/luxenvironment.py"]

    def setUp(self):
        super().setUp()
        self.env = LuxRenderEnvironment()

    def test_get_performance(self):
        # given
        perf_value = 1234.5
        perf = Performance(environment_id=LuxRenderEnvironment.get_id(),
                           value=perf_value)
        perf.save()

        # then
        self.assertEqual(self.env.get_performance(), perf_value)

    def test_get_min_accepted_performance_default(self):
        self.assertEqual(MinPerformanceMultiplier.get(), 0.0)
        self.assertEqual(self.env.get_min_accepted_performance(), 0.0)

    def test_get_min_accepted_performance(self):
        # given
        p = Performance(environment_id=LuxRenderEnvironment.get_id(),
                        min_accepted_step=100)
        p.save()
        MinPerformanceMultiplier.set(3.141)

        # then
        self.assertEqual(MinPerformanceMultiplier.get(), 3.141)
        self.assertEqual(self.env.get_min_accepted_performance(), 314.1)

    def test_main_program_file(self):
        assert path.isfile(LuxRenderEnvironment().main_program_file)
