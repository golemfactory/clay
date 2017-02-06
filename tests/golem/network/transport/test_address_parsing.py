import sys
import unittest
from ipaddress import AddressValueError

from golem.network.transport.tcpnetwork import SocketAddress


class TestSocketAddressParsing(unittest.TestCase):
    """Test suite for SocketAddress.parse()"""

    def __expect_exception(self, value, exception):
        try:
            SocketAddress.parse(value)
            suffix = ', not succeed'
        except exception:
            return
        except:
            exc = sys.exc_info()[0]
            suffix = ', not ' + exc.__name__

        self.fail('SocketAddress.parse("' + str(value) +
                  '") should raise ' + exception.__name__ +
                  suffix)

    def __expect_valid(self, value):
        if value[0] == '[':
            addr, port = value.split(']:')
            addr = addr[1:]
        else:
            addr, port = value.split(':')
        a = SocketAddress.parse(value)
        self.assertTrue(a.address == addr)
        self.assertTrue(a.port == int(port))

    def test_type_error(self):
        self.__expect_exception(None, TypeError)
        self.__expect_exception(5, TypeError)

    def test_empty(self):
        self.__expect_exception('', AddressValueError)

    def test_ipv4_bad_port(self):
        self.__expect_exception('1.2.3.4', AddressValueError)
        self.__expect_exception('1.2.3.4:', AddressValueError)
        self.__expect_exception('1.2.3.4:0xdead', AddressValueError)

    def test_ipv4_port_out_of_range(self):
        self.__expect_exception('1.2.3.4:-1', AddressValueError)
        self.__expect_exception('1.2.3.4:0', AddressValueError)
        self.__expect_exception('1.2.3.4:65536', AddressValueError)
        self.__expect_exception('1.2.3.4:65536655366536655366553', AddressValueError)

    def test_bad_ip4(self):
        self.__expect_exception('1.2.3:40102', AddressValueError)
        self.__expect_exception('1.2.3.4.:40102', AddressValueError)
        self.__expect_exception('.1.2.3.4:40102', AddressValueError)
        self.__expect_exception('1..2.3.4:40102', AddressValueError)
        self.__expect_exception('1..3.4:40102', AddressValueError)
        self.__expect_exception('1.2.3.256:40102', AddressValueError)

    def test_bad_ipv6(self):
        self.__expect_exception('[0:1:2:3:4:5:6]:1', AddressValueError)
        self.__expect_exception('[0:1:2:3:4:5:6:7:8]:1', AddressValueError)
        self.__expect_exception('[0:1:2:33333:4:5:6:7]:1', AddressValueError)
        self.__expect_exception('[0:1:2:-3:4:5:6:7]:1', AddressValueError)

    def test_bad_hostname(self):
        self.__expect_exception('-golem.net:1111', AddressValueError)
        self.__expect_exception('golem-.net:1111', AddressValueError)
        self.__expect_exception('0001:1111', AddressValueError)
        self.__expect_exception('x' * 64, AddressValueError)
        self.__expect_exception('x' + ('.x' * 127), AddressValueError)
        self.__expect_exception('www.underscores_not_allowed.com', AddressValueError)

    def test_valid_ipv4(self):
        self.__expect_valid('11.22.33.44:1')
        self.__expect_valid('11.22.33.44:001')
        self.__expect_valid('11.22.33.44:65535')
        self.__expect_valid('0.0.0.0:40102')
        self.__expect_valid('255.255.255.255:40102')

    def test_valid_ipv6(self):
        self.__expect_valid('[0:1a:2B:c3:D4:555:ffff:0000]:1')
        self.__expect_valid('[::1a:2B:c3:D4:555:ffff:0000]:1')
        self.__expect_valid('[0::c3:D4:555:ffff:0000]:1')
        self.__expect_valid('[0:1:2:3:4:5:6:7]:1')
        self.__expect_valid('[::7]:1')

    def test_valid_hostname(self):
        self.__expect_valid('localhost:40102')
        self.__expect_valid('0golem-node0:40102')
        self.__expect_valid('0.a.b.c.d.e.f.g.h:40102')
        self.__expect_valid('x' * 63 + ':40102')
        self.__expect_valid('x' + ('.x' * 127) + ':40102')
        # TODO: should we allow this one?
        self.__expect_valid('trailing.dot.is.allowed.:40102')

    def test_is_proper_address(self):
        import socket
        from struct import pack
        from random import randint
        from ipaddress import IPv6Address
        for i in range(5000):
            assert SocketAddress.is_proper_address(
                socket.inet_ntoa(pack('>I', randint(0, 16777215))),
                randint(1, 10000)
            )
        for i in range(5000):
            assert SocketAddress.is_proper_address(
                str(IPv6Address(randint(0, 2 ** 128 - 1))),
                randint(1, 10000)
            )
        assert not SocketAddress.is_proper_address('1.2.3.4', '')
        assert not SocketAddress.is_proper_address('1.2.3.4', None)
        assert not SocketAddress.is_proper_address('1.2.3.4', '0xdead')
        assert not SocketAddress.is_proper_address('1.2.3.4', '-1')
        assert not SocketAddress.is_proper_address('1.2.3.4', '0')
        assert not SocketAddress.is_proper_address('1.2.3.4', '65536')
        assert not SocketAddress.is_proper_address('1.2.3.4', '65536655366536655366553')
        assert not SocketAddress.is_proper_address('1.2.3:40102', '')
        assert not SocketAddress.is_proper_address('1.2.3.4.', '40102')
        assert not SocketAddress.is_proper_address('.1.2.3.4', '40102')
        assert not SocketAddress.is_proper_address('1..2.3.4', '40102')
        assert not SocketAddress.is_proper_address('1..3.4:40102', '2')
        assert not SocketAddress.is_proper_address('1.2.3.256', '40102')
        assert not SocketAddress.is_proper_address('[0:1:2:3:4:5:6]', '1')
        assert not SocketAddress.is_proper_address('[0:1:2:3:4:5:6:7:8]', '1')
        assert not SocketAddress.is_proper_address('[0:1:2:33333:4:5:6:7]', '1')
        assert not SocketAddress.is_proper_address('[0:1:2:-3:4:5:6:7]', '1')

    def test_valid_hostname(self):
        SocketAddress.validate_hostname('localhost')
        SocketAddress.validate_hostname('0golem-node0')
        SocketAddress.validate_hostname('0.a.b.c.d.e.f.g.h')
        SocketAddress.validate_hostname('x' * 63)
        SocketAddress.validate_hostname('x' + ('.x' * 127))
        SocketAddress.validate_hostname('trailing.dot.is.allowed.')

        with self.assertRaises(ValueError):
            SocketAddress.validate_hostname('-golem.net:1111')
        with self.assertRaises(ValueError):
            SocketAddress.validate_hostname('golem-.net:1111')
        with self.assertRaises(ValueError):
            SocketAddress.validate_hostname('0001:1111')
        with self.assertRaises(ValueError):
            SocketAddress.validate_hostname('x' * 64)
        with self.assertRaises(ValueError):
            SocketAddress.validate_hostname('www.underscores_not_allowed.com')
