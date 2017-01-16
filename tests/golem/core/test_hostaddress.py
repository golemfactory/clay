import unittest

import netifaces
from golem.core.hostaddress import get_host_address, ip_address_private, ip_network_contains, ipv4_networks, \
                                   ip_addresses, get_host_address_from_connection, get_external_address
from mock import patch


def mock_ifaddresses(*args):
    addrs = dict()
    addrs[netifaces.AF_INET] = [
        dict(
            addr='127.0.0.1',
            netmask=None
        ),
        dict(
            addr='10.0.0.10',
            netmask='255.255.255.0'
        ),
        dict(
            addr='8.8.8.8',
            netmask='255.255.255.255'
        ),
        dict(
            addr='invalid',
            netmask='invalid'
        ),
    ]
    return addrs


def is_ip_address(address, ip_v4, ip_v6):
    """
    Check if @address is correct IP address
    :param address: Address to be checked
    :param ip_v4: Check if is IPv4 address
    :param ip_v6: Check if is IPv6 address
    :return: True if is correct, false otherwise
    """
    import socket

    if ip_v4:
        try:
            socket.inet_pton(socket.AF_INET, address)   # will raise socket.error in case of incorrect address
            return True
        except socket.error:
            pass

    if ip_v6:
        try:
            socket.inet_pton(socket.AF_INET6, address)   # will raise socket.error in case of incorrect address
            return True
        except socket.error:
            pass

    return False


class TestIPAddresses(unittest.TestCase):
    """ Test getting IP addresses """

    def test_ip_addresses_v4(self):
        """ Test getting IP addresses for IPv4 """
        addresses = ip_addresses(False)
        if addresses:
            for address in addresses:
                self.assertTrue(is_ip_address(address, True, False), "Incorrect IP addres: {}".format(address))

    def test_ip_addresses_v6(self):
        """ Test getting IP addresses for IPv6 """
        addresses = ip_addresses(True)
        if addresses:
            for address in addresses:
                self.assertTrue(is_ip_address(address, False, True), "Incorrect IP addres: {}".format(address))


class TestHostAddress(unittest.TestCase):
    def testGetHostAddressFromConnection(self):
        """ Test getting host address by connecting """
        address = get_host_address_from_connection(use_ipv6=False)
        self.assertTrue(is_ip_address(address, True, False), "Incorrect IPv4 address: {}".format(address))
        address = get_host_address_from_connection(use_ipv6=True)
        self.assertTrue(is_ip_address(address, False, True), "Incorrect IPv6 address: {}".format(address))

    def testGetExternalAddress(self):
        """ Test getting host public address with STUN protocol """
        nats = ["Blocked", "Open Internet", "Full Cone", "Symmetric UDP Firewall",
                "Restric NAT", "Restric Port NAT", "Symmetric NAT"]
        address, port, nat = get_external_address()
        self.assertTrue(is_ip_address(address, True, True), "Incorrect IP address: {}".format(address))
        self.assertIsInstance(port, int, "Incorrect port type")
        self.assertTrue(0 < port < 65535, "Incorrect port number")
        self.assertIn(nat, nats, "Incorrect nat type")

        address, port, nat = get_external_address(9876)
        self.assertTrue(is_ip_address(address, True, True), "Incorrect IP address: {}".format(address))
        self.assertIsInstance(port, int, "Incorrect port type")
        self.assertTrue(0 < port < 65535, "Incorrect port number")
        self.assertIn(nat, nats, "Incorrect nat type")

    def testGetHostAddress(self):
        self.assertGreater(len(get_host_address('127.0.0.1')), 0)
        self.assertTrue(is_ip_address(get_host_address(None, False), True, False))
        self.assertTrue(is_ip_address(get_host_address(None, True), False, True))
        self.assertEqual(get_host_address("::1", True), "::1")

    @unittest.skip("Find network testing framework")
    def testGetHostAddress2(self):
        self.assertEqual(get_host_address('10.30.100.100'), '10.30.10.216')
        self.assertEqual(get_host_address('10.30.10.217'), '10.30.10.216')

    def testGetIPNetworks(self):
        addresses = ipv4_networks()

        if addresses:
            for address in addresses:
                self.assertTrue(is_ip_address(address[0], True, True), "Incorrect IP address: {}".format(address[0]))
                self.assertTrue(0 < int(address[1]) < 33, "Incorrect mask: {}".format(address[1]))

    @patch('netifaces.ifaddresses', side_effect=mock_ifaddresses)
    def testGetIPNetworks2(self, *_):
        ipv4_networks()

    def testIpAddressPrivate(self):
        self.assertTrue(ip_address_private('::1'))
        ipv6_private_pattern = 'fd{}::'
        for i in xrange(0, 256):
            self.assertTrue(ip_address_private(ipv6_private_pattern.format("%0.2X" % i)))

        self.assertTrue(ip_address_private('10.0.0.0'))
        self.assertTrue(ip_address_private('127.0.0.0'))
        self.assertTrue(ip_address_private('172.16.0.0'))
        self.assertTrue(ip_address_private('192.168.0.0'))
        self.assertFalse(ip_address_private('8.8.8.8'))
        self.assertFalse(ip_address_private('11.0.0.0'))
        self.assertFalse(ip_address_private('definitely.not.ip.address'))

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

        self.assertTrue(ip_network_contains(nets[0][0], nets[0][1], addrs[0]))
        self.assertTrue(ip_network_contains(nets[1][0], nets[1][1], addrs[1]))
        self.assertTrue(ip_network_contains(nets[2][0], nets[2][1], addrs[2]))
        self.assertTrue(ip_network_contains(nets[3][0], nets[3][1], addrs[3]))

        self.assertFalse(ip_network_contains(nets[0][0], nets[0][1], addrs[3]))
        self.assertFalse(ip_network_contains(nets[1][0], nets[1][1], addrs[2]))
        self.assertFalse(ip_network_contains(nets[2][0], nets[2][1], addrs[1]))
        self.assertFalse(ip_network_contains(nets[3][0], nets[3][1], addrs[0]))

        self.assertFalse(ip_network_contains(nets[0][0], nets[0][1], addrs[4]))
        self.assertFalse(ip_network_contains(nets[1][0], nets[1][1], addrs[4]))
        self.assertFalse(ip_network_contains(nets[2][0], nets[2][1], addrs[4]))
        self.assertFalse(ip_network_contains(nets[3][0], nets[3][1], addrs[4]))
