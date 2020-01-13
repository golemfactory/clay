# pylint: disable=protected-access
from os import path
import unittest
from unittest.mock import (
    ANY,
    call,
    MagicMock,
    Mock,
    patch,
)

from click.testing import CliRunner
from twisted.internet.defer import Deferred, succeed, FirstError
from twisted.python.failure import Failure

import golem.argsparser as argsparser
from golem.appconfig import AppConfig
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core import variables
from golem.network.transport.tcpnetwork_helpers import SocketAddress
from golem.node import Node, ShutdownResponse
from golem.report import Component, Stage
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from golem.tools.testwithdatabase import TestWithDatabase
from golemapp import start
from tests.golem.config.utils import mock_config

concent_disabled = variables.CONCENT_CHOICES['disabled']


# pylint: disable=too-many-public-methods
@ci_skip
@patch('twisted.internet.asyncioreactor', Mock(), create=True)
@patch('twisted.internet.reactor', Mock(), create=True)
@patch('golem.core.common.config_logging')
class TestNode(TestWithDatabase):
    def setUp(self):
        super(TestNode, self).setUp()
        self.args = ['--datadir', self.path]
        config_desc = ClientConfigDescriptor()
        config_desc.rpc_address = '127.0.0.1'
        config_desc.rpc_port = 12345

        self.node_kwargs = {
            'datadir': self.path,
            'app_config': Mock(),
            'config_desc': config_desc,
            'use_docker_manager': True,
            'concent_variant': concent_disabled,
        }

    @patch('twisted.internet.reactor', create=True)
    def test_should_help_message_be_printed_out(self, _mock_reactor, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--help'], catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)
        self.assertTrue(return_value.output.startswith('Usage'))

    @patch('twisted.internet.reactor', create=True)
    def test_wrong_option_should_fail(self, _mock_reactor, *_):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--blargh'],
                                     catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue(return_value.output.startswith('Usage'))

    @patch('twisted.internet.reactor', create=True)
    @patch('golem.node.Node')
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
        # when
        keys_auth = object()
        node = Node(**self.node_kwargs)
        node._client_factory(keys_auth)

        # then
        mock_client.assert_called_with(datadir=self.path,
                                       app_config=ANY,
                                       config_desc=self.node_kwargs[
                                           'config_desc'
                                       ],
                                       keys_auth=keys_auth,
                                       database=ANY,
                                       transaction_system=ANY,
                                       use_docker_manager=True,
                                       concent_variant=concent_disabled,
                                       use_monitor=False,
                                       apps_manager=ANY,
                                       task_finished_cb=node._try_shutdown,
                                       update_hw_preset=node.upsert_hw_preset)
        self.assertEqual(
            self.node_kwargs['config_desc'].node_address,
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
    @patch('golem.node.Node')
    def test_geth_address_should_be_passed_to_node(self, mock_node, *_):
        geth_address = 'https://3.14.15.92:6535'

        runner = CliRunner()
        args = self.args + ['--geth-address', geth_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)

        mock_node.assert_called_with(datadir=path.join(self.path, 'rinkeby'),
                                     app_config=ANY,
                                     config_desc=ANY,
                                     geth_address=geth_address,
                                     peers=[],
                                     concent_variant=variables.CONCENT_CHOICES[
                                         'test'
                                     ],
                                     use_monitor=None,
                                     use_talkback=None,
                                     password=None)

    @patch('golem.node.TransactionSystem')
    def test_geth_address_should_be_passed_to_transaction_system(
            self,
            mock_ts,
            *_):
        # given
        geth_address = 'https://3.14.15.92:6535'

        # when
        Node(**self.node_kwargs, geth_address=geth_address)

        # then
        self.assertTrue(mock_ts.called)
        self.assertEqual([geth_address], mock_ts.call_args[0][1].NODE_LIST)

    def test_geth_address_wo_http_should_fail(self, *_):
        runner = CliRunner()
        geth_addr = '3.14.15.92'
        args = self.args + ['--geth-address', geth_addr]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Invalid value for "--geth-address"', return_value.output)
        self.assertIn('Address without https:// prefix', return_value.output)
        self.assertIn(geth_addr, return_value.output)

    def test_geth_address_w_wrong_prefix_should_fail(self, *_):
        runner = CliRunner()
        geth_addr = 'http://3.14.15.92'
        args = self.args + ['--geth-address', geth_addr]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertIn('Invalid value for "--geth-address"', return_value.output)
        self.assertIn('Address without https:// prefix', return_value.output)
        self.assertIn(geth_addr, return_value.output)

    def test_geth_address_wo_port_should_fail(self, *_):
        runner = CliRunner()
        geth_addr = 'https://3.14.15.92'
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

    @patch('golem.node.Node')
    def test_mainnet_should_be_passed_to_node(self, mock_node, *_):

        # given
        args = self.args + ['--mainnet']

        # when
        runner = CliRunner()

        with mock_config():
            return_value = runner.invoke(start, args)

        # then
        assert return_value.exit_code == 0
        mock_node.assert_called_with(datadir=path.join(self.path, 'mainnet'),
                                     app_config=ANY,
                                     config_desc=ANY,
                                     geth_address=None,
                                     peers=[],
                                     concent_variant=variables.CONCENT_CHOICES[
                                         'main'
                                     ],
                                     use_monitor=None,
                                     use_talkback=None,
                                     password=None)

    @patch('golem.node.Client')
    def test_mainnet_should_be_passed_to_client(self, mock_client, *_):
        # when
        with mock_config():
            node = Node(**self.node_kwargs)
            node._client_factory(None)

        # then
        mock_client.assert_called_with(datadir=self.path,
                                       app_config=ANY,
                                       config_desc=ANY,
                                       keys_auth=None,
                                       database=ANY,
                                       transaction_system=ANY,
                                       use_docker_manager=True,
                                       concent_variant=concent_disabled,
                                       use_monitor=False,
                                       apps_manager=ANY,
                                       task_finished_cb=node._try_shutdown,
                                       update_hw_preset=node.upsert_hw_preset)

    @patch('golem.node.Node')
    def test_net_testnet_should_be_passed_to_node(self, mock_node, *_):

        # given
        args = self.args + ['--net', 'testnet']

        # when
        runner = CliRunner()

        with mock_config():
            return_value = runner.invoke(start, args)

            from golem.config.active import EthereumConfig
            assert EthereumConfig().IS_MAINNET is False

        # then
        assert return_value.exit_code == 0
        mock_node.assert_called_with(
            datadir=path.join(self.path, 'rinkeby'),
            app_config=ANY,
            config_desc=ANY,
            geth_address=None,
            peers=[],
            concent_variant=variables.CONCENT_CHOICES['test'],
            use_monitor=None,
            use_talkback=None,
            password=None
        )

    @patch('golem.node.Node')
    def test_net_mainnet_should_be_passed_to_node(self, mock_node, *_):

        # given
        args = self.args + ['--net', 'mainnet']

        # when
        runner = CliRunner()

        with mock_config():
            return_value = runner.invoke(start, args)

            from golem.config.active import EthereumConfig
            assert EthereumConfig().IS_MAINNET is True

        # then
        assert return_value.exit_code == 0
        mock_node.assert_called_with(datadir=path.join(self.path, 'mainnet'),
                                     app_config=ANY,
                                     config_desc=ANY,
                                     geth_address=None,
                                     peers=[],
                                     concent_variant=variables.CONCENT_CHOICES[
                                         'main'
                                     ],
                                     use_monitor=None,
                                     use_talkback=None,
                                     password=None)

    @patch('golem.node.Node')
    def test_config_change(self, *_):

        def compare_config(m):
            from golem.config import active as a

            def objattrs(obj):
                return [(a, getattr(obj, a))
                        for a in dir(obj) if not a.startswith('__')]

            assert a.DATA_DIR == m.DATA_DIR
            assert objattrs(a.EthereumConfig()) == objattrs(m.EthereumConfig())
            assert a.P2P_SEEDS == m.P2P_SEEDS
            assert a.PROTOCOL_CONST.ID == m.PROTOCOL_CONST.ID
            assert a.APP_MANAGER_CONFIG_FILES == m.APP_MANAGER_CONFIG_FILES

        with mock_config():
            args = self.args + ['--net', 'mainnet']

            runner = CliRunner()
            runner.invoke(start, args)

            from golem.config.environments import mainnet
            compare_config(mainnet)

        with mock_config():
            args = self.args + ['--net', 'testnet']

            runner = CliRunner()
            runner.invoke(start, args)

            from golem.config.environments import testnet
            compare_config(testnet)

    @patch('golem.node.Node')
    def test_single_peer(self, mock_node: MagicMock, *_):
        host, port = '10.30.10.216', 40111

        runner = CliRunner()
        args = self.args + ['--peer', '{}:{}'.format(host, port)]
        return_value = runner.invoke(start, args, catch_exceptions=False)

        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_called_once()
        peers = mock_node.call_args[1].get('peers')
        self.assertEqual(peers, [SocketAddress(host, port)])

    @patch('golem.node.Node')
    def test_many_peers(self, mock_node: MagicMock, *_):
        host1, port1 = '10.30.10.216', 40111
        host2, port2 = '10.30.10.214', 3333

        runner = CliRunner()
        args = self.args + [
            '--peer', '{}:{}'.format(host1, port1),
            '--peer', '{}:{}'.format(host2, port2)
        ]
        return_value = runner.invoke(start, args, catch_exceptions=False)

        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_called_once()
        peers = mock_node.call_args[1].get('peers')
        self.assertEqual(peers, [
            SocketAddress(host1, port1),
            SocketAddress(host2, port2)
        ])

    @patch('golem.node.Node')
    def test_bad_peer(self, mock_node: MagicMock, *_):
        addr1 = '10.30.10.216:40111'

        runner = CliRunner()
        args = self.args + ['--peer', addr1, '--peer', 'bla']
        return_value = runner.invoke(start, args, catch_exceptions=False)

        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue('Invalid peer address' in return_value.output)
        mock_node.assert_not_called()

    @patch('golem.node.Node')
    def test_peers(self, mock_node: MagicMock, *_):
        host1, port1 = '10.30.10.216', 40111
        host2, port2 = '2001:db8:85a3:8d3:1319:8a2e:370:7348', 443
        host3, port3 = '::ffff:0:0:0', 96

        runner = CliRunner()
        args = self.args + [
            '--peer', '{}:{}'.format(host1, port1),
            '--peer', '[{}]:{}'.format(host2, port2),
            '--peer', '[{}]:{}'.format(host3, port3)
        ]
        return_value = runner.invoke(start, args, catch_exceptions=False)

        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_called_once()
        peers = mock_node.call_args[1].get('peers')
        self.assertEqual(peers, [
            SocketAddress(host1, port1),
            SocketAddress(host2, port2),
            SocketAddress(host3, port3)
        ])

    @patch('golem.node.Node')
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

    @patch('golem.terms.TermsOfUse.are_accepted', return_value=object())
    def test_are_terms_accepted(self, accepted, *_):
        self.assertEqual(Node.are_terms_accepted(), accepted.return_value)

    @patch('golem.terms.TermsOfUse.accept')
    def test_accept_terms(self, accept, *_):
        node = Mock()

        Node.accept_terms(node)
        accept.assert_called_once_with()

        assert not isinstance(node._use_monitor, bool)
        assert not isinstance(node._use_talkback, bool)
        assert node._app_config.change_config.called

    @patch('golem.terms.TermsOfUse.accept')
    def test_accept_terms_monitor_arg(self, accept, *_):
        node = Mock()

        Node.accept_terms(node, enable_monitor=True)
        accept.assert_called_once_with()

        assert node._use_monitor is True
        assert not isinstance(node._use_talkback, bool)
        assert node._app_config.change_config.called

    @patch('golem.terms.TermsOfUse.accept')
    def test_accept_terms_talkback_arg(self, accept, *_):
        node = Mock()

        Node.accept_terms(node, enable_talkback=False)
        accept.assert_called_once_with()

        assert not isinstance(node._use_monitor, bool)
        assert node._use_talkback is False
        assert node._app_config.change_config.called

    @patch('golem.terms.TermsOfUse.show', return_value=object())
    def test_show_terms(self, show, *_):
        self.assertEqual(Node.show_terms(), show.return_value)


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


def done_deferred(f, *args, **kwargs):
    return succeed(f(*args, **kwargs))


def chain_function(_, fn, *args, **kwargs):
    result = fn(*args, **kwargs)
    deferred = Deferred()
    deferred.callback(result)
    return deferred


def set_keys_auth(obj):
    obj._keys_auth = Mock(
        key_id='a'*32,
    )
    return succeed(None)


def call_now(fn, *args, **kwargs):
    fn(*args, **kwargs)


class MockThread:

    def __init__(self, target=None) -> None:
        self._target = target

    def start(self):
        self._target()

    @property
    def target(self):
        return self._target


@patch('golem.client.node_info_str')
@patch('golem.node.Node._start_keys_auth', set_keys_auth)
@patch('golem.core.golem_async.async_run', mock_async_run)
@patch('golem.node.chain_function', chain_function)
@patch('golem.node.threads.deferToThread', done_deferred)
@patch('golem.node.CrossbarRouter', Mock(_start_node=done_deferred))
@patch('golem.terms.TermsOfUse.are_accepted', return_value=True)
@patch('golem.core.golem_async.async_run')
@patch('golem.node.Session')
@patch('twisted.internet.reactor', create=True)
class TestOptNode(TempDirFixture):

    def setUp(self):
        super().setUp()
        self.node = None

        config_desc = ClientConfigDescriptor()
        config_desc.rpc_address = '127.0.0.1'
        config_desc.rpc_port = 12345

        self.node_kwargs = {
            'datadir': self.path,
            'app_config': Mock(),
            'config_desc': config_desc,
            'use_docker_manager': False,
            'concent_variant': variables.CONCENT_CHOICES['disabled'],
        }

    def tearDown(self):
        if self.node:
            if self.node.client:
                with patch('golem.task.taskserver.TaskServer.quit'):
                    self.node.client.quit()
            if self.node._db:
                self.node._db.close()

        super().tearDown()

    def assertAddSystemEvent(self, reactor):
        reactor.addSystemEventTrigger.assert_has_calls(
            [
                call('before', 'shutdown', self.node.rpc_router.stop),
                call('before', 'shutdown', self.node.client.quit),
            ],
        )

    def test_start_rpc_router(self, reactor, *_):
        # when
        self.node = Node(**self.node_kwargs)
        self.node._setup_client = Mock()
        self.node.start()

        # then
        assert self.node.rpc_router
        assert self.node.rpc_router.start.called  # noqa pylint: disable=no-member
        assert reactor.addSystemEventTrigger.called
        assert reactor.addSystemEventTrigger.call_args[0] == (
            'before', 'shutdown', self.node.rpc_router.stop)

    @patch('golem.node.DockerManager')
    def test_start_docker_mgr(self, *_):
        # when
        self.node_kwargs['use_docker_manager'] = True
        self.node = Node(**self.node_kwargs)
        self.node._setup_client = Mock()
        self.node.start()

        # then
        assert self.node._docker_manager
        assert self.node._docker_manager.check_environment.called  # noqa # pylint: disable=no-member
        assert self.node._docker_manager.apply_config.called  # noqa # pylint: disable=no-member

    @patch('golem.node.DockerManager')
    def test_not_start_docker_mgr(self, *_):
        # when
        self.node_kwargs['use_docker_manager'] = False
        self.node = Node(**self.node_kwargs)
        self.node._setup_client = Mock()
        self.node.start()

        # then
        assert not self.node._docker_manager

    @patch('golem.node.DockerManager')
    def test_start_docker_unavailable(self, mock_dm, *_):
        self.node_kwargs['use_docker_manager'] = True
        self.node = Node(**self.node_kwargs)
        setup_client_mock = Mock()
        self.node._setup_client = setup_client_mock
        # This needs to be wrapped in FirstError since the exception is raised
        # from a Deferred in gatherResults
        mock_dm.check_environment.side_effect = FirstError(
            Failure(EnvironmentError()), 0)

        with patch('golem.node.DockerManager.install', return_value=mock_dm):
            self.node.start()

        setup_client_mock.assert_not_called()
        self.node._docker_manager.apply_config.assert_not_called() # noqa # pylint: disable=no-member
        self.node._docker_manager.check_environment.assert_called() # noqa # pylint: disable=no-member

    @patch('golem.node.DockerManager')
    def test_start_docker_other_error(self, mock_dm, *_):
        self.node_kwargs['use_docker_manager'] = True
        self.node = Node(**self.node_kwargs)
        error_msg = 'just a test'
        mock_dm.check_environment.side_effect = FirstError(
            Failure(Exception(error_msg)), 0)

        with patch('golem.node.DockerManager.install', return_value=mock_dm), \
                self.assertLogs('golem.node', level='INFO') as logs:
            self.node.start()
            output = "\n".join(logs.output)

        assert error_msg in output

    @patch('golem.node.gatherResults')
    @patch('golem.node.TransactionSystem')
    def test_start_creates_client(self, _ets, mock_gather_results, reactor, *_):
        mock_gather_results.return_value = mock_gather_results
        mock_gather_results.addCallbacks.side_effect = \
            lambda callback, _: callback([])

        # when
        self.node = Node(**self.node_kwargs)
        with patch('golem.task.taskarchiver.TaskArchiver._dump_archive'):
            self.node.start()

        # then
        assert self.node.client
        assert self.node.client.datadir == self.path
        assert self.node.client.config_desc == self.node_kwargs['config_desc']
        self.assertAddSystemEvent(reactor)

    @patch('golem.node.gatherResults')
    @patch('golem.node.TransactionSystem')
    @patch('golem.node.Node._run')
    def test_start_creates_client_and_calls_run(
            self,
            mock_run,
            _ets,
            mock_gather_results,
            reactor,
            mock_session,
            async_run,
            *_):
        # given
        mock_gather_results.return_value = mock_gather_results
        mock_gather_results.addCallbacks.side_effect = \
            lambda callback, _: callback([Mock(), None])

        mock_session.return_value = mock_session
        mock_session.connect.return_value = mock_session
        mock_session.addCallbacks.side_effect = \
            lambda callback, _: callback(None)
        async_run.side_effect = mock_async_run

        # when
        self.node = Node(**self.node_kwargs)
        self.node.start()

        # then
        assert self.node.client
        assert self.node.rpc_session
        assert self.node.client.rpc_publisher
        assert self.node.client.rpc_publisher.session == self.node.rpc_session
        assert self.node.rpc_session.connect.called  # pylint: disable=no-member
        assert mock_run.called
        self.assertAddSystemEvent(reactor)

    @patch('golem.node.gatherResults')
    def test_start_starts_client(
            self, mock_gather_results, reactor, mock_session, async_run, *_):

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
        async_run.side_effect = mock_async_run

        # when
        self.node = Node(**self.node_kwargs,
                         peers=parsed_peer)

        self.node._client_factory = Mock()
        self.node._setup_apps = Mock()

        self.node.start()

        # then
        assert self.node._setup_apps.called
        assert self.node.client.sync.called
        assert self.node.client.start.call_count == 1
        self.node.client.connect.assert_called_with(parsed_peer[0])
        self.assertAddSystemEvent(reactor)

    @patch('golem.node.gatherResults')
    def test_start_prints_exception_message(self, *_):
        # given
        self.node = Node(**self.node_kwargs)
        self.node._start_rpc = lambda: succeed(None)
        self.node._check_terms = lambda: succeed(None)
        self.node._start_keys_auth = lambda: succeed(None)
        self.node._start_docker = lambda: succeed(None)

        msg = "setup client error message"

        def _setup_client(_):
            raise Exception(msg)
        self.node._setup_client = _setup_client

        # when
        with self.assertLogs('golem.node', level='INFO') as logs:
            self.node.start()
        output = "\n".join(logs.output)

        # then
        full_msg = \
            "ERROR:golem.node:Stopping because of " \
            f"'setup client' error: {msg}"
        assert full_msg in output

    def test_is_mainnet(self, *_):
        self.node = Node(**self.node_kwargs)
        assert not self.node.is_mainnet()

    @patch('golem.node.Session')
    def test_start_session(self, *_):
        self.node = Node(**self.node_kwargs)
        self.node.rpc_router = Mock()

        self.node._start_session()
        assert self.node.rpc_session.connect.called  # noqa # pylint: disable=no-member

    def test_start_session_failure(self, reactor, *_):
        self.node = Node(**self.node_kwargs)
        self.node.rpc_router = None

        assert isinstance(self.node._start_session().result, Failure)
        reactor.callFromThread.assert_called_with(reactor.stop)

    def test_error(self, reactor, *_):
        import functools
        reactor.running = True

        self.node = Node(**self.node_kwargs)

        error = self.node._error('any')
        assert not reactor.callFromThread.called
        assert isinstance(self.node._error('any'), functools.partial)

        error_result = error('error message')
        assert reactor.callFromThread.called
        assert error_result is None

    @patch('golem.node.Database')
    @patch('threading.Thread', MockThread)
    @patch('twisted.internet.reactor', create=True)
    def test_quit_mock(self, reactor, *_):
        reactor.running = False
        reactor.callFromThread = call_now

        node = Node.__new__(Node)

        setattr(node, '_reactor', reactor)
        setattr(node, '_docker_manager', Mock())
        setattr(node, 'client', None)

        node.quit()

        assert not node._reactor.stop.called

    @patch('golem.node.Database')
    @patch('threading.Thread', MockThread)
    @patch('twisted.internet.reactor', create=True)
    def test_quit(self, reactor, *_):
        reactor.running = True

        self.node = Node(**self.node_kwargs)
        self.node._reactor.callFromThread = call_now

        self.node.quit()
        assert self.node._reactor.stop.called

    @patch('golem.node.Database')
    @patch('threading.Thread', MockThread)
    @patch('twisted.internet.reactor', create=True)
    def test_graceful_shutdown_quit(self, reactor, *_):
        reactor.running = True

        self.node = Node(**self.node_kwargs)
        self.node.client = Mock()
        self.node._reactor.callFromThread = call_now
        self.node._is_task_in_progress = Mock(return_value=False)

        result = self.node.graceful_shutdown()
        assert result == ShutdownResponse.quit
        assert self.node._is_task_in_progress.called
        assert self.node._reactor.stop.called

    @patch('golem.node.StatusPublisher')
    def test_graceful_shutdown_off(self, publisher, *_):
        self.node_kwargs['config_desc'].in_shutdown = 1

        self.node = Node(**self.node_kwargs)
        self.node.quit = Mock()
        self.node.client = Mock()
        self.node._is_task_in_progress = Mock(return_value=False)

        result = self.node.graceful_shutdown()
        assert result == ShutdownResponse.off
        assert self.node.client.update_settings.called_with('in_shutdown', 0)
        assert self.node._is_task_in_progress.not_called
        assert self.node.quit.not_called
        publisher.publish.assert_called_with(
            Component.client, 'start', Stage.post)

    @patch('golem.node.StatusPublisher')
    def test_graceful_shutdown_on(self, publisher, *_):
        self.node = Node(**self.node_kwargs)
        self.node.quit = Mock()
        self.node.client = Mock()
        self.node._is_task_in_progress = Mock(return_value=True)

        result = self.node.graceful_shutdown()
        assert result == ShutdownResponse.on
        assert self.node.client.update_settings.called_with('in_shutdown', 1)
        assert self.node.quit.not_called
        assert self.node._is_task_in_progress.called
        publisher.publish.assert_called_with(
            Component.client, 'scheduled_shutdown', Stage.pre)

    def test_try_shutdown(self, *_):
        self.node = Node(**self.node_kwargs)
        self.node.quit = Mock()
        self.node.client = Mock()
        self.node._is_task_in_progress = Mock(return_value=True)

        self.node._try_shutdown()
        assert self.node.quit.not_called

        result = self.node.graceful_shutdown()
        assert result == ShutdownResponse.on

        self.node._config_desc.in_shutdown = 1
        self.node._is_task_in_progress = Mock(return_value=False)
        self.node._try_shutdown()
        assert self.node._is_task_in_progress.called
        assert self.node.quit.called

    def test__is_task_in_progress_no_shutdown(self, *_):
        self.node = Node(**self.node_kwargs)

        mock_tm = Mock()
        mock_tc = Mock()
        self.node.client = Mock()
        self.node.client.task_server.task_manager = mock_tm
        self.node.client.task_server.task_computer = mock_tc

        mock_tm.get_progresses = Mock(return_value={})
        mock_tc.has_assigned_task = Mock(return_value=False)

        result = self.node._is_task_in_progress()

        assert result is False
        assert mock_tm.get_progresses.called

    def test__is_task_in_progress_in_progress(self, *_):
        self.node = Node(**self.node_kwargs)

        mock_tm = Mock()
        mock_tc = Mock()
        self.node.client = Mock()
        self.node.client.task_server = Mock()
        self.node.client.task_server.task_manager = mock_tm
        self.node.client.task_server.task_computer = mock_tc

        mock_tm.get_progresses = Mock(return_value={'a': 'a'})

        result = self.node._is_task_in_progress()

        assert result is True
        assert mock_tm.get_progresses.called

    def test__is_task_in_progress_quit(self, *_):
        self.node = Node(**self.node_kwargs)

        mock_tm = Mock()
        mock_tc = Mock()
        self.node.client = Mock()
        self.node.client.task_server = Mock()
        self.node.client.task_server.task_manager = mock_tm
        self.node.client.task_server.task_computer = mock_tc

        mock_tm.get_progresses = Mock(return_value={'a': 'a'})
        mock_tc.has_assigned_task = Mock(return_value=True)

        result = self.node._is_task_in_progress()

        assert result is True
        assert mock_tm.get_progresses.called


class TestConcentTermsOfService(unittest.TestCase):
    def test_show(self):
        result = Node.show_concent_terms()
        self.assertIsInstance(result, str)

    @classmethod
    @patch("golem.terms.ConcentTermsOfUse.accept")
    def test_accept(cls, accept_mock):
        Node.accept_concent_terms()
        accept_mock.assert_called_once_with()

    @patch("golem.terms.ConcentTermsOfUse.are_accepted")
    def test_are_accepted(self, are_mock):
        sentinel = object()
        are_mock.return_value = sentinel
        result = Node.are_concent_terms_accepted()
        self.assertEqual(result, sentinel)
