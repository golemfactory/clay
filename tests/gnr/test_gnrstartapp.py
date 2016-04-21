from mock import patch, Mock

from golem.tools.testdirfixture import TestDirFixture
from golem.environments.environment import Environment
from gnr.gnrstartapp import config_logging, load_environments, start_and_configure_client
from gnr.renderingapplicationlogic import RenderingApplicationLogic


class TestStartAppFunc(TestDirFixture):
    def test_config_logging(self):
        config_logging()

    @patch("gnr.gnrstartapp.start_client")
    def test_start_clients(self, mock_start):
        envs = load_environments()
        for el in envs:
            assert isinstance(el, Environment)
        assert len(envs) > 2

        logic = RenderingApplicationLogic()
        logic.customizer = Mock()
        start_and_configure_client(logic, envs, self.path)
