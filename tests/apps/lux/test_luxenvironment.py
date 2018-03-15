from os import path

from apps.lux.luxenvironment import LuxRenderEnvironment

from golem.model import Performance
from golem.testutils import DatabaseFixture, PEP8MixIn
from golem.tools.ci import ci_skip


@ci_skip
class TestLuxRenderEnvironment(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["apps/lux/luxenvironment.py"]

    def test_lux(self):
        env = LuxRenderEnvironment()
        self.assertIsInstance(env, LuxRenderEnvironment)

    def test_get_performance(self):
        env = LuxRenderEnvironment()
        perf_value = 1234.5
        perf = Performance(environment_id=LuxRenderEnvironment.get_id(),
                           value=perf_value)
        perf.save()
        result = env.get_performance()
        self.assertTrue(result == perf_value)

    def test_main_program_file(self):
        assert path.isfile(LuxRenderEnvironment().default_program_file)
