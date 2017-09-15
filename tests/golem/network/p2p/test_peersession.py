import unittest
from mock import Mock, sentinel

from golem.network.p2p.peersession import PeerMonitor
from golem.diag.service import DiagnosticsOutputFormat


class TestPeerMonitor(unittest.TestCase):

    def test_get_diagnostics(self):
        peermanager = Mock()
        monitor = PeerMonitor(peermanager)

        peermanager.peers = [
            Mock(
                remote_pubkey=sentinel.pub1,
                ip_port=sentinel.ip1,
                node_name=sentinel.name1,
                spec=['remote_pubkey', 'ip_port', 'node_name']
            ),
            Mock(
                remote_pubkey=sentinel.pub2,
                ip_port=sentinel.ip2,
                spec=['remote_pubkey', 'ip_port']
            ),
        ]

        diag = monitor.get_diagnostics(DiagnosticsOutputFormat.data)
        self.assertEquals(sentinel.pub1, diag[0]['remote_pubkey'])
        self.assertEquals(sentinel.ip1, diag[0]['ip_port'])
        self.assertEquals(sentinel.name1, diag[0]['node_name'])
        self.assertEquals(sentinel.pub2, diag[1]['remote_pubkey'])
        self.assertEquals(sentinel.ip2, diag[1]['ip_port'])
        self.assertNotIn('node_name', diag[1])
