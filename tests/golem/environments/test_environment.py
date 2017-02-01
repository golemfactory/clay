from os import path

from golem.testutils import TempDirFixture

from golem.environments.environment import Environment
from golem.clientconfigdescriptor import ClientConfigDescriptor


class EnvTest(TempDirFixture):

    def test_get_performance(self):
        env = Environment()
        perf = 6666.6
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)

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

