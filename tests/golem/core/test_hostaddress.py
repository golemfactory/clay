import unittest
from unittest.mock import patch

import netifaces

from golem.core.hostaddress import get_host_address, ip_address_private, \
    ip_network_contains, ipv4_networks, \
    ip_addresses, get_host_address_from_connection, get_external_address


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


def is_ip_address(address):
    """
    Check if @address is correct IP address
    :param address: Address to be checked
    :return: True if is correct, false otherwise
    """
    from ipaddress import ip_address, AddressValueError
    try:
        # will raise error in case of incorrect address
        ip_address(str(address))
        return True
    except (ValueError, AddressValueError):
        return False


class TestIPAddresses(unittest.TestCase):
    """ Test getting IP addresses """

    @patch('golem.core.hostaddress.netifaces.ifaddresses')
    @patch('golem.core.hostaddress.netifaces.interfaces')
    def test_empty_netifaces_ifaddresses(self, interfaces, ifaddresses):
        interfaces.return_value = ['eth0']
        ifaddresses.return_value = {}
        assert ip_addresses(use_ipv6=True) == []
        assert ip_addresses(use_ipv6=False) == []

    @patch('golem.core.hostaddress.netifaces.ifaddresses')
    @patch('golem.core.hostaddress.netifaces.interfaces')
    def test_filter_ip_addresses_v4(self, interfaces, ifaddresses):
        interfaces.return_value = ['eth0']
        ifaddresses.return_value = {
            netifaces.AF_INET: [
                {'addr': None},  # invalid
                {'addr': '?'},  # invalid
                {'addr': '0.0.0.0'},  # unspecified
                {'addr': '127.0.0.1'},  # loopback
                {'addr': '127.0.0.123'},  # loopback
                {'addr': '169.254.0.1'},  # link local
                {'addr': '169.254.0.123'},  # link local
                {'addr': '224.0.0.1'},  # multicast
                {'addr': '240.0.0.1'},  # reserved
                {'addr': '192.168.0.5'},  # private
                {'addr': '1.2.3.4'},  # public
            ]
        }

        assert ip_addresses(use_ipv6=False) == ['192.168.0.5', '1.2.3.4']

    @patch('golem.core.hostaddress.netifaces.ifaddresses')
    @patch('golem.core.hostaddress.netifaces.interfaces')
    def test_filter_ip_addresses_v6(self, interfaces, ifaddresses):
        interfaces.return_value = ['eth0']
        ifaddresses.return_value = {
            netifaces.AF_INET6: [
                {'addr': None},  # invalid
                {'addr': '?'},  # invalid
                {'addr': '::'},
                {'addr': '::1'},  # loopback
                {'addr': 'fe80::'},  # link local
                {'addr': 'fe80::dead'},  # link local
                {'addr': 'ff00::'},  # multicast
                {'addr': 'FE00::'},  # reserved
                {'addr': '2001::1'},  # private
                {'addr': '2001:4660:4660::6666'},  # public
            ]
        }

        assert ip_addresses(use_ipv6=True) == ['2001::1',
                                               '2001:4660:4660::6666']

    def test_ip_addresses_v4(self):
        """ Test getting IP addresses for IPv4 """
        addresses = ip_addresses(use_ipv6=False)
        if addresses:
            for address in addresses:
                self.assertTrue(is_ip_address(address),
                                "Incorrect IP address: {}".format(address))

    def test_ip_addresses_v6(self):
        """ Test getting IP addresses for IPv6 """
        addresses = ip_addresses(use_ipv6=True)
        if addresses:
            for address in addresses:
                self.assertTrue(is_ip_address(address),
                                "Incorrect IP address: {}".format(address))


class TestHostAddress(unittest.TestCase):
    def testGetHostAddressFromConnection(self):
        """ Test getting host address by connecting """
        address = get_host_address_from_connection(use_ipv6=False)
        self.assertTrue(is_ip_address(address), "Incorrect IPv4 address: {}".format(address))

    def test_get_external_address_live(self):
        """ Test getting host public address with STUN protocol """
        address, port = get_external_address()
        self.assertTrue(is_ip_address(address), "Incorrect IP address: {}".format(address))
        self.assertIsInstance(port, int, "Incorrect port type")
        self.assertTrue(0 < port < 65535, "Incorrect port number")

    @patch('golem.network.stun.pystun.get_ip_info')
    def test_get_external_address_argument(self, stun):
        stun.return_value = ('2607:f0d0:1002:51::4', 1234)
        address, port = get_external_address(9876)
        assert stun.called_once_with(9876)
        address, port = get_external_address()
        assert stun.called_once_with(0)

    @patch('golem.core.hostaddress.socket.gethostname')
    def testGetHostAddress(self, *_):
        with patch('golem.core.hostaddress.socket.gethostbyname',
                   return_value='127.0.0.1'):
            self.assertGreater(len(get_host_address('127.0.0.1')), 0)
            self.assertTrue(is_ip_address(get_host_address(None, False)))

        with patch('golem.core.hostaddress.socket.gethostbyname',
                   return_value='::1'):
            self.assertTrue(is_ip_address(get_host_address(None, True)))
            self.assertTrue(is_ip_address(get_host_address("::1", True)))

    @unittest.skip("Find network testing framework")
    def testGetHostAddress2(self):
        self.assertEqual(get_host_address('10.30.100.100'), '10.30.10.216')
        self.assertEqual(get_host_address('10.30.10.217'), '10.30.10.216')

    def testGetIPNetworks(self):
        addresses = ipv4_networks()

        if addresses:
            for address in addresses:
                self.assertTrue(is_ip_address(address[0]), "Incorrect IP address: {}".format(address[0]))
                self.assertTrue(0 < int(address[1]) < 33, "Incorrect mask: {}".format(address[1]))

    @patch('netifaces.ifaddresses', side_effect=mock_ifaddresses)
    def testGetIPNetworks2(self, *_):
        ipv4_networks()

    def testIpAddressPrivate(self):
        self.assertTrue(ip_address_private('::1'))
        ipv6_private_pattern = 'fd{}::'
        for i in range(0, 256):
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
            ('10.0.0.0', 8),
            ('127.0.0.0', 8),
            ('172.16.0.0', 12),
            ('192.168.0.0', 16),
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
