import os
import uuid

from mock import Mock

from golem.client import Client
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.client import file_sha_256
from golem.resource.dirmanager import DirManager
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.utils import encode_hex


class AddGetResources(TempDirFixture, LogTestCase):

    __test__ = False
    _resource_manager_class = None

    @staticmethod
    def _create_resources(resource_dir):

        resources_relative = [
            'resource_1',
            os.path.join('dir_1', 'resource_2'),
            os.path.join('dir_1', 'resource_3'),
            os.path.join('dir_2', 'subdir', 'resource_4')
        ]

        resources = [os.path.join(resource_dir, r) for r in resources_relative]

        for resource in resources:
            d = os.path.dirname(resource)
            if not os.path.exists(d):
                os.makedirs(d)

            with open(resource, 'wb') as f:
                f.write(str(uuid.uuid4()).encode() * 256)

        return resources_relative, resources

    @classmethod
    def _create_server(cls, datadir, task_id):
        dir_manager = DirManager(datadir)
        resource_manager = cls._resource_manager_class(dir_manager)

        client = Client(datadir=datadir,
                        connect_to_known_hosts=False,
                        use_docker_machine_manager=False,
                        use_monitor=False)

        resource_dir = resource_manager.storage.get_dir(task_id)
        resource_server = BaseResourceServer(resource_manager,
                                             dir_manager,
                                             Mock(), client)
        client.start = Mock()
        client.start_network = Mock()
        client.task_server = Mock()
        client.resource_server = resource_server

        return resource_server, resource_dir

    def setUp(self):
        TempDirFixture.setUp(self)
        LogTestCase.setUp(self)

        self.task_id = str(uuid.uuid4())
        self.datadir_1 = os.path.join(self.tempdir, 'node_1')
        self.datadir_2 = os.path.join(self.tempdir, 'node_2')

        self.resource_server_1, self.resource_dir_1 = self._create_server(
            self.datadir_1, self.task_id)
        self.resource_server_2, self.resource_dir_2 = self._create_server(
            self.datadir_2, self.task_id)

        resource_manager = self.resource_server_1.resource_manager
        self.client_options = resource_manager.build_client_options('node_1')

        self.resources_relative, self.resources = self._create_resources(
            self.resource_dir_1)

    def tearDown(self):
        self.resource_server_1.client.quit()
        self.resource_server_2.client.quit()
        LogTestCase.tearDown(self)
        TempDirFixture.tearDown(self)

    def test(self):

        rm = self.resource_server_1.resource_manager
        rm._add_task(self.resources, self.task_id)

        to_download = rm.get_resources(self.task_id)
        to_download = rm.to_wire(to_download)
        to_download = rm.from_wire(to_download)

        self.resource_server_2.download_resources(to_download,
                                                  self.task_id,
                                                  self.client_options)
        self.resource_server_2._download_resources(async=False)

        for r in self.resources_relative:
            location_1 = os.path.join(self.resource_dir_1, r)
            location_2 = os.path.join(self.resource_dir_2, r)

            assert os.path.exists(location_1)
            assert os.path.exists(location_2)

            sha_256_1 = file_sha_256(location_1)
            sha_256_2 = file_sha_256(location_2)
            assert sha_256_1 == sha_256_2, '{} != {}'.format(
                encode_hex(sha_256_1), encode_hex(sha_256_2))
