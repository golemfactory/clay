import unittest
from golem.environments.environment import Environment
from golem.environments.environmentsconfig import EnvironmentsConfig
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.tools.testdirfixture import TestDirFixture


class TestEnvironmentsConfig(TestDirFixture):

    def test_load_config(self):
        envs = {"test-env": ("Test Env", True)}
        node_name = "X"
        config = EnvironmentsConfig.load_config(node_name, envs, self.path)
        assert config

    @unittest.expectedFailure
    def test_load_config_empty(self):
        envs = {}  # FIXME: Passing empty env list breaks config write.
        node_name = "X"
        config = EnvironmentsConfig.load_config(node_name, envs, self.path)
        assert config

    def test_load_config_manager(self):
        mgr = EnvironmentsManager()
        mgr.environments.add(Environment())
        mgr.load_config("obsolate name", self.path)
        assert mgr.env_config

    @unittest.expectedFailure
    def test_load_config_manager_empty(self):
        # FIXME: Passing empty env list breaks config write.
        mgr = EnvironmentsManager()
        mgr.load_config("obsolate name", self.path)
        assert mgr.env_config
