import unittest
from mock import Mock
from golem.resource.resourceserver import ResourceServer


class TestResourceServer(unittest.TestCase):

    def test_resource_server_datadir(self):
        client = Mock()
        client.datadir = "great/datadir"
        rs = ResourceServer(Mock(), Mock(), client)
        assert rs.dir_manager.root_path == client.datadir
