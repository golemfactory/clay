from mock import patch, Mock

from gnr.gnrstartapp import config_logging, load_environments, start_and_configure_client
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from golem.environments.environment import Environment
from golem.tools.testdirfixture import TestDirFixture


class TestStartAppFunc(TestDirFixture):
    def test_config_logging(self):
        config_logging()

    @patch("gnr.gnrstartapp.Client")
    def test_start_clients(self, client):
        envs = load_environments()
        for el in envs:
            assert isinstance(el, Environment)
        assert len(envs) > 2

        client.transaction_system = None

        logic = RenderingApplicationLogic()
        logic.customizer = Mock()
        start_and_configure_client(logic, envs, self.path)
        assert client.called
