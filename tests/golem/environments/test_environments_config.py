from golem.environments.environmentsconfig import EnvironmentsConfig
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.tools.testdirfixture import TestDirFixture
from tests.golem.environments.test_environment_class import DummyTestEnvironment


class TestEnvironmentsConfig(TestDirFixture):

    def test_load_config(self):
        envs = {"test-env": ("Test Env", True)}
        config = EnvironmentsConfig.load_config(envs, self.path)
        assert config

    def test_load_config_empty(self):
        envs = {}
        config = EnvironmentsConfig.load_config(envs, self.path)
        assert config

    def test_load_config_manager(self):
        mgr = EnvironmentsManager()
        mgr.add_environment(DummyTestEnvironment.get_id(),
                            DummyTestEnvironment())
        mgr.load_config(self.path)
        assert mgr.env_config

    def test_load_config_manager_empty(self):
        mgr = EnvironmentsManager()
        mgr.load_config(self.path)
        assert mgr.env_config
