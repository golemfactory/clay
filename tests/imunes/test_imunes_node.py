import unittest
from mock import patch
from gnr.node import GNRNode
from click.testing import CliRunner
from apps.blender.blenderenvironment import BlenderEnvironment
from golem.testutils import DatabaseFixture


# Do not remove! (even if pycharm complains that this import is not used)
from node import immunes_start
from twisted.internet import reactor  # noqa


class TestNode(DatabaseFixture):

    def setUp(self):
        super(TestNode, self).setUp()
        self.saved_default_environments = GNRNode.default_environments

    def tearDown(self):
        GNRNode.default_environments = self.saved_default_environments
        super(TestNode, self).tearDown()

    @unittest.expectedFailure
    @patch('golem.client.Client')
    @patch('twisted.internet.reactor')
    def test_blender_enabled(self, mock_reactor, mock_client):
        result = CliRunner().invoke(immunes_start, ['--nogui', '-d', self.path])
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
        result = runner.invoke(immunes_start, ['--no-blender', '--nogui', '-d', self.path])
        assert not result.exception
        assert result.exit_code == 0

        env_types = []
        for name, args, _ in mock_client.mock_calls:
            if name == '().environments_manager.add_environment':
                (env_arg, ) = args
                env_types.append(type(env_arg))
        self.assertTrue(BlenderEnvironment not in env_types)

    @unittest.expectedFailure
    @patch('gnr.node.Node.initialize')
    @patch('gnr.node.Node.run', autospec=True)
    def test_public_address(self, mock_run, mock_initialize):
        public_address = '1.0.0.1'
        runner = CliRunner()
        return_value = runner.invoke(immunes_start, ['--public-address', public_address, '-d', self.path])
        self.assertEquals(return_value.exit_code, 0)
        (gnr_node, ) = mock_run.call_args[0]
        try:
            self.assertEqual(gnr_node.client.node.pub_addr, public_address)
            self.assertTrue(gnr_node.client.node.is_super_node())
        except Exception as exc:
            self.fail(exc)
        finally:
            gnr_node.client.quit()
