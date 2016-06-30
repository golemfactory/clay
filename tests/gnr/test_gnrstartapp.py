from mock import Mock

import twisted

from gnr.gnrstartapp import config_logging, load_environments, start_app, start_client_process
from golem.environments.environment import Environment
from golem.tools.testdirfixture import TestDirFixture


class TestStartAppFunc(TestDirFixture):
    def test_config_logging(self):
        config_logging()

    def test_start_clients(self):
        envs = load_environments()
        for el in envs:
            assert isinstance(el, Environment)
        assert len(envs) > 2

        prev_reactor = twisted.internet.reactor
        twisted.internet.reactor = Mock()

        queue = Mock()
        start_client_process(queue, self.path, False, False)

        twisted.internet.reactor = prev_reactor
