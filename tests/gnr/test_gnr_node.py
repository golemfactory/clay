import unittest
import os
import cPickle
import jsonpickle
from mock import patch, call
from gnr.node import start
from click.testing import CliRunner
from golem.network.transport.tcpnetwork import TCPAddress
from golem.appconfig import AppConfig, CommonConfig, NodeConfig
from golem.tools.testwithdatabase import TestWithDatabase


class A(object):
    def __init__(self):
        self.a = 2
        self.b = "abc"


class TestNode(TestWithDatabase):

    def setUp(self):
        # This is to prevent test methods from picking up AppConfigs
        # created by previously run test methods:
        AppConfig.CONFIG_LOADED = False
        TestWithDatabase.setUp(self)

    def tearDown(self):
        AppConfig.CONFIG_LOADED = False
        if hasattr(CommonConfig, "_properties"):
            del CommonConfig._properties
        if hasattr(CommonConfig, "properties"):
            del CommonConfig.properties
        if hasattr(NodeConfig, "_properties"):
            del NodeConfig._properties
        if hasattr(NodeConfig, "properties"):
            del NodeConfig.properties
        TestWithDatabase.tearDown(self)

    @patch('gnr.node.reactor')
    def test_help(self, mock_reactor):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--help'])
        self.assertEqual(return_value.exit_code, 0)
        self.assertTrue(return_value.output.startswith('Usage'))
        mock_reactor.run.assert_not_called()

    @patch('gnr.node.reactor')
    def test_wrong_option(self, mock_reactor):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--blargh'])
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue(return_value.output.startswith('Error'))
        mock_reactor.run.assert_not_called()

    @patch('gnr.node.reactor')
    def test_no_args(self, mock_reactor):
        runner = CliRunner()
        return_value = runner.invoke(start)
        self.assertEqual(return_value.exit_code, 0)
        mock_reactor.run.assert_called_with()

    @patch('golem.client.Client')
    @patch('gnr.node.reactor')
    def test_node_address_none(self, mock_reactor, mock_client):
        """Test that without '--node-address' arg the client is started with
        a 'config_desc' arg such that 'config_desc.node_address' is ''.
        """
        runner = CliRunner()
        return_value = runner.invoke(start)
        self.assertEqual(return_value.exit_code, 0)

        self.assertGreater(len(mock_client.mock_calls), 0)
        init_call = mock_client.mock_calls[0]
        self.assertEqual(init_call[0], '')  # call name == '' for __init__ call
        (config_desc, ) = init_call[1]
        self.assertTrue(hasattr(config_desc, 'node_address'))
        self.assertEqual(config_desc.node_address, '')

    @patch('gnr.node.GNRNode')
    def test_node_address_valid(self, mock_node):
        node_address = '1.2.3.4'

        runner = CliRunner()
        return_value = runner.invoke(start, ['--node-address', node_address])
        self.assertEquals(return_value.exit_code, 0)

        self.assertGreater(len(mock_node.mock_calls), 0)
        init_call = mock_node.mock_calls[0]
        self.assertEqual(init_call[0], '')  # call name == '' for __init__ call
        init_call_args = init_call[1]
        init_call_kwargs = init_call[2]
        self.assertEqual(init_call_args, ())
        self.assertEqual(init_call_kwargs.get('node_address'), node_address)

    @patch('golem.client.Client')
    @patch('gnr.node.reactor')
    def test_node_address_passed_to_client(self, mock_reactor, mock_client):
        """Test that with '--node-address <addr>' arg the client is started with
        a 'config_desc' arg such that 'config_desc.node_address' is <addr>.
        """
        node_address = '1.2.3.4'

        runner = CliRunner()
        return_value = runner.invoke(start, ['--node-address', node_address])
        self.assertEquals(return_value.exit_code, 0)

        self.assertGreater(len(mock_client.mock_calls), 0)
        init_call = mock_client.mock_calls[0]
        self.assertEqual(init_call[0], '')  # call name == '' for __init__ call
        (config_desc, ) = init_call[1]
        self.assertTrue(hasattr(config_desc, 'node_address'))
        self.assertEqual(config_desc.node_address, node_address)

    @patch('gnr.node.GNRNode')
    def test_node_address_invalid(self, mock_node):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--node-address', '10.30.10.2555'])
        self.assertEquals(return_value.exit_code, 2)
        self.assertTrue('Invalid value for "--node-address"' in
                        return_value.output)

    @patch('gnr.node.GNRNode')
    def test_node_address_missing(self, mock_node):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--node-address'])
        self.assertEquals(return_value.exit_code, 2)
        self.assertTrue('Error' in return_value.output)

    @patch('gnr.node.GNRNode')
    def test_single_peer(self, mock_node):
        addr1 = '10.30.10.216:40111'
        runner = CliRunner()
        return_value = runner.invoke(start, ['--peer', addr1])
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run(), call().add_tasks([])], any_order=True)
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().connect_with_peers' in call_names)
        peer_num = call_names.index('().connect_with_peers')
        peer_arg = mock_node.mock_calls[peer_num][1][0]
        self.assertEqual(len(peer_arg), 1)
        self.assertEqual(peer_arg[0], TCPAddress.parse(addr1))

    @patch('gnr.node.GNRNode')
    def test_many_peers(self, mock_node):
        addr1 = '10.30.10.216:40111'
        addr2 = '10.30.10.214:3333'
        runner = CliRunner()
        return_value = runner.invoke(start, ['--peer', addr1, '--peer', addr2])
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run(), call().add_tasks([])], any_order=True)
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().connect_with_peers' in call_names)
        peer_num = call_names.index('().connect_with_peers')
        peer_arg = mock_node.mock_calls[peer_num][1][0]
        self.assertEqual(len(peer_arg), 2)
        self.assertEqual(peer_arg[0], TCPAddress.parse(addr1))
        self.assertEqual(peer_arg[1], TCPAddress.parse(addr2))

    @patch('gnr.node.GNRNode')
    def test_bad_peer(self, mock_node):
        addr1 = '10.30.10.216:40111'
        runner = CliRunner()
        return_value = runner.invoke(start, ['--peer', addr1, '--peer', 'bla'])
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue('Invalid peer address' in return_value.output)

    @patch('gnr.node.GNRNode')
    def test_peers(self, mock_node):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--peer', u'10.30.10.216:40111',
                                             u'--peer', u'[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443',
                                             '--peer', '[::ffff:0:0:0]:96'])
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run(), call().add_tasks([])], any_order=True)
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().connect_with_peers' in call_names)
        peer_num = call_names.index('().connect_with_peers')
        peer_arg = mock_node.mock_calls[peer_num][1][0]
        self.assertEqual(len(peer_arg), 3)
        self.assertEqual(peer_arg[0], TCPAddress('10.30.10.216', 40111))
        self.assertEqual(peer_arg[1], TCPAddress('2001:db8:85a3:8d3:1319:8a2e:370:7348', 443))
        self.assertEqual(peer_arg[2], TCPAddress('::ffff:0:0:0', 96))

    @patch('gnr.node.GNRNode')
    def test_wrong_task(self, mock_node):
        runner = CliRunner()
        return_value = runner.invoke(start, ['--task', 'testtask.gt'])
        self.assertEqual(return_value.exit_code, 2)
        self.assertTrue('Error' in return_value.output and 'Usage' in return_value.output)

    @patch('gnr.node.GNRNode')
    def test_task(self, mock_node):
        runner = CliRunner()

        a = A()
        with open('testclassdump', 'w') as f:
            cPickle.dump(a, f)
        return_value = runner.invoke(start, ['--task', 'testclassdump', '--task', 'testclassdump'])
        self.assertEqual(return_value.exit_code, 0)
        mock_node.assert_has_calls([call().run()])
        call_names = [name for name, arg, kwarg in mock_node.mock_calls]
        self.assertTrue('().add_tasks' in call_names)
        task_num = call_names.index('().add_tasks')
        task_arg = mock_node.mock_calls[task_num][1][0]
        self.assertEqual(len(task_arg), 2)
        self.assertIsInstance(task_arg[0], A)
        if os.path.exists('testclassdump'):
            os.remove('testclassdump')

    @patch('gnr.node.GNRNode')
    def test_task_from_json(self, mock_node):
        test_json_file = 'task.json'
        a1 = A()
        a1.name = 'Jake the Dog'
        a2 = A()
        a2.child = a1

        with open(test_json_file, 'w') as f:
            j = jsonpickle.encode(a2)
            f.write(j)

        try:
            runner = CliRunner()
            return_value = runner.invoke(start, ['--task', test_json_file])
            self.assertEqual(return_value.exit_code, 0)

            mock_node.assert_has_calls([call().run()])
            call_names = [name for name, arg, kwarg in mock_node.mock_calls]
            self.assertTrue('().add_tasks' in call_names)
            add_tasks_num = call_names.index('().add_tasks')
            (task_arg, ) = mock_node.mock_calls[add_tasks_num][1][0]
            self.assertIsInstance(task_arg, A)
            self.assertEqual(task_arg.child.name, 'Jake the Dog')

        finally:
            if os.path.exists(test_json_file):
                os.remove(test_json_file)

    @patch('gnr.node.GNRNode')
    def test_task_from_invalid_json(self, mock_node):
        test_json_file = 'task.json'
        with open(test_json_file, 'w') as f:
            f.write('Clearly this is not a valid json.')

        try:
            runner = CliRunner()
            return_value = runner.invoke(start, ['--task', test_json_file])
            self.assertEqual(return_value.exit_code, 2)
            self.assertIn('Invalid value for "--task"', return_value.output)

        finally:
            if os.path.exists(test_json_file):
                os.remove(test_json_file)
