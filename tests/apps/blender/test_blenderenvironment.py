from os import path

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
        self.assertTrue(self.env.check_software())

    def test_get_performance(self):
        """Changing estimated performance in ClientConfigDescriptor."""
        result = self.env.get_performance()
        assert result == 0.0

        fake_performance = 2345.2
        p = Performance(environment_id=BlenderEnvironment.get_id(),
                        value=fake_performance)
        p.save()
        result = self.env.get_performance()
        self.assertEqual(result, fake_performance)

    def test_get_min_accepted_performance_default(self):
        self.assertEqual(MinPerformanceMultiplier.get(), 0.0)
        self.assertEqual(self.env.get_min_accepted_performance(), 0.0)

    def test_get_min_accepted_performance(self):
        p = Performance(environment_id=BlenderEnvironment.get_id(),
                        min_accepted_step=100)
        p.save()
        MinPerformanceMultiplier.set(3.141)
        self.assertEqual(MinPerformanceMultiplier.get(), 3.141)
        self.assertEqual(self.env.get_min_accepted_performance(), 314.1)

    def test_main_program_file(self):
        assert path.isfile(BlenderEnvironment().main_program_file)
