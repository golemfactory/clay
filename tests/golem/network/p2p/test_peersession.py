import unittest
import unittest.mock as mock

from golem.network.p2p.peersession import PeerMonitor
from golem.diag.service import DiagnosticsOutputFormat


class TestPeerMonitor(unittest.TestCase):

    def test_get_diagnostics(self):
        peermanager = mock.Mock()
        monitor = PeerMonitor(peermanager)

        peermanager.peers = [
            mock.Mock(
                remote_pubkey=mock.sentinel.pub1,
                ip_port=mock.sentinel.ip1,
                node_name=mock.sentinel.name1,
                spec=['remote_pubkey', 'ip_port', 'node_name']
            ),
            mock.Mock(
                remote_pubkey=mock.sentinel.pub2,
                ip_port=mock.sentinel.ip2,
                spec=['remote_pubkey', 'ip_port']
            ),
        ]

        diag = monitor.get_diagnostics(DiagnosticsOutputFormat.data)
        self.assertEquals(mock.sentinel.pub1, diag[0]['remote_pubkey'])
        self.assertEquals(mock.sentinel.ip1, diag[0]['ip_port'])
        self.assertEquals(mock.sentinel.name1, diag[0]['node_name'])
        self.assertEquals(mock.sentinel.pub2, diag[1]['remote_pubkey'])
        self.assertEquals(mock.sentinel.ip2, diag[1]['ip_port'])
        self.assertNotIn('node_name', diag[1])
