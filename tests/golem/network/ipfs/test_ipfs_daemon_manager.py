import unittest
import uuid
from unittest import skipIf

from mock import patch, Mock

import requests

from golem.network.ipfs.client import IPFSAddress, IPFSCommands, IPFS_BOOTSTRAP_NODES, IPFSConfig, ipfs_running
from golem.network.ipfs.daemon_manager import IPFSDaemonManager


@skipIf(not ipfs_running(), "IPFS daemon isn't running")
class TestIPFSDaemonManager(unittest.TestCase):

    def testStoreInfo(self):
        dm = IPFSDaemonManager(connect_to_bootstrap_nodes=False)
        ipfs_id = dm.store_client_info()
        self.assertIsInstance(ipfs_id, basestring)
        from base58 import b58decode
        b58decode(ipfs_id)

    def testAddRemoveBootstrapNodes(self):
        default_node = '/ip4/127.0.0.1/tcp/4001/ipfs/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ'
        dm = IPFSDaemonManager(connect_to_bootstrap_nodes=False)
        dm.remove_bootstrap_node(default_node, async=False)

        dm.add_bootstrap_node(default_node, async=False)
        assert default_node in dm.list_bootstrap_nodes()

        dm.remove_bootstrap_node(default_node, async=False)
        assert default_node not in dm.list_bootstrap_nodes()

    def testMetadata(self):
        dm = IPFSDaemonManager(connect_to_bootstrap_nodes=False)
        dm.store_client_info()
        metadata = dm.get_metadata()

        assert dm.addresses is not None
        assert dm.get_metadata() is not None
        assert len(metadata['ipfs']) >= 2

        for ipfs_addr in dm.addresses:
            if IPFSAddress.allowed_ip_address(ipfs_addr.ip_address):
                assert metadata['ipfs']['addresses']

    @patch('twisted.internet.reactor', create=True)
    def testInterpretMetadata(self, mock_reactor):
        dm = IPFSDaemonManager(connect_to_bootstrap_nodes=False)
        dm.store_client_info()
        meta = dm.get_metadata()
        node_id = dm.addresses[0].node_id

        ipv4 = '127.0.0.1'
        ipv6 = '2001:db8:85a3::8a2e:370:7334'
        port = 40102

        meta['ipfs']['addresses'] = [
            str(IPFSAddress(ipv4, node_id)),
            str(IPFSAddress('::1', node_id))
        ]
        addrs = [(ipv4, port), (ipv6, port)]

        ip4_node = u'/ip4/{}/tcp/{}/ipfs/{}'.format(ipv4, 4001, node_id)
        ip6_node = u'/ip6/{}/tcp/{}/ipfs/{}'.format(ipv6, 4001, node_id)

        dm.remove_bootstrap_node(ip4_node, async=False)
        dm.remove_bootstrap_node(ip6_node, async=False)

        assert ip4_node not in dm.list_bootstrap_nodes()
        assert ip6_node not in dm.list_bootstrap_nodes()

        assert not dm.interpret_metadata(meta, [('1.2.3.4', port)], addrs, async=False)

        assert dm.interpret_metadata(meta, [(ipv4, port)], addrs, async=False)
        assert ip4_node in dm.list_bootstrap_nodes()

        assert dm.interpret_metadata(meta, [(ipv6, port)], addrs, async=False)

        dm.remove_bootstrap_node(ip4_node, async=False)
        dm.remove_bootstrap_node(ip6_node, async=False)

        assert ip4_node not in dm.list_bootstrap_nodes()
        assert ip6_node not in dm.list_bootstrap_nodes()

    def testSwarm(self):
        dm = IPFSDaemonManager(connect_to_bootstrap_nodes=False)
        dm.store_client_info()

        err_node = '/ip4/127.0.0.1/tcp/4001/ipfs/badhash'

        assert not dm.swarm_connect(err_node, async=False)
        assert not dm.swarm_disconnect(err_node, async=False)
        assert dm.swarm_peers() is not None

    def testCommandFailed(self):
        dm = IPFSDaemonManager(connect_to_bootstrap_nodes=False)
        dm.last_backoff_clear_ts = 0
        dm.command_failed(requests.exceptions.ReadTimeout(),
                          IPFSCommands.get,
                          str(uuid.uuid4()),
                          async=False)

    def testNodeAction(self):
        dm = IPFSDaemonManager(connect_to_bootstrap_nodes=False)
        status = [True]

        def success(*args, **kwargs):
            status[0] = True
            return True

        def error(*args, **kwargs):
            status[0] = False
            return False

        def method(*args, **kwargs):
            return True

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

    @patch('golem.network.ipfs.client.IPFSClient')
    @patch('golem.network.ipfs.client.IPFSClient.bootstrap_list', create=True)
    def testConnectToBootstrapNodes(self, *_):
        invalid_node = 'invalid node'

        config = IPFSConfig(bootstrap_nodes=IPFS_BOOTSTRAP_NODES + [invalid_node])
        dm = IPFSDaemonManager(config=config)

        client = Mock()
        dm.bootstrap_nodes = IPFS_BOOTSTRAP_NODES
        dm.connect_to_bootstrap_nodes(async=False, client=client)
        assert client.swarm_connect.called
