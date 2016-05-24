import unittest

from golem.network.ipfs.client import IPFSAddress, IPFSCommands
from golem.network.ipfs.daemon_manager import IPFSDaemonManager


class TestIPFSDaemonManager(unittest.TestCase):

    def testStoreInfo(self):
        dm = IPFSDaemonManager()
        dm.store_client_info()

        ipfs_id = dm.node_id

        self.assertIsInstance(ipfs_id, basestring)
        assert ipfs_id

    def testAddRemoveBootstrapNodes(self):
        default_node = '/ip4/127.0.0.1/tcp/4001/ipfs/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ'
        dm = IPFSDaemonManager()
        dm.remove_bootstrap_node(default_node, async=False)
        nodes = dm.list_bootstrap_nodes()

        dm.add_bootstrap_node(default_node, async=False)
        assert len(dm.list_bootstrap_nodes()) > len(nodes)

        dm.remove_bootstrap_node(default_node, async=False)
        assert len(dm.list_bootstrap_nodes()) == len(nodes)

    def testMetadata(self):
        dm = IPFSDaemonManager()
        dm.store_client_info()
        metadata = dm.get_metadata()

        assert dm.addresses is not None
        assert dm.get_metadata() is not None
        assert len(metadata['ipfs']) >= 2

        for ipfs_addr in dm.addresses:
            if IPFSAddress.allowed_ip_address(ipfs_addr.ip_address):
                assert metadata['ipfs']['addresses']

    def testInterpretMetadata(self):
        dm = IPFSDaemonManager()
        dm.store_client_info()
        meta = dm.get_metadata()
        node_id = dm.addresses[0].node_id

        ipv4 = '127.0.0.1'
        ipv6 = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
        port = 40102

        meta['ipfs']['addresses'] = [
            str(IPFSAddress(ipv4, node_id)),
            str(IPFSAddress('::1', node_id))
        ]
        addrs = [(ipv4, port), (ipv6, port)]

        ip4_node = '/ip4/{}/tcp/{}/ipfs/{}'.format(ipv4, 4001, node_id)
        ip6_node = '/ip6/{}/tcp/{}/ipfs/{}'.format(ipv6, 4001, node_id)

        dm.remove_bootstrap_node(ip4_node, async=False)
        dm.remove_bootstrap_node(ip6_node, async=False)

        nodes = dm.list_bootstrap_nodes()

        assert not dm.interpret_metadata(meta, [('1.2.3.4', port)], addrs, async=False)

        assert dm.interpret_metadata(meta, [(ipv4, port)], addrs, async=False)
        assert len(dm.list_bootstrap_nodes()) == len(nodes) + 1

        assert dm.interpret_metadata(meta, [(ipv6, port)], addrs, async=False)
        assert len(dm.list_bootstrap_nodes()) == len(nodes) + 2

        dm.remove_bootstrap_node(ip4_node, async=False)
        dm.remove_bootstrap_node(ip6_node, async=False)
        assert len(dm.list_bootstrap_nodes()) == len(nodes)

    def testSwarm(self):
        dm = IPFSDaemonManager()
        dm.store_client_info()

        err_node = '/ip4/127.0.0.1/tcp/4001/ipfs/badhash'

        assert not dm.swarm_connect(err_node, async=False)
        assert not dm.swarm_disconnect(err_node, async=False)
        assert dm.swarm_peers() is not None

    def testNodeAction(self):
        dm = IPFSDaemonManager()
        status = [True]

        def success(*args, **kwargs):
            status[0] = True

        def error(*args, **kwargs):
            status[0] = False

        def method(*args, **kwargs):
            pass

        def raise_method(*args, **kwargs):
            raise Exception("Error")

        status[0] = True
        dm._node_action(
            "test",
            method=method,
            command=-1,
            success=success,
            error=error,
            async=False
        )

        assert not status[0]

        status[0] = True
        dm._node_action(
            '/ip4/127.0.0.1/tcp/4001/ipfs/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ',
            method=raise_method,
            command=IPFSCommands.add,
            success=success,
            error=error,
            async=False
        )

        assert not status[0]
