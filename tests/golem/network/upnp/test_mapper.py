from unittest import TestCase
from unittest.mock import Mock

from golem_messages.factories.datastructures import p2p as dt_p2p_factory

from golem.network.upnp.mapper import PortMapperManager, IPortMapper


class MockPortMapper(IPortMapper):

    def __init__(self, available=False, network=None, discover_raises=None):
        self._available = available
        self._network = network
        self._discover_raises = discover_raises

        self.available_calls = 0
        self.network_calls = 0
        self.discover_calls = 0
        self.get_mapping_calls = 0

    @property
    def available(self):
        self.available_calls += 1
        return self._available

    @property
    def network(self):
        self.network_calls += 1
        return self._network

    def discover(self):
        self.discover_calls += 1
        if self._discover_raises:
            raise RuntimeError("Test error")

    def get_mapping(self, external_port: int, protocol: str = 'TCP'):
        self.get_mapping_calls += 1
        return '10.0.0.10', 40102, True

    def create_mapping(self, local_port, external_port=None,
                       protocol='TCP', lease_duration=None):
        pass

    def remove_mapping(self, port, external_port, protocol='TCP'):
        pass


class TestPortMapperManagerDiscovery(TestCase):

    def test_discover(self):
        mapper = MockPortMapper(available=True)
        manager = PortMapperManager(mappers=[mapper])

        manager.discover()
        assert manager.available
        assert manager._active_mapper is mapper

    def test_discover_failure(self):
        mapper = MockPortMapper(available=False)
        manager = PortMapperManager(mappers=[mapper])

        manager.discover()
        assert not manager._active_mapper
        assert not manager.available

    def test_discover_calls(self):
        mappers = [
            MockPortMapper(available=False, discover_raises=Exception),
            MockPortMapper(available=False),
            MockPortMapper(available=False),
        ]

        manager = PortMapperManager(mappers=mappers)
        manager.discover()
        assert all(mapper.discover_calls == 1 for mapper in mappers)


class TestPortMapperManagerCreateMapping(TestCase):

    def test_create_mapping_not_available(self):
        manager = PortMapperManager(mappers=[MockPortMapper()])
        assert manager.create_mapping(40102) is None

    def test_create_mapping_failure(self):
        mapper = MockPortMapper(available=True)
        mapper.create_mapping = Mock(side_effect=Exception)
        manager = PortMapperManager(mappers=[mapper])

        manager._active_mapper = mapper
        assert manager.create_mapping(40102) is None

    def test_create_mapping(self):
        mapper = MockPortMapper(available=True)
        mapper.create_mapping = Mock(return_value=50102)
        manager = PortMapperManager(mappers=[mapper])

        manager._active_mapper = mapper
        assert manager.create_mapping(40102) == 50102


class TestPortMapperManagerRemoveMapping(TestCase):

    def test_remove_mapping_not_available(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        assert manager.remove_mapping(40102, 40102) is False

    def test_remove_mapping_failure(self):
        mapper = MockPortMapper(available=True)
        mapper.remove_mapping = Mock(side_effect=Exception)

        manager = PortMapperManager(mappers=[mapper])
        manager._active_mapper = mapper
        assert manager.remove_mapping(40102, 40102) is False

    def test_remove_mapping(self):
        mapper = MockPortMapper(available=True)
        mapper.remove_mapping = Mock(return_value=True)

        manager = PortMapperManager(mappers=[mapper])
        manager._active_mapper = mapper
        manager._mapping = {
            'TCP': {
                40102: 40102,
                40103: 40103,
                3282: 3282
            },
            'UDP': {},
        }
        assert manager.remove_mapping(40102, 40102) is True


class TestPortMapperManagerQuit(TestCase):

    def test_quit_not_available(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        manager.remove_mapping = Mock()

        manager.quit()
        assert not manager.remove_mapping.called

    def test_quit_available_no_mapping(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        manager.remove_mapping = Mock()
        manager._active_mapper = manager._mappers[0]

        manager.quit()
        assert not manager.remove_mapping.called

    def test_quit(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        manager.remove_mapping = Mock()
        manager._active_mapper = mapper
        manager._mapping = {
            'TCP': {
                40102: 40102,
                40103: 40103,
                3282: 3282
            },
            'UDP': {
                40102: 40102,
                40103: 40103,
                3282: 3282
            },
        }

        manager.quit()
        assert manager.remove_mapping.call_count == sum(
            len(m) for m in manager._mapping.values()
        )


class TestPortMapperUpdateNode(TestCase):

    def setUp(self):
        self.node = dt_p2p_factory.Node(
            prv_port=40102, pub_port=50102,
            p2p_prv_port=40103, p2p_pub_port=50103
        )

    def test_update_node(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        manager._mapping = {
            'TCP': {
                40102: 60102,
                40103: 60103,
                3282: 6282
            }
        }

        manager.update_node(self.node)
        assert self.node.pub_port == 60102
        assert self.node.p2p_pub_port == 60103

    def test_update_node_without_mapping(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])

        manager.update_node(self.node)
        assert self.node.pub_port == 50102
        assert self.node.p2p_pub_port == 50103


class TestPortMapperManagerProperties(TestCase):

    def test_available(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        assert not manager.available
        manager._active_mapper = Mock()
        assert manager.available

    def test_network(self):
        network_dict = {
            'local_ip_address': '192.168.0.10',
            'external_ip_address': '1.2.3.4',
            'connection_type': dict(),
            'status_info': dict()
        }

        mapper = MockPortMapper(network=network_dict)
        manager = PortMapperManager(mappers=[mapper])

        assert manager.network == dict()
        manager._active_mapper = mapper
        assert manager.network == network_dict

    def test_mapping(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])

        assert manager.mapping == manager._mapping
        assert manager.mapping is not manager._mapping


class TestPortMapperManagerGetMapping(TestCase):

    def test_available(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        manager._active_mapper = mapper
        assert manager.get_mapping(40102)
        assert mapper.get_mapping_calls == 1

    def test_not_available(self):
        mapper = MockPortMapper()
        manager = PortMapperManager(mappers=[mapper])
        assert not manager.get_mapping(40102)
        assert mapper.get_mapping_calls == 0

    def test_exception(self):
        mapper = MockPortMapper()
        mapper.get_mapping = Mock(side_effect=Exception('Test exception'))
        manager = PortMapperManager(mappers=[mapper])
        manager._active_mapper = mapper
        assert not manager.get_mapping(40102)
