import sys
import unittest

from golem.network.transport.tcpnetwork import TCPAddress


class TestTCPAddressParsing(unittest.TestCase):
    """Test suite for TCPAddress.parse()"""

    def __expect_exception(self, value, exception):
        try:
            TCPAddress.parse(value)
            suffix = ', not succeed'
        except exception:
            return
        except:
            exc = sys.exc_info()[0]
            suffix = ', not ' + exc.__name__

        self.fail('TCPAddress.parse("' + str(value) +
                  '") should raise ' + exception.__name__ +
                  suffix)

    def __expect_valid(self, value):
        if value[0] == '[':
            addr, port = value.split(']:')
            addr = addr[1:-1]
        else:
            addr, port = value.split(':')
        a = TCPAddress.parse(value)
        self.assertTrue(a.address == addr)
        self.assertTrue(a.port == int(port))

    def test_type_error(self):
        self.__expect_exception(None, TypeError)
        self.__expect_exception(5, TypeError)

    def test_empty(self):
        self.__expect_exception('', ValueError)

    def test_ipv4_bad_port(self):
        self.__expect_exception('1.2.3.4', ValueError)
        self.__expect_exception('1.2.3.4:', ValueError)
        self.__expect_exception('1.2.3.4:0xdead', ValueError)

    def test_ipv4_port_out_of_range(self):
        self.__expect_exception('1.2.3.4:-1', ValueError)
        self.__expect_exception('1.2.3.4:0', ValueError)
        self.__expect_exception('1.2.3.4:65536', ValueError)
        self.__expect_exception('1.2.3.4:6553665536655366553665536', ValueError)

    def test_bad_ip4(self):
        self.__expect_exception('1.2.3:40102', ValueError)
        self.__expect_exception('1.2.3.4.:40102', ValueError)
        self.__expect_exception('.1.2.3.4:40102', ValueError)
        self.__expect_exception('1..2.3.4:40102', ValueError)
        self.__expect_exception('1..3.4:40102', ValueError)
        self.__expect_exception('1.2.3.256:40102', ValueError)

    def test_bad_ipv6(self):
        self.__expect_exception('[0:1:2:3:4:5:6]:1', ValueError)
        self.__expect_exception('[0:1:2:3:4:5:6:7:8]:1', ValueError)
        self.__expect_exception('[0:1:2:33333:4:5:6:7]:1', ValueError)
        self.__expect_exception('[0:1:2:-3:4:5:6:7]:1', ValueError)

    def test_bad_hostname(self):
        self.__expect_exception('-golem.net:1111', ValueError)
        self.__expect_exception('golem-.net:1111', ValueError)
        self.__expect_exception('0001:1111', ValueError)
        self.__expect_exception('x' * 64, ValueError)
        self.__expect_exception('x' + ('.x' * 127), ValueError)
        self.__expect_exception('www.underscores_not_allowed.com', ValueError)

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

    def test_valid_hostname(self):
        self.__expect_valid('localhost:40102')
        self.__expect_valid('0golem-node0:40102')
        self.__expect_valid('0.a.b.c.d.e.f.g.h:40102')
        self.__expect_valid('x' * 63 + ':40102')
        self.__expect_valid('x' + ('.x' * 127) + ':40102')
        # TODO: should we allow this one?
        self.__expect_valid('trailing.dot.is.allowed.:40102')
