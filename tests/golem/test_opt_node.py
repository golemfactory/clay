import os

from click.testing import CliRunner
from mock import patch, call, Mock

from golem.core.compress import save
from golem.network.transport.tcpnetwork import SocketAddress
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from golem.tools.testwithdatabase import TestWithDatabase
from golemapp import start, OptNode


class A(object):
    def __init__(self):
        self.a = 2
        self.b = "abc"


class TestNode(TestWithDatabase):
    def setUp(self):
        super(TestNode, self).setUp()
        self.args = ['--nogui', '--datadir', self.path]

    def tearDown(self):
        super(TestNode, self).tearDown()

    @ci_skip
    @patch('twisted.internet.reactor', create=True)
    def test_help(self, mock_reactor):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--help'], catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)
        self.assertTrue(return_value.output.startswith('Usage'))
        mock_reactor.run.assert_not_called()

    @ci_skip
    @patch('twisted.internet.reactor', create=True)
    def test_wrong_option(self, mock_reactor):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--blargh'],
                                     catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue(return_value.output.startswith('Error'))
        mock_reactor.run.assert_not_called()

    @ci_skip
    @patch('golemapp.OptNode')
    @patch('twisted.internet.reactor', create=True)
    @patch('golem.core.common.config_logging')
    def test_node_address_valid(self, config_logging, mock_reactor, mock_node):
        node_address = '1.2.3.4'

        runner = CliRunner()
        args = self.args + ['--node-address', node_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEquals(return_value.exit_code, 0)

        self.assertGreater(len(mock_node.mock_calls), 0)
        init_call = mock_node.mock_calls[0]
        self.assertEqual(init_call[0], '')  # call name == '' for __init__ call
        init_call_args = init_call[1]
        init_call_kwargs = init_call[2]
        self.assertEqual(init_call_args, ())
        self.assertEqual(init_call_kwargs.get('node_address'), node_address)

    @ci_skip
    @patch('golem.node.Client')
    @patch('twisted.internet.reactor', create=True)
    @patch('golem.core.common.config_logging')
    @patch('golemapp.delete_reactor')
    def test_node_address_passed_to_client(self, delete_reactor, config_logging,
                                           mock_reactor, mock_client):
        """Test that with '--node-address <addr>' arg the client is started with
        a 'config_desc' arg such that 'config_desc.node_address' is <addr>.
        """
        node_address = '1.2.3.4'
        runner = CliRunner()
        args = self.args + ['--node-address', node_address]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEquals(return_value.exit_code, 0)

        mock_client.assert_called_with(node_address=node_address,
                                       datadir=self.path,
                                       transaction_system=True)

    @ci_skip
    @patch('golem.core.common.config_logging')
    def test_node_address_invalid(self, config_logging):
        runner = CliRunner()
        args = self.args + ['--node-address', '10.30.10.2555']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEquals(return_value.exit_code, 2)
        self.assertTrue('Invalid value for "--node-address"' in
                        return_value.output)

    @ci_skip
    def test_node_address_missing(self):
        runner = CliRunner()
        return_value = runner.invoke(start, self.args + ['--node-address'])
        self.assertEquals(return_value.exit_code, 2)
        self.assertIn('Error: --node-address', return_value.output)

    @ci_skip
    @patch('golemapp.OptNode')
    @patch('golem.core.common.config_logging')
    def test_single_peer(self, config_logging, mock_node):
        addr1 = '10.30.10.216:40111'
        runner = CliRunner()
        return_value = runner.invoke(start, self.args + ['--peer', addr1],
                                     catch_exceptions=False)
        self.assertTrue(mock_node.called)
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run(use_rpc=True),
                                   call().add_tasks([])], any_order=True)
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().connect_with_peers' in call_names)
        peer_num = call_names.index('().connect_with_peers')
        peer_arg = mock_node.mock_calls[peer_num][1][0]
        self.assertEqual(len(peer_arg), 1)
        self.assertEqual(peer_arg[0], SocketAddress.parse(addr1))

    @ci_skip
    @patch('golemapp.OptNode')
    @patch('golem.core.common.config_logging')
    def test_many_peers(self, config_logging, mock_node):
        addr1 = '10.30.10.216:40111'
        addr2 = '10.30.10.214:3333'
        runner = CliRunner()
        args = self.args + ['--peer', addr1, '--peer', addr2]
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run(use_rpc=True),
                                   call().add_tasks([])], any_order=True)
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().connect_with_peers' in call_names)
        peer_num = call_names.index('().connect_with_peers')
        peer_arg = mock_node.mock_calls[peer_num][1][0]
        self.assertEqual(len(peer_arg), 2)
        self.assertEqual(peer_arg[0], SocketAddress.parse(addr1))
        self.assertEqual(peer_arg[1], SocketAddress.parse(addr2))

    @ci_skip
    @patch('golemapp.OptNode')
    def test_bad_peer(self, mock_node):
        addr1 = '10.30.10.216:40111'
        runner = CliRunner()
        args = self.args + ['--peer', addr1, '--peer', 'bla']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue('Invalid peer address' in return_value.output)

    @ci_skip
    @patch('golemapp.OptNode')
    @patch('golem.core.common.config_logging')
    def test_peers(self, config_logging, mock_node):
        runner = CliRunner()
        return_value = runner.invoke(
            start, self.args + ['--peer', u'10.30.10.216:40111',
                                u'--peer', u'[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443',
                                '--peer', '[::ffff:0:0:0]:96'],
            catch_exceptions=False
        )
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run(use_rpc=True), call().add_tasks([])], any_order=True)
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().connect_with_peers' in call_names)
        peer_num = call_names.index('().connect_with_peers')
        peer_arg = mock_node.mock_calls[peer_num][1][0]
        self.assertEqual(len(peer_arg), 3)
        self.assertEqual(peer_arg[0], SocketAddress('10.30.10.216', 40111))
        self.assertEqual(peer_arg[1], SocketAddress('2001:db8:85a3:8d3:1319:8a2e:370:7348', 443))
        self.assertEqual(peer_arg[2], SocketAddress('::ffff:0:0:0', 96))

    @ci_skip
    @patch('golemapp.OptNode')
    @patch('golem.core.common.config_logging')
    def test_rpc_address(self, config_logging, mock_node):
        runner = CliRunner()

        ok_addresses = [['--rpc-address', u'10.30.10.216:61000'],
                        ['--rpc-address', '[::ffff:0:0:0]:96'],
                        [u'--rpc-address', u'[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443']]
        bad_addresses = [['--rpc-address', u'10.30.10.216:91000'],
                         ['--rpc-address', '[::ffff:0:0:0]:96999']]
        skip_addresses = [[u'--rpc-address', u'']]

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

    @ci_skip
    @patch('golemapp.OptNode')
    def test_wrong_task(self, mock_node):
        runner = CliRunner()
        args = self.args + ['--task', 'testtask.gt']
        return_value = runner.invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 2)
        assert 'Error' in return_value.output
        assert 'Usage' in return_value.output

    @ci_skip
    @patch('golemapp.OptNode')
    @patch('golem.core.common.config_logging')
    def test_task(self, config_logging, mock_node):
        a = A()
        dump = os.path.join(self.path, 'testcalssdump')
        save(a, dump, False)
        args = self.args + ['--task', dump, '--task', dump]
        return_value = CliRunner().invoke(start, args, catch_exceptions=False)
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run(use_rpc=True)])
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().add_tasks' in call_names)
        task_num = call_names.index('().add_tasks')
        task_arg = mock_node.mock_calls[task_num][1][0]
        self.assertEqual(len(task_arg), 2)
        self.assertIsInstance(task_arg[0], A)

    @ci_skip
    @patch('golemapp.OptNode')
    @patch('golem.core.common.config_logging')
    def test_task_from_json(self, config_logging, mock_node):
        test_json_file = os.path.join(self.path, 'task.json')
        a1 = A()
        a1.name = 'Jake the Dog'
        a2 = A()
        a2.child = a1

        save(a2, test_json_file, False)
        try:
            runner = CliRunner()
            args = self.args + ['--task', test_json_file]
            return_value = runner.invoke(start, args, catch_exceptions=False)
            self.assertEqual(return_value.exit_code, 0)

            mock_node.assert_has_calls([call().run(use_rpc=True)])
            call_names = [name for name, arg, kwarg in mock_node.mock_calls]
            self.assertTrue('().add_tasks' in call_names)
            add_tasks_num = call_names.index('().add_tasks')
            (task_arg,) = mock_node.mock_calls[add_tasks_num][1][0]
            self.assertIsInstance(task_arg, A)
            self.assertEqual(task_arg.child.name, 'Jake the Dog')

        finally:
            if os.path.exists(test_json_file):
                os.remove(test_json_file)

    @ci_skip
    @patch('golemapp.OptNode')
    def test_task_from_invalid_json(self, mock_node):
        test_json_file = os.path.join(self.path, 'task.json')
        with open(test_json_file, 'w') as f:
            f.write('Clearly this is not a valid json.')

        try:
            runner = CliRunner()
            args = self.args + ['--task', test_json_file]
            return_value = runner.invoke(start, args, catch_exceptions=False)
            self.assertEqual(return_value.exit_code, 2)
            self.assertIn('Invalid value for "--task"', return_value.output)

        finally:
            if os.path.exists(test_json_file):
                os.remove(test_json_file)


class TestOptNode(TempDirFixture):

    def setUp(self):
        super(TestOptNode, self).setUp()
        self.node = OptNode(self.path)

    def tearDown(self):
        self.node.client.quit()
        super(TestOptNode, self).tearDown()

    def test_task_builder(self):
        task_def = Mock()
        task_def.task_type = "Blender"
        self.assertIsNotNone(self.node._get_task_builder(task_def))

    @patch('golem.rpc.router.CrossbarRouter', create=True)
    @patch('twisted.internet.reactor', create=True)
    def test_start_rpc_server(self, reactor, router):
        self.node._start_rpc_server('127.0.0.1', 12345)
        assert self.node.rpc_router
        assert self.node.rpc_router.start.called
        assert reactor.addSystemEventTrigger.called
