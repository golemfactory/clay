from golem.environments.environmentsconfig import EnvironmentsConfig
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.tools.testdirfixture import TestDirFixture
from tests.golem.environments.test_environment_class import DummyTestEnvironment


class TestEnvironmentsConfig(TestDirFixture):

    def test_load_config(self):
        envs = [("Test Env", True)]
        config = EnvironmentsConfig.load_config(envs, self.path)
        assert config

    def test_load_config_empty(self):
        envs = {}
        config = EnvironmentsConfig.load_config(envs, self.path)
        assert config

    def test_load_config_manager(self):
        mgr = EnvironmentsManager()
        env = DummyTestEnvironment()
        mgr.add_environment(env.get_id(), env)
        mgr.load_config(self.path)
        assert mgr.env_config

    def test_load_config_manager_empty(self):
        mgr = EnvironmentsManager()
        mgr.load_config(self.path)
        assert mgr.env_config
