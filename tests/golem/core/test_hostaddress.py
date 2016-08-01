import unittest
from golem.core.hostaddress import get_host_address, ip_address_private, ip_network_contains, ipv4_networks


class TestHostAddress(unittest.TestCase):
    def testGetHostAddress(self):
        self.assertGreater(len(get_host_address('127.0.0.1')), 0)

    @unittest.skip("Find network testing framework")
    def testGetHostAddress2(self):
        self.assertEqual(get_host_address('10.30.100.100'), '10.30.10.216')
        self.assertEqual(get_host_address('10.30.10.217'), '10.30.10.216')

    def testGetIPNetworks(self):
        ipv4_networks()

    def testIpAddressPrivate(self):
        assert ip_address_private('::1')
        ipv6_private_pattern = 'fd{}::'
        for i in xrange(0, 256):
            assert ip_address_private(ipv6_private_pattern.format("%0.2X" % i))

        assert ip_address_private('10.0.0.0')
        assert ip_address_private('127.0.0.0')
        assert ip_address_private('172.16.0.0')
        assert ip_address_private('192.168.0.0')
        assert not ip_address_private('8.8.8.8')
        assert not ip_address_private('11.0.0.0')

    def testIpNetworkContains(self):
        addrs = [
            '10.0.0.1',
            '127.0.0.1',
            '172.16.0.1',
            '192.168.0.1',
            '8.8.8.8'
        ]
        nets = [
            (u'10.0.0.0', 8),
            (u'127.0.0.0', 8),
            (u'172.16.0.0', 12),
            (u'192.168.0.0', 16),
        ]

        assert ip_network_contains(nets[0][0], nets[0][1], addrs[0])
        assert ip_network_contains(nets[1][0], nets[1][1], addrs[1])
        assert ip_network_contains(nets[2][0], nets[2][1], addrs[2])
        assert ip_network_contains(nets[3][0], nets[3][1], addrs[3])

        assert not ip_network_contains(nets[0][0], nets[0][1], addrs[3])
        assert not ip_network_contains(nets[1][0], nets[1][1], addrs[2])
        assert not ip_network_contains(nets[2][0], nets[2][1], addrs[1])
        assert not ip_network_contains(nets[3][0], nets[3][1], addrs[0])

        assert not ip_network_contains(nets[0][0], nets[0][1], addrs[4])
        assert not ip_network_contains(nets[1][0], nets[1][1], addrs[4])
        assert not ip_network_contains(nets[2][0], nets[2][1], addrs[4])
        assert not ip_network_contains(nets[3][0], nets[3][1], addrs[4])
