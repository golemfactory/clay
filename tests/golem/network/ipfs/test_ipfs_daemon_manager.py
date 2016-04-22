import unittest

from golem.network.ipfs.daemon_manager import IPFSDaemonManager


class TestIPFSDaemonManager(unittest.TestCase):

    def testId(self):
        rm = IPFSDaemonManager()
        ipfs_id = rm.id()

        self.assertIsInstance(ipfs_id, basestring)
        assert ipfs_id

    def testAddRemoveBootstrapNodes(self):
        default_node = '/ip4/127.0.0.1/tcp/4001/ipfs/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ'
        rm = IPFSDaemonManager()
        rm.remove_bootstrap_node(default_node)

        nodes = rm.list_bootstrap_nodes()
        assert nodes

        rm.add_bootstrap_node(default_node)
        assert len(rm.list_bootstrap_nodes()) > len(nodes)

        rm.remove_bootstrap_node(default_node)
        assert len(rm.list_bootstrap_nodes()) == len(nodes)

    def testBuildNodeAddress(self):
        expected_ipv4 = '/ip4/127.0.0.1/tcp/4001/ipfs/QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'
        expected_ipv6 = '/ip6/::1/tcp/14001/ipfs/QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'

        ipv4 = IPFSDaemonManager.build_node_address('127.0.0.1', 'QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB')
        ipv6 = IPFSDaemonManager.build_node_address('::1', 'QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB',
                                                    port=14001)

        assert ipv4 == expected_ipv4
        assert ipv6 == expected_ipv6
