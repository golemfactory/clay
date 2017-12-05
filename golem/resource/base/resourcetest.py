import os
import unittest.mock as mock
import uuid

from golem_messages import message

from golem.client import Client
from golem.core.simplehash import SimpleHash
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.dirmanager import DirManager
from golem.task.taskserver import TaskServer
from golem.task.tasksession import TaskSession
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

    def setUp(self):
        TempDirFixture.setUp(self)
        LogTestCase.setUp(self)

        self.task_id = str(uuid.uuid4())

        self.datadir_1 = os.path.join(self.tempdir, 'node_1')
        self.datadir_2 = os.path.join(self.tempdir, 'node_2')

        self.dir_manager_1 = DirManager(self.datadir_1)
        self.dir_manager_2 = DirManager(self.datadir_2)

        self.resource_manager_1 = self._resource_manager_class(
            self.dir_manager_1)
        self.resource_manager_2 = self._resource_manager_class(
            self.dir_manager_2)

        self.client_1 = Client(datadir=self.datadir_1,
                               connect_to_known_hosts=False,
                               use_docker_machine_manager=False,
                               use_monitor=False)
        self.client_2 = Client(datadir=self.datadir_2,
                               connect_to_known_hosts=False,
                               use_docker_machine_manager=False,
                               use_monitor=False)

        self.client_1.start = self.client_2.start = mock.Mock()
        self.client_1.start_network = self.client_2.start_network = mock.Mock()

        self.resource_server_1 = BaseResourceServer(self.resource_manager_1,
                                                    self.dir_manager_1,
                                                    mock.Mock(), self.client_1)
        self.resource_server_2 = BaseResourceServer(self.resource_manager_2,
                                                    self.dir_manager_2,
                                                    mock.Mock(), self.client_2)

        self.resource_server_1.client.resource_server = self.resource_server_1
        self.resource_server_2.client.resource_server = self.resource_server_2

        task_server_1 = TaskServer(mock.Mock(), mock.Mock(),
                                   self.client_1.keys_auth, self.client_1,
                                   use_docker_machine_manager=False)
        task_server_2 = TaskServer(mock.Mock(), mock.Mock(),
                                   self.client_2.keys_auth, self.client_2,
                                   use_docker_machine_manager=False)

        task_server_1.sync_network = task_server_2.sync_network = mock.Mock()
        task_server_1.start_accepting = task_server_2.start_accepting\
            = mock.Mock()
        task_server_1.task_computer = task_server_2.task_computer = mock.Mock()

        self.client_1.task_server = task_server_1
        self.client_2.task_server = task_server_2

        self.task_session_1 = TaskSession(mock.Mock())
        self.task_session_2 = TaskSession(mock.Mock())
        self.task_session_1.task_server = task_server_1
        self.task_session_2.task_server = task_server_2
        self.task_session_1.task_id = self.task_session_2.task_id = self.task_id

        self.resource_dir_1 = self.resource_manager_1.storage.get_dir(
            self.task_id)
        self.resource_dir_2 = self.resource_manager_2.storage.get_dir(
            self.task_id)

        self.resources_relative, self.resources = self._create_resources(
            self.resource_dir_1)
        self.resource_manager_1._add_task(self.resources, self.task_id)

    def tearDown(self):
        self.client_1.quit()
        self.client_2.quit()
        LogTestCase.tearDown(self)
        TempDirFixture.tearDown(self)

    def test(self):

        send_buf_1 = []
        send_buf_2 = []

        self.task_session_1.send = lambda x: send_buf_1.append(x)
        self.task_session_2.send = lambda x: send_buf_2.append(x)

        fake_sign = lambda x: b'\000' * message.Message.SIG_LEN

        msg_get_resource = message.GetResource(task_id=self.task_id)
        msg = message.GetResource.deserialize(
            msg_get_resource.serialize(fake_sign),
            lambda x: x
        )
        assert msg

        self.task_session_1._react_to_get_resource(msg)

        msg_resource_list = send_buf_1.pop()
        msg = message.ResourceList.deserialize(
            msg_resource_list.serialize(fake_sign),
            lambda x: x
        )
        assert msg

        self.task_session_2._react_to_resource_list(msg)
        self.resource_server_2._download_resources(async=False)

        for r in self.resources_relative:
            location_1 = os.path.join(self.resource_dir_1, r)
            location_2 = os.path.join(self.resource_dir_2, r)

            assert os.path.exists(location_1)
            assert os.path.exists(location_2)

            sha_256_1 = SimpleHash.hash_file_base64(location_1)
            sha_256_2 = SimpleHash.hash_file_base64(location_2)
            assert sha_256_1 == sha_256_2, '{} != {}'.format(
                encode_hex(sha_256_1), encode_hex(sha_256_2))
