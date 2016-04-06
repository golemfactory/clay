from mock import Mock
from golem.testutils import TempDirFixture
from golem.resource.resourceserver import ResourceServer


class TestResourceServer(TempDirFixture):

    def test_resource_server_datadir(self):
        client = Mock()
        client.datadir = self.tempdir
        rs = ResourceServer(Mock(), Mock(), client)
        assert rs.dir_manager.root_path == client.datadir
