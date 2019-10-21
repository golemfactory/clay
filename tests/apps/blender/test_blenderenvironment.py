from apps.blender.blenderenvironment import BlenderEnvironment
from golem.environments.minperformancemultiplier import MinPerformanceMultiplier

from golem.model import Performance
from golem.testutils import DatabaseFixture, PEP8MixIn
from golem.tools.ci import ci_skip


@ci_skip
class BlenderEnvTest(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["apps/blender/blenderenvironment.py"]

    def setUp(self):
        super().setUp()
        self.env = BlenderEnvironment()

    def test_blender(self):
        """Basic environment test."""
        self.assertTrue(self.env.check_support())

    def test_get_performance(self):
        """Changing estimated performance in ClientConfigDescriptor."""
        assert self.env.get_benchmark_result().performance == 0.0

        # given
        fake_performance = 2345.2
        p = Performance(environment_id=BlenderEnvironment.get_id(),
                        value=fake_performance)
        p.save()

        # then
        self.assertEqual(self.env.get_benchmark_result().performance,
                         fake_performance)

    def test_get_min_accepted_performance_default(self):
        self.assertEqual(MinPerformanceMultiplier.get(), 0.0)
        self.assertEqual(self.env.get_min_accepted_performance(), 0.0)

    def test_get_min_accepted_performance(self):
        # given
        p = Performance(environment_id=BlenderEnvironment.get_id(),
                        min_accepted_step=100)
        p.save()
        MinPerformanceMultiplier.set(3.141)

        # then
        self.assertEqual(MinPerformanceMultiplier.get(), 3.141)
        self.assertEqual(self.env.get_min_accepted_performance(), 314.1)
