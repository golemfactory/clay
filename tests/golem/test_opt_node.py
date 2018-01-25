from click.testing import CliRunner
from mock import patch, Mock

from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from golem.tools.testwithdatabase import TestWithDatabase
from golemapp import start, OptNode


@ci_skip
@patch('twisted.internet.iocpreactor', create=True)
@patch('golem.core.common.config_logging')
class TestNode(TestWithDatabase):
    def setUp(self):
        super(TestNode, self).setUp()
        self.args = ['--datadir', self.path]

    def tearDown(self):
        super(TestNode, self).tearDown()

    @patch('twisted.internet.reactor', create=True)
    def test_should_help_message_be_printed_out(self, mock_reactor, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--help'], catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)
        self.assertTrue(return_value.output.startswith('Usage'))
        mock_reactor.run.assert_not_called()

    @patch('twisted.internet.reactor', create=True)
    def test_wrong_option_should_fail(self, mock_reactor, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--blargh'],
                                     catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue(return_value.output.startswith('Error'))
        mock_reactor.run.assert_not_called()

    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.OptNode')
    def test_node_address_should_be_passed_to_node(self, mock_node, *_):
        node_address = '1.2.3.4'

        runner = CliRunner()
        args = self.args + ['--node-address', node_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        self.assertEqual(len(mock_node.mock_calls), 2)
        init_call = mock_node.mock_calls[0]
        self.assertEqual(init_call[0], '')  # call name == '' for __init__ call
        init_call_args = init_call[1]
        init_call_kwargs = init_call[2]
        self.assertEqual(init_call_args, ())
        self.assertEqual(init_call_kwargs.get('node_address'), node_address)

    @patch('golem.node.Node.run')
    @patch('golem.docker.manager.DockerManager')
    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.delete_reactor')
    @patch('golem.node.Client')
    def test_node_address_should_be_passed_to_client(self, mock_client, *_):
        """Test that with '--node-address <addr>' arg the client is started with
        a 'config_desc' arg such that 'config_desc.node_address' is <addr>.
        """
        node_address = '1.2.3.4'
        runner = CliRunner()
        args = self.args + ['--node-address', node_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_client.assert_called_with(datadir=self.path,
                                       geth_address=None,
                                       node_address=node_address,
                                       start_geth=False,
                                       start_geth_port=None,
                                       transaction_system=True,
                                       use_docker_machine_manager=True,
                                       use_monitor=True)

    def test_invalid_node_address_should_fail(self, *_):
        runner = CliRunner()
        args = self.args + ['--node-address', '10.30.10.2555']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Invalid value for "--node-address"', return_value.output)

    def test_missing_node_address_should_fail(self, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, self.args + ['--node-address'])
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Error: --node-address', return_value.output)

    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.OptNode')
    def test_geth_address_should_be_passed_to_node(self, mock_node, *_):
        geth_address = 'http://3.14.15.92:6535'

        runner = CliRunner()
        args = self.args + ['--geth-address', geth_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_node.assert_called_with(datadir=self.path,
                                     geth_address=geth_address,
                                     node_address=None,
                                     peers=[],
                                     start_geth=False,
                                     start_geth_port=None,
                                     transaction_system=True,
                                     use_monitor=True)

    @patch('golem.node.Node.run')
    @patch('golem.docker.manager.DockerManager')
    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.delete_reactor')
    @patch('golem.node.Client')
    def test_geth_address_should_be_passed_to_client(self, mock_client, *_):
        geth_address = 'http://3.14.15.92:6535'
        runner = CliRunner()
        args = self.args + ['--geth-address', geth_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_client.assert_called_with(datadir=self.path,
                                       geth_address=geth_address,
                                       node_address=None,
                                       start_geth=False,
                                       start_geth_port=None,
                                       transaction_system=True,
                                       use_docker_machine_manager=True,
                                       use_monitor=True)

    def test_geth_address_wo_http_should_fail(self, *_):
        runner = CliRunner()
        geth_addr = '3.14.15.92'
        args = self.args + ['--geth-address', geth_addr]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Invalid value for "--geth-address"', return_value.output)
        self.assertIn('Address without http:// prefix', return_value.output)
        self.assertIn(geth_addr, return_value.output)

    def test_geth_address_w_wrong_prefix_should_fail(self, *_):
        runner = CliRunner()
        geth_addr = 'https://3.14.15.92'
        args = self.args + ['--geth-address', geth_addr]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Invalid value for "--geth-address"', return_value.output)
        self.assertIn('Address without http:// prefix', return_value.output)
        self.assertIn(geth_addr, return_value.output)

    def test_geth_address_wo_port_should_fail(self, *_):
        runner = CliRunner()
        geth_addr = 'http://3.14.15.92'
        args = self.args + ['--geth-address', geth_addr]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Invalid value for "--geth-address"', return_value.output)
        self.assertIn('Invalid network address specified', return_value.output)
        self.assertIn(geth_addr[len(geth_addr):], return_value.output)

    def test_geth_address_missing_should_fail(self, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, self.args + ['--geth-address'])
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Error: --geth-address', return_value.output)

    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.OptNode')
    def test_start_geth_should_be_passed_to_node(self, mock_node, *_):
        runner = CliRunner()
        args = self.args + ['--start-geth']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_node.assert_called_with(datadir=self.path,
                                     geth_address=None,
                                     node_address=None,
                                     peers=[],
                                     start_geth=True,
                                     start_geth_port=None,
                                     transaction_system=True,
                                     use_monitor=True)

    @patch('golem.node.Node.run')
    @patch('golem.docker.manager.DockerManager')
    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.delete_reactor')
    @patch('golem.node.Client')
    def test_start_geth_should_be_passed_to_client(self, mock_client, *_):
        runner = CliRunner()
        args = self.args + ['--start-geth']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_client.assert_called_with(datadir=self.path,
                                       geth_address=None,
                                       node_address=None,
                                       start_geth=True,
                                       start_geth_port=None,
                                       transaction_system=True,
                                       use_docker_machine_manager=True,
                                       use_monitor=True)

    def test_start_geth_port_wo_param_should_fail(self, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, self.args + ['--start-geth-port'])
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Error: --start-geth-port option requires an argument',
                      return_value.output)

    def test_start_geth_port_wo_start_geth_should_fail(self, *_):
        runner = CliRunner()
        args = self.args + ['--start-geth-port', 1]
        return_value = runner.invoke(start, args)
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('it makes sense only together with --start-geth',
                      return_value.output)

    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.OptNode')
    def test_start_geth_port_should_be_passed_to_node(self, mock_node, *_):
        port = 27182

        runner = CliRunner()
        args = self.args + ['--start-geth', '--start-geth-port', port]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_node.assert_called_with(datadir=self.path,
                                     geth_address=None,
                                     node_address=None,
                                     peers=[],
                                     start_geth=True,
                                     start_geth_port=port,
                                     transaction_system=True,
                                     use_monitor=True)

    @patch('golem.node.Node.run')
    @patch('golem.docker.manager.DockerManager')
    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.delete_reactor')
    @patch('golem.node.Client')
    def test_start_geth_port_should_be_passed_to_client(self, mock_client, *_):
        port = 27182

        runner = CliRunner()
        args = self.args + ['--start-geth-port', port, '--start-geth']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_client.assert_called_with(datadir=self.path,
                                       geth_address=None,
                                       node_address=None,
                                       start_geth=True,
                                       start_geth_port=port,
                                       transaction_system=True,
                                       use_docker_machine_manager=True,
                                       use_monitor=True)

    @patch('golemapp.OptNode')
    def test_single_peer(self, mock_node, *_):
        mock_node.return_value = mock_node
        addr1 = '10.30.10.216:40111'

        runner = CliRunner()
        return_value = runner.invoke(start, self.args + ['--peer', addr1],
                                     catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)
        # TODO: check peer == [addr1]
        mock_node.run.assert_called_once_with(use_rpc=True)

    @patch('golemapp.OptNode')
    def test_many_peers(self, mock_node, *_):
        mock_node.return_value = mock_node
        addr1 = '10.30.10.216:40111'
        addr2 = '10.30.10.214:3333'

        runner = CliRunner()
        args = self.args + ['--peer', addr1, '--peer', addr2]
        return_value = runner.invoke(start, args, catch_exceptions=False)

        self.assertEqual(return_value.exit_code, 0)
        # TODO: check peer == [addr1, addr2]
        mock_node.run.assert_called_once_with(use_rpc=True)

    @patch('golemapp.OptNode')
    def test_bad_peer(self, *_):
        addr1 = '10.30.10.216:40111'
        runner = CliRunner()
        args = self.args + ['--peer', addr1, '--peer', 'bla']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue('Invalid peer address' in return_value.output)

    @patch('golemapp.OptNode')
    def test_peers(self, mock_node, *_):
        mock_node.return_value = mock_node
        runner = CliRunner()
        return_value = runner.invoke(
            start, self.args + [
                '--peer', '10.30.10.216:40111',
                '--peer', '[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443',
                '--peer', '[::ffff:0:0:0]:96'
            ], catch_exceptions=False
        )
        self.assertEqual(return_value.exit_code, 0)
        # TODO: check peer == [addrs...]
        mock_node.run.assert_called_with(use_rpc=True)

    @patch('golemapp.OptNode')
    def test_rpc_address(self, *_):
        runner = CliRunner()

        ok_addresses = [
            ['--rpc-address', '10.30.10.216:61000'],
            ['--rpc-address', '[::ffff:0:0:0]:96'],
            ['--rpc-address', '[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443']
        ]
        bad_addresses = [
            ['--rpc-address', '10.30.10.216:91000'],
            ['--rpc-address', '[::ffff:0:0:0]:96999']
        ]
        skip_addresses = [
            ['--rpc-address', '']
        ]

        for address in ok_addresses + skip_addresses:
            return_value = runner.invoke(
                start, self.args + address,
                catch_exceptions=False
            )
            assert return_value.exit_code == 0

        for address in bad_addresses:
            return_value = runner.invoke(
                start, self.args + address,
                catch_exceptions=False
            )
            assert return_value.exit_code != 0


def mock_async_callback(call):
    def callback(result):
        return call(result)

    return callback


@patch('golem.node.async_callback', mock_async_callback)
@patch('golem.rpc.router.CrossbarRouter', create=True)
@patch('twisted.internet.reactor', create=True)
class TestOptNode(TempDirFixture):

    def tearDown(self):
        if hasattr(self, 'node'):
            self.node.client.quit()
        super(TestOptNode, self).tearDown()

    def test_start_rpc_router(self, reactor, router, *_):
        from golem.rpc.session import WebSocketAddress

        self.node = OptNode(self.path, use_docker_machine_manager=False,
                            rpc_address='127.0.0.1', rpc_port=12345)

        config = self.node.client.config_desc

        router.return_value = router
        router.address = WebSocketAddress(config.rpc_address,
                                          config.rpc_port,
                                          realm='test_realm')
        self.node._setup_rpc()
        self.node._start_rpc_router()

        assert self.node.rpc_router
        assert self.node.rpc_router.start.called
        assert reactor.addSystemEventTrigger.called

    @patch('golem.docker.image.DockerImage')
    def test_setup_without_docker(self, *_):
        self.parsed_peer = OptNode.parse_peer(None, None, ['10.0.0.10:40104'])
        self.node = OptNode(self.path, use_docker_machine_manager=False,
                            peers=self.parsed_peer)

        self.node._setup_docker = Mock()
        self.node.client.connect = Mock()
        self.node.client.start = Mock()
        self.node.client.environments_manager = Mock()
        self.node.run()

        assert self.node.client.start.called
        assert self.node._apps_manager is not None
        assert not self.node._setup_docker.called
        self.node.client.connect.assert_called_with(self.parsed_peer[0])

    @patch('golem.docker.image.DockerImage')
    def test_setup_with_docker(self, docker_manager, *_):
        docker_manager.return_value = docker_manager

        self.node = OptNode(self.path, use_docker_machine_manager=True)

        self.node._setup_docker = Mock()
        self.node.client.connect = Mock()
        self.node.client.start = Mock()
        self.node.client.environments_manager = Mock()
        self.node.run()

        assert self.node.client.start.called
        assert self.node._apps_manager is not None
        assert self.node._setup_docker.called
