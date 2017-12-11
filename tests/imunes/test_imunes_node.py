import unittest

from mock import patch
from click.testing import CliRunner

from golem.testutils import DatabaseFixture

from apps.blender.blenderenvironment import BlenderEnvironment


# Do not remove! (even if pycharm complains that this import is not used)
from .node import immunes_start
from twisted.internet import reactor  # noqa


class TestNode(DatabaseFixture):

    @unittest.expectedFailure
    @patch('golem.client.Client')
    @patch('twisted.internet.reactor')
    def test_blender_enabled(self, mock_reactor, mock_client):
        result = CliRunner().invoke(immunes_start, ['-d', self.path])
        assert not result.exception
        assert result.exit_code == 0

        env_types = []
        for name, args, _ in mock_client.mock_calls:
            if name == '().environments_manager.add_environment':
                (env_arg, ) = args
                self.assertTrue(env_arg.accept_tasks)
                env_types.append(type(env_arg))
        self.assertTrue((BlenderEnvironment in env_types))

    @unittest.expectedFailure
    @patch('golem.client.Client')
    @patch('twisted.internet.reactor')
    def test_blender_disabled(self, mock_reactor, mock_client):
        runner = CliRunner()
        result = runner.invoke(immunes_start, ['--no-blender', '-d', self.path])
        assert not result.exception
        assert result.exit_code == 0

        env_types = []
        for name, args, _ in mock_client.mock_calls:
            if name == '().environments_manager.add_environment':
                (env_arg, ) = args
                env_types.append(type(env_arg))
        self.assertTrue(BlenderEnvironment not in env_types)
