from os import path

from golem.testutils import DatabaseFixture

from golem.environments.environment import Environment
from golem.model import Performance
from golem.testutils import PEP8MixIn


class EnvTest(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["golem/environments/environment.py"]

    def test_get_performance(self):
        env = Environment()
        perf_value = 6666.6
        perf = Performance(environment_id="DEFAULT", value=perf_value)
        perf.save()
        result = env.get_performance()
        self.assertTrue(result == perf_value)

    def test_get_source_code(self):
        env = Environment()
        assert env.get_source_code() is None

        file_name = path.join(self.path, "mainprogramfile")
        env.main_program_file = file_name
        assert env.get_source_code() is None

        with open(file_name, 'w') as f:
            f.write("PROGRAM CODE")

        env.main_program_file = file_name
        assert env.get_source_code() == "PROGRAM CODE"

    def test_check_software(self):
        env = Environment()
        assert not env.check_software()
        env.allow_custom_main_program_file = True
        assert env.check_software()
        env.allow_custom_main_program_file = False

        file_name = path.join(self.path, "mainprogramfile")
        env.main_program_file = file_name

        with open(file_name, 'w') as f:
            f.write("PROGRAM CODE")

        assert env.check_software()

    def test_run_default_benchmark(self):
        assert Environment.get_performance() == 0.0
        assert Environment.run_default_benchmark(save=True) > 0.0
        assert Environment.get_performance() > 0.0
