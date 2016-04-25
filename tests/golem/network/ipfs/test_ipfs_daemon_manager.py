import unittest

import time

from golem.network.ipfs.daemon_manager import IPFSDaemonManager


class TestIPFSDaemonManager(unittest.TestCase):

    def testId(self):
        dm = IPFSDaemonManager()
        ipfs_id = dm.store_info()

        self.assertIsInstance(ipfs_id, basestring)
        assert ipfs_id

    def testAddRemoveBootstrapNodes(self):
        default_node = '/ip4/127.0.0.1/tcp/4001/ipfs/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ'
        dm = IPFSDaemonManager()
        dm.remove_bootstrap_node(default_node, async=False)
        nodes = dm.list_bootstrap_nodes()
        assert nodes

        dm.add_bootstrap_node(default_node, async=False)
        assert len(dm.list_bootstrap_nodes()) > len(nodes)

        dm.remove_bootstrap_node(default_node, async=False)
        assert len(dm.list_bootstrap_nodes()) == len(nodes)

    def testBuildNodeAddress(self):
        expected_ipv4 = '/ip4/127.0.0.1/tcp/4001/ipfs/QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'
        expected_ipv6 = '/ip6/::1/tcp/14001/ipfs/QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'

        ipv4 = IPFSDaemonManager.build_node_address('127.0.0.1', 'QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB')
        ipv6 = IPFSDaemonManager.build_node_address('::1', 'QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB',
                                                    port=14001)

        assert ipv4 == expected_ipv4
        assert ipv6 == expected_ipv6

    def testMetadata(self):
        dm = IPFSDaemonManager()
        metadata = dm.get_metadata()

        assert dm.get_metadata() is not None
        assert len(metadata['ipfs']) >= 3
        assert metadata['ipfs']['id'] == dm.node_id

    def testInterpretMetadata(self):
        dm = IPFSDaemonManager()
        dm.store_info()
        meta = dm.get_metadata()

        ip_1 = '127.0.0.1'
        port_1 = 40102

        ip_2 = '1.2.3.4'
        port_2 = 40102

        addrs = [(ip_1, port_1)]

        default_node = '/ip4/{}/tcp/{}/ipfs/{}'.format(ip_1, 4001, meta['ipfs']['id'])
        dm.remove_bootstrap_node(default_node, async=False)

        nodes = dm.list_bootstrap_nodes()
        assert nodes

        assert not dm.interpret_metadata(meta, ip_2, port_2, addrs, async=False)
        assert dm.interpret_metadata(meta, ip_1, port_1, addrs, async=False)
        assert len(dm.list_bootstrap_nodes()) > len(nodes)

        dm.remove_bootstrap_node(default_node, async=False)

        assert len(dm.list_bootstrap_nodes()) == len(nodes)
