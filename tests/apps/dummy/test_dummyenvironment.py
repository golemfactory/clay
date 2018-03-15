from os import path

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from golem.model import Performance
from golem.testutils import DatabaseFixture
from golem.tools.ci import ci_skip


@ci_skip
class TestDummyEnvironment(DatabaseFixture):
    def test_dummy(self):
        env = DummyTaskEnvironment()
        self.assertIsInstance(env, DummyTaskEnvironment)

    def test_get_performance(self):
        env = DummyTaskEnvironment()
        result = env.get_performance()
        assert result == 0.0

        perf = 1234.5
        p = Performance(environment_id=DummyTaskEnvironment.get_id(),
                        value=perf)
        p.save()
        result = env.get_performance()
        self.assertTrue(result == perf)

    def test_main_program_file(self):
        assert path.isfile(DummyTaskEnvironment().default_program_file)
