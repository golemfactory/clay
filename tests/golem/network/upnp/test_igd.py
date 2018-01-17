from unittest import TestCase
from unittest.mock import patch

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
        mapper = IGDPortMapper()

        mapper.upnp.addanyportmapping.side_effect = Exception
        mapper.upnp.addportmapping.return_value = 41102
        mapper.upnp.getspecificportmapping = lambda x, *_: \
            False if x == 41102 else True

        assert mapper.create_mapping(40102, 40102) == 41102
        assert mapper.create_mapping(40102, 40112) == 41102
        assert mapper.create_mapping(40102) == 41102

        mapper.upnp.addanyportmapping.side_effect = lambda *_: 45555
        assert mapper.create_mapping(40102, 40102) == 45555
        assert mapper.create_mapping(40102, 40112) == 45555
        assert mapper.create_mapping(40102) == 45555

    def test_remove_mapping(self, *_):
        mapper = IGDPortMapper()

        obj = object()
        mapper.upnp.deleteportmapping.return_value = obj

        assert mapper.remove_mapping(40102) is obj

    def test_find_free_port(self, *_):
        mapper = IGDPortMapper()
        mapper.upnp.getspecificportmapping.return_value = True

        with self.assertRaises(RuntimeError):
            mapper._find_free_port(40102, 'TCP')

        mapper.upnp.getspecificportmapping.side_effect = lambda x, *_: \
            False if x == 40112 else True

        assert mapper._find_free_port(40102, 'TCP') == 40112

        mapper.upnp.getspecificportmapping.side_effect = lambda x, *_: \
            False if x == 1025 else True

        assert mapper._find_free_port(40102, 'TCP') == 1025
