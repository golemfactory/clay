from os import path

from golem.testutils import DatabaseFixture

from golem.model import Performance
from golem.testutils import PEP8MixIn
from tests.golem.environments.test_environment_class import DummyTestEnvironment


class EnvTest(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["golem/environments/environment.py"]

    def test_get_performance(self):
        env = DummyTestEnvironment()
        perf_value = 6666.6
        perf = Performance(environment_id=env.get_id(),
                           value=perf_value)
        perf.save()
        result = env.get_performance()
        self.assertTrue(result == perf_value)

    def test_get_source_code(self):
        env = DummyTestEnvironment()
        assert env.get_source_code() is None

        file_name = path.join(self.path, "mainprogramfile")
        env.default_program_file = file_name
        assert env.get_source_code() is None

        with open(file_name, 'w') as f:
            f.write("PROGRAM CODE")

        env.default_program_file = file_name
        assert env.get_source_code() == "PROGRAM CODE"

    def test_check_software(self):
        env = DummyTestEnvironment()
        assert not env._check_software()  # pylint: disable=protected-access
        env.allow_custom_source_code = True
        assert env._check_software()  # pylint: disable=protected-access
        env.allow_custom_source_code = False

        file_name = path.join(self.path, "mainprogramfile")
        env.default_program_file = file_name

        with open(file_name, 'w') as f:
            f.write("PROGRAM CODE")

        assert env._check_software()  # pylint: disable=protected-access

    def test_run_default_benchmark(self):
        env = DummyTestEnvironment()
        self.assertEqual(env.get_performance(), 0.0)
        self.assertGreater(
            DummyTestEnvironment.run_default_benchmark(
                save=True, env_id=env.get_id()),
            0.0)
        self.assertGreater(env.get_performance(), 0.0)
