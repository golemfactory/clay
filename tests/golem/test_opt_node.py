from os import path
from unittest.mock import patch, Mock, ANY

from click.testing import CliRunner
from twisted.internet.defer import Deferred

import golem.argsparser as argsparser
from golem.appconfig import AppConfig
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from golem.tools.testwithdatabase import TestWithDatabase
from golemapp import start, Node


@ci_skip
@patch('twisted.internet.iocpreactor', create=True)
@patch('twisted.internet.kqreactor', create=True)
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

    @patch('twisted.internet.reactor', create=True)
    def test_wrong_option_should_fail(self, mock_reactor, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--blargh'],
                                     catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue(return_value.output.startswith('Error'))

    @patch('twisted.internet.reactor', create=True)
    @patch('golemapp.Node')
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
        self.assertEqual(
            init_call_kwargs.get('config_desc').node_address,
            node_address,
        )

    @patch('golem.node.Client')
    def test_cfg_and_keys_should_be_passed_to_client(self, mock_client, *_):
        # given
        cfg = ClientConfigDescriptor()
        cfg.node_address = '1.2.3.4'
        keys_auth = object()

        # when
        node = Node(
            datadir=self.path,
            app_config=Mock(),
            config_desc=cfg)

        node._client_factory(keys_auth)

        # then
        mock_client.assert_called_with(datadir=self.path,
                                       app_config=ANY,
                                       config_desc=cfg,
                                       keys_auth=keys_auth,
                                       mainnet=False,
                                       geth_address=None,
                                       start_geth=False,
                                       start_geth_port=None,
                                       use_docker_manager=True,
                                       use_concent=False,
                                       use_monitor=False)
        self.assertEqual(
            cfg.node_address,
            mock_client.mock_calls[0][2]['config_desc'].node_address,
        )

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
    @patch('golemapp.Node')
    def test_geth_address_should_be_passed_to_node(self, mock_node, *_):
        geth_address = 'http://3.14.15.92:6535'

        runner = CliRunner()
        args = self.args + ['--geth-address', geth_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_node.assert_called_with(datadir=path.join(self.path, 'rinkeby'),
                                     app_config=ANY,
                                     config_desc=ANY,
                                     mainnet=False,
                                     geth_address=geth_address,
                                     peers=[],
                                     start_geth=False,
                                     start_geth_port=None,
                                     use_concent=False,
                                     use_monitor=True)

    @patch('golem.node.Client')
    def test_geth_address_should_be_passed_to_client(self, mock_client, *_):
        # given
        geth_address = 'http://3.14.15.92:6535'

        # when
        node = Node(
            datadir=self.path,
            app_config=Mock(),
            config_desc=Mock(),
            geth_address=geth_address)

        node._client_factory(None)

        # then
        mock_client.assert_called_with(datadir=self.path,
                                       app_config=ANY,
                                       config_desc=ANY,
                                       keys_auth=None,
                                       mainnet=False,
                                       geth_address=geth_address,
                                       start_geth=False,
                                       start_geth_port=None,
                                       use_docker_manager=True,
                                       use_concent=False,
                                       use_monitor=False)

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
    @patch('golemapp.Node')
    def test_start_geth_should_be_passed_to_node(self, mock_node, *_):
        runner = CliRunner()
        args = self.args + ['--start-geth']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_node.assert_called_with(datadir=path.join(self.path, 'rinkeby'),
                                     app_config=ANY,
                                     config_desc=ANY,
                                     mainnet=False,
                                     geth_address=None,
                                     peers=[],
                                     start_geth=True,
                                     start_geth_port=None,
                                     use_concent=False,
                                     use_monitor=True)

    @patch('golem.node.Client')
    def test_start_geth_should_be_passed_to_client(self, mock_client, *_):
        # when
        node = Node(
            datadir=self.path,
            app_config=Mock(),
            config_desc=Mock(),
            start_geth=True)

        node._client_factory(None)

        # then
        mock_client.assert_called_with(datadir=self.path,
                                       app_config=ANY,
                                       config_desc=ANY,
                                       keys_auth=None,
                                       mainnet=False,
                                       geth_address=None,
                                       start_geth=True,
                                       start_geth_port=None,
                                       use_docker_manager=True,
                                       use_concent=False,
                                       use_monitor=False)

    @patch('golemapp.Node')
    def test_mainnet_should_be_passed_to_node(self, mock_node, *_):
        # given
        args = self.args + ['--mainnet']

        # when
        runner = CliRunner()
        return_value = runner.invoke(start, args)

        # then
        assert return_value.exit_code == 0
        mock_node.assert_called_with(datadir=path.join(self.path, 'mainnet'),
                                     app_config=ANY,
                                     config_desc=ANY,
                                     geth_address=None,
                                     peers=[],
                                     start_geth=False,
                                     start_geth_port=None,
                                     use_concent=False,
                                     use_monitor=True,
                                     mainnet=True)

    @patch('golem.node.Client')
    def test_mainnet_should_be_passed_to_client(self, mock_client, *_):
        # when
        node = Node(
            datadir=self.path,
            app_config=Mock(),
            config_desc=Mock(),
            mainnet=True)

        node._client_factory(None)

        # then
        mock_client.assert_called_with(datadir=self.path,
                                       app_config=ANY,
                                       config_desc=ANY,
                                       keys_auth=None,
                                       geth_address=None,
                                       start_geth=False,
                                       start_geth_port=None,
                                       use_docker_manager=True,
                                       use_concent=False,
                                       use_monitor=False,
                                       mainnet=True)

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
    @patch('golemapp.Node')
    def test_start_geth_port_should_be_passed_to_node(self, mock_node, *_):
        port = 27182

        runner = CliRunner()
        args = self.args + ['--start-geth', '--start-geth-port', port]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_node.assert_called_with(datadir=path.join(self.path, 'rinkeby'),
                                     app_config=ANY,
                                     config_desc=ANY,
                                     mainnet=False,
                                     geth_address=None,
                                     peers=[],
                                     start_geth=True,
                                     start_geth_port=port,
                                     use_concent=False,
                                     use_monitor=True)

    @patch('golem.node.Client')
    def test_start_geth_port_should_be_passed_to_client(self, mock_client, *_):
        # given
        port = 27182

        # when
        node = Node(
            datadir=self.path,
            app_config=Mock(),
            config_desc=Mock(),
            start_geth=True,
            start_geth_port=port)

        node._client_factory(None)

        # then
        mock_client.assert_called_with(datadir=self.path,
                                       app_config=ANY,
                                       config_desc=ANY,
                                       keys_auth=None,
                                       mainnet=False,
                                       geth_address=None,
                                       start_geth=True,
                                       start_geth_port=port,
                                       use_docker_manager=True,
                                       use_concent=False,
                                       use_monitor=False)

    @patch('golemapp.Node')
    def test_single_peer(self, mock_node, *_):
        mock_node.return_value = mock_node
        addr1 = '10.30.10.216:40111'

        runner = CliRunner()
        return_value = runner.invoke(start, self.args + ['--peer', addr1],
                                     catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)
        # TODO: check peer == [addr1]

    @patch('golemapp.Node')
    def test_many_peers(self, mock_node, *_):
        mock_node.return_value = mock_node
        addr1 = '10.30.10.216:40111'
        addr2 = '10.30.10.214:3333'

        runner = CliRunner()
        args = self.args + ['--peer', addr1, '--peer', addr2]
        return_value = runner.invoke(start, args, catch_exceptions=False)

        self.assertEqual(return_value.exit_code, 0)
        # TODO: check peer == [addr1, addr2]

    @patch('golemapp.Node')
    def test_bad_peer(self, *_):
        addr1 = '10.30.10.216:40111'
        runner = CliRunner()
        args = self.args + ['--peer', addr1, '--peer', 'bla']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue('Invalid peer address' in return_value.output)

    @patch('golemapp.Node')
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

    @patch('golemapp.Node')
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
            AppConfig._AppConfig__loaded_configs = set()
            return_value = runner.invoke(
                start, self.args + address,
                catch_exceptions=False
            )
            assert return_value.exit_code == 0

        for address in bad_addresses:
            AppConfig._AppConfig__loaded_configs = set()
            return_value = runner.invoke(
                start, self.args + address,
                catch_exceptions=False
            )
            assert return_value.exit_code != 0


def mock_async_run(req, success=None, error=None):
    deferred = Deferred()
    if success:
        deferred.addCallback(success)
    if error:
        deferred.addErrback(error)

    try:
        result = req.method(*req.args, **req.kwargs)
    except Exception as e:  # pylint: disable=broad-except
        deferred.errback(e)
    else:
        deferred.callback(result)

    return deferred


def done_deferred(*_):
    deferred = Deferred()
    deferred.callback(True)
    return deferred


def chain_function(_, fn, *args, **kwargs):
    result = fn(*args, **kwargs)
    deferred = Deferred()
    deferred.callback(result)
    return deferred


@patch('golem.node.Node._start_keys_auth')
@patch('golem.node.Node._start_docker')
@patch('golem.node.async_run', mock_async_run)
@patch('golem.node.chain_function', chain_function)
@patch('golem.node.threads.deferToThread', done_deferred)
@patch('golem.node.CrossbarRouter', Mock(_start_node=done_deferred))
@patch('golem.node.Session', Mock(connect=done_deferred))
@patch('golem.node.gatherResults')
@patch('twisted.internet.reactor', create=True)
class TestOptNode(TempDirFixture):

    def tearDown(self):
        if self.node.client:
            self.node.client.quit()
        super().tearDown()

    def test_start_rpc_router(self, reactor, *_):
        # given
        config_desc = ClientConfigDescriptor()
        config_desc.rpc_address = '127.0.0.1'
        config_desc.rpc_port = 12345

        # when
        self.node = Node(datadir=self.path,
                         app_config=Mock(),
                         config_desc=config_desc,
                         use_docker_manager=False)

        self.node.start()

        # then
        assert self.node.rpc_router
        assert self.node.rpc_router._start_node.called  # noqa pylint: disable=no-member
        assert reactor.addSystemEventTrigger.called
        assert reactor.addSystemEventTrigger.call_args[0] == (
            'before', 'shutdown', self.node.rpc_router.stop)

    @patch('golem.client.EthereumTransactionSystem')
    def test_start_creates_client(self, _ets, reactor, mock_gather_results, *_):
        # given
        keys_auth = Mock()
        config_descriptor = ClientConfigDescriptor()

        mock_gather_results.return_value = mock_gather_results
        mock_gather_results.addCallbacks.side_effect = \
            lambda callback, _: callback([keys_auth, None])

        # when
        self.node = Node(datadir=self.path,
                         app_config=Mock(),
                         config_desc=config_descriptor,
                         use_docker_manager=False)
        self.node.start()

        # then
        assert self.node.client
        assert self.node.client.datadir == self.path
        assert self.node.client.config_desc == config_descriptor
        assert self.node.client.keys_auth == keys_auth
        assert reactor.addSystemEventTrigger.call_count == 2
        assert reactor.addSystemEventTrigger.call_args_list[0][0] == (
            'before', 'shutdown', self.node.rpc_router.stop)
        assert reactor.addSystemEventTrigger.call_args_list[1][0] == (
            'before', 'shutdown', self.node.client.quit)

    @patch('golem.client.EthereumTransactionSystem')
    @patch('golem.node.Node._run')
    def test_start_creates_client_and_calls_run(
            self,
            mock_run,
            _ets,
            reactor,
            mock_gather_results,
            mock_session,
            *_):
        # given
        mock_gather_results.return_value = mock_gather_results
        mock_gather_results.addCallbacks.side_effect = \
            lambda callback, _: callback([Mock(), None])

        mock_session.return_value = mock_session
        mock_session.connect.return_value = mock_session
        mock_session.addCallbacks.side_effect = \
            lambda callback, _: callback(None)

        # when
        self.node = Node(datadir=self.path,
                         app_config=Mock(),
                         config_desc=(ClientConfigDescriptor()),
                         use_docker_manager=False)
        self.node.start()

        # then
        assert self.node.client
        assert self.node.rpc_session
        assert self.node.client.rpc_publisher
        assert self.node.client.rpc_publisher.session == self.node.rpc_session
        assert self.node.rpc_session.connect.called  # pylint: disable=no-member
        assert mock_run.called
        assert reactor.addSystemEventTrigger.call_count == 2

    def test_start_starts_client(
            self, reactor, mock_gather_results, mock_session, *_):

        # given
        mock_gather_results.return_value = mock_gather_results
        mock_gather_results.addCallbacks.side_effect = \
            lambda callback, _: callback([Mock(), None])

        mock_session.return_value = mock_session
        mock_session.connect.return_value = mock_session
        mock_session.addCallbacks.side_effect = \
            lambda callback, _: callback(None)

        parsed_peer = argsparser.parse_peer(
            None,
            None,
            ['10.0.0.10:40104'],
        )

        # when
        self.node = Node(datadir=self.path,
                         app_config=Mock(),
                         config_desc=ClientConfigDescriptor(),
                         peers=parsed_peer,
                         use_docker_manager=False)

        self.node._client_factory = Mock()
        self.node._setup_apps = Mock()

        self.node.start()

        # then
        assert self.node._setup_apps.called
        assert self.node.client.sync.called
        assert self.node.client.start.call_count == 1
        self.node.client.connect.assert_called_with(parsed_peer[0])
        assert reactor.addSystemEventTrigger.call_count == 2
