import unittest
from mock import patch
from gnr.node import start, GNRNode
from click.testing import CliRunner
from golem.appconfig import AppConfig
from gnr.renderingenvironment import BlenderEnvironment

# Do not remove! (even if pycharm complains that this import is not used)
import node


class TestNode(unittest.TestCase):

    def setUp(self):
        # This is to prevent test methods from picking up AppConfigs
        # created by previously run test methods:
        AppConfig.CONFIG_LOADED = False

        self.saved_default_environments = GNRNode.default_environments

    def tearDown(self):
        GNRNode.default_environments = self.saved_default_environments

    @patch('golem.client.Client')
    @patch('gnr.node.reactor')
    def test_blender_enabled(self, mock_reactor, mock_client):
        runner = CliRunner()
        return_value = runner.invoke(start)
        self.assertEquals(return_value.exit_code, 0)

        env_types = []
        for name, args, _ in mock_client.mock_calls:
            if name == '().environments_manager.add_environment':
                (env_arg, ) = args
                self.assertTrue(env_arg.accept_tasks)
                env_types.append(type(env_arg))
        self.assertTrue(BlenderEnvironment in env_types)

    @patch('golem.client.Client')
    @patch('gnr.node.reactor')
    def test_blender_disabled(self, mock_reactor, mock_client):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--no-blender'])
        self.assertEquals(return_value.exit_code, 0)

        env_types = []
        for name, args, _ in mock_client.mock_calls:
            if name == '().environments_manager.add_environment':
                (env_arg, ) = args
                env_types.append(type(env_arg))
        self.assertTrue(BlenderEnvironment not in env_types)
