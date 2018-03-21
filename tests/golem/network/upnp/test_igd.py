from types import MethodType
from unittest import TestCase
from unittest.mock import Mock, patch

from golem.network.upnp.igd import IGDPortMapper


@patch('miniupnpc.UPnP')
class TestIGDPortMapper(TestCase):

    def test_available(self, *_):
        mapper = IGDPortMapper()

        assert mapper._available is None
        assert not mapper.available

        mapper._available = False
        assert not mapper.available

        mapper._available = True
        assert mapper.available

    def test_network(self, *_):
        mapper = IGDPortMapper()
        keys = [
            'local_ip_address',
            'external_ip_address',
            'connection_type',
            'status_info'
        ]

        network = mapper.network
        assert all(key in network for key in keys)

    def test_discover(self, *_):
        mapper = IGDPortMapper()

        mapper.upnp.discover.return_value = 0
        with self.assertRaises(RuntimeError):
            mapper.discover()
        assert not mapper.available

        mapper.upnp.discover.return_value = 1
        mapper.discover()
        assert mapper.available

    def test_create_mapping(self, *_):
        mapping = '10.0.0.10', 40112, 'desc', True, 3600
        mapper = IGDPortMapper()
        mapper._mapping_exists = Mock(return_value=False)

        mapper.upnp.addanyportmapping.side_effect = Exception
        mapper.upnp.addportmapping.return_value = 41102
        mapper.upnp.getspecificportmapping = lambda x, *_: \
            None if x == 41102 else mapping

        assert mapper.create_mapping(40102, 40102) == 41102
        assert mapper.create_mapping(40102, 40112) == 41102
        assert mapper.create_mapping(40102) == 41102

        mapper.upnp.addanyportmapping.side_effect = lambda *_: 45555
        assert mapper.create_mapping(40102, 40102) == 45555
        assert mapper.create_mapping(40102, 40112) == 45555
        assert mapper.create_mapping(40102) == 45555

    def test_create_mapping_exists(self, *_):
        mapper = IGDPortMapper()
        mapper._mapping_exists = Mock(return_value=True)

        assert mapper.create_mapping(40102, 40102) == 40102
        assert mapper.create_mapping(40102, 40112) == 40112

    def test_mapping_exists_failure(self, *_):
        mapper = IGDPortMapper()

        mapper.get_mapping = Mock(return_value=None)

        assert not mapper._mapping_exists(40102, 40102, protocol='TCP')
        assert not mapper._mapping_exists(40102, 40102, protocol='UDP')
        assert not mapper._mapping_exists(40102, 40112, protocol='TCP')

        mapper.get_mapping = Mock(return_value=Exception)

        assert not mapper._mapping_exists(40102, 40102, protocol='TCP')
        assert not mapper._mapping_exists(40102, 40102, protocol='UDP')
        assert not mapper._mapping_exists(40102, 40112, protocol='TCP')

    def test_mapping_exists(self, *_):

        def upnp_get_port_mapping(_self, external_port, protocol):
            if external_port == 40112 and protocol == 'TCP':
                return '10.0.0.10', 40102, 'desc', True, 3600
            return '10.0.0.11', 40112, 'desc', True, 3600

        mapper = IGDPortMapper()
        mapper.upnp.lanaddr = '10.0.0.10'
        mapper.upnp.externalipaddress = Mock(return_value='1.2.3.4')
        mapper.upnp.connectiontype = Mock(return_value='')
        mapper.upnp.statusinfo = Mock(return_value='')
        mapper.upnp.getspecificportmapping = MethodType(upnp_get_port_mapping,
                                                        mapper.upnp)

        assert not mapper._mapping_exists(40102, 40102)
        assert not mapper._mapping_exists(40102, 40112, protocol='UDP')
        assert mapper._mapping_exists(40102, 40112, protocol='TCP')
        assert mapper._mapping_exists(40102, 40112)

    def test_remove_mapping(self, *_):
        mapper = IGDPortMapper()

        obj = object()
        mapper.upnp.deleteportmapping.return_value = obj

        assert mapper.remove_mapping(40102, 40102) is obj

    def test_find_free_port(self, *_):
        mapping = '10.0.0.10', 40112, 'desc', True, 3600

        mapper = IGDPortMapper()
        mapper.upnp.getspecificportmapping.return_value = mapping

        with self.assertRaises(RuntimeError):
            mapper._find_free_port(40102, 'TCP')

        mapper.upnp.getspecificportmapping.side_effect = lambda x, *_: \
            None if x == 40112 else mapping

        assert mapper._find_free_port(40102, 'TCP') == 40112

        mapper.upnp.getspecificportmapping.side_effect = lambda x, *_: \
            None if x == 1025 else mapping

        assert mapper._find_free_port(40102, 'TCP') == 1025
