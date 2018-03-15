from os import path

from apps.blender.dockerenvironment.blenderenvironment import BlenderEnvironment

from golem.model import Performance
from golem.testutils import DatabaseFixture, PEP8MixIn
from golem.tools.ci import ci_skip


@ci_skip
class BlenderEnvTest(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["apps/blender/dockerenvironment/blenderenvironment.py"]

    def test_blender(self):
        """Basic environment test."""
        env = BlenderEnvironment()
        self.assertTrue(env.check_support())
        self.assertTrue(env.check_software())

    def test_get_performance(self):
        """Changing estimated performance in ClientConfigDescriptor."""
        env = BlenderEnvironment()
        result = env.get_performance()
        assert result == 0.0

        fake_performance = 2345.2
        p = Performance(environment_id=BlenderEnvironment.get_id(),
                        value=fake_performance)
        p.save()
        result = env.get_performance()
        self.assertEquals(result, fake_performance)

    def test_main_program_file(self):
        assert path.isfile(BlenderEnvironment().default_program_file)
