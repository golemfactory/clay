from mock import patch
from gnr.node import start, GNRNode
from click.testing import CliRunner
from golem.core.simpleenv import SimpleEnv
from gnr.renderingenvironment import BlenderEnvironment
from gnr.docker_environments import BlenderDockerEnvironment
from golem.tools.testwithappconfig import TestWithAppConfig

import shutil
import tempfile

# Do not remove! (even if pycharm complains that this import is not used)
import node


class TestNode(TestWithAppConfig):

    def setUp(self):
        super(TestNode, self).setUp()
        self.saved_default_environments = GNRNode.default_environments
        self.tmpdir = tempfile.mkdtemp(prefix="golem-test-")
        SimpleEnv.DATA_DIRECTORY = self.tmpdir

    def tearDown(self):
        GNRNode.default_environments = self.saved_default_environments
        shutil.rmtree(self.tmpdir)
        super(TestNode, self).tearDown()

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
        self.assertTrue((BlenderEnvironment in env_types) or
                        (BlenderDockerEnvironment in env_types))

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

    @patch('gnr.node.Node.initialize')
    @patch('gnr.node.Node.run', autospec = True)
    def test_public_address(self, mock_run, mock_initialize):
        public_address = '1.0.0.1'
        runner = CliRunner()
        return_value = runner.invoke(start, ['--public-address', public_address])
        self.assertEquals(return_value.exit_code, 0)
        (gnr_node, ) = mock_run.call_args[0]
        self.assertEqual(gnr_node.client.node.pub_addr, public_address)
        self.assertTrue(gnr_node.client.node.is_super_node())
