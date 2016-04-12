from unittest import TestCase
from os import path

from mock import patch

from gnr.docker_environments import LuxRenderEnvironment

from golem.tools.testdirfixture import TestDirFixture


class TestLuxRenderEnvironment(TestDirFixture):
    @patch("gnr.docker_environments.environ")
    def test_check_software(self, mock_environ):
        env = LuxRenderEnvironment()
        self.assertIsInstance(env, LuxRenderEnvironment)
        mock_environ.get.return_value = None
        assert not env.check_software()
        mock_environ.get.return_value = self.path
        assert not env.check_software()
        with open(path.join(self.path, env.software_name[0]), 'w'):
            pass
        with open(path.join(self.path, env.software_name[1]), 'w'):
            pass
        assert env.check_software()
