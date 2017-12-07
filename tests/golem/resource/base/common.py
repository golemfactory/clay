import os
import uuid
from unittest import mock as mock

from golem_messages import message

from golem.client import Client
from golem.core.simplehash import SimpleHash
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.dirmanager import DirManager
from golem.task.taskserver import TaskServer
from golem.task.tasksession import TaskSession
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase


def fake_sign(_):
    return b'\000' * message.Message.SIG_LEN


def fake_decrypt(data):
    return data


class AddGetResources(TempDirFixture, LogTestCase):

    __test__ = False
    _resource_manager_class = None

    def setUp(self):
        TempDirFixture.setUp(self)
        LogTestCase.setUp(self)

        self.task_id = str(uuid.uuid4())

        client_1, dir_1, session_1 = self._create_client(self.task_id, '_1')
        client_2, dir_2, session_2 = self._create_client(self.task_id, '_2')

        self.client_1 = client_1
        self.client_2 = client_2
        self.resource_dir_1 = dir_1
        self.resource_dir_2 = dir_2
        self.task_session_1 = session_1
        self.task_session_2 = session_2

        self.resources_relative, resources = self._create_resources(
            self.resource_dir_1)
        client_1.resource_server.resource_manager._add_task(
            resources, self.task_id)

    def tearDown(self):
        self.client_1.quit()
        self.client_2.quit()

        LogTestCase.tearDown(self)
        TempDirFixture.tearDown(self)

    @staticmethod
    def _create_resources(resource_dir):
        relative = [
            'resource_1',
            os.path.join('dir_1', 'resource_2'),
            os.path.join('dir_1', 'resource_3'),
            os.path.join('dir_2', 'subdir', 'resource_4')
        ]

        absolute = [os.path.join(resource_dir, r) for r in relative]

        for resource in absolute:
            d = os.path.dirname(resource)
            os.makedirs(d, exist_ok=True)

            with open(resource, 'wb') as f:
                f.write(str(uuid.uuid4()).encode() * 256)

        return relative, absolute

    def _create_client(self, task_id, postfix):
        directory = os.path.join(self.tempdir, 'node' + postfix)
        dir_manager = DirManager(directory)

        cls = self._resource_manager_class
        resource_manager = cls.__new__(cls)
        resource_manager.__init__(dir_manager)

        client = Client(datadir=dir_manager.root_path,
                        connect_to_known_hosts=False,
                        use_docker_machine_manager=False,
                        use_monitor=False)
        client.resource_server = BaseResourceServer(resource_manager,
                                                    dir_manager,
                                                    mock.Mock(), client)
        client.task_server = TaskServer(mock.Mock(), mock.Mock(),
                                        client.keys_auth, client,
                                        use_docker_machine_manager=False)

        client.start = mock.Mock()
        client.start_network = mock.Mock()
        client.task_server.sync_network = mock.Mock()
        client.task_server.start_accepting = mock.Mock()
        client.task_server.task_computer = mock.Mock()

        task_session = TaskSession(mock.Mock(server=client.task_server))
        task_session.task_id = task_id

        resource_dir = resource_manager.storage.get_dir(task_id)
        return client, resource_dir, task_session

    def test(self):
        send_buf = []
        self.task_session_1.send = lambda x: send_buf.append(x)

        # session_2 [GetResource] -> session_1
        msg_get = message.GetResource(task_id=self.task_id)
        self.task_session_1._react_to_get_resource(msg_get)

        # session_1 [ResourceList] -> session_2
        msg_list = send_buf.pop()
        self.task_session_2._react_to_resource_list(msg_list)

        # client_2 downloads resources specified in the message
        self.client_2.resource_server._download_resources(async=False)

        # verify downloaded resources
        for relative_path in self.resources_relative:
            location_1 = os.path.join(self.resource_dir_1, relative_path)
            location_2 = os.path.join(self.resource_dir_2, relative_path)

            assert os.path.exists(location_1)
            assert os.path.exists(location_2)

            sha_256_1 = SimpleHash.hash_file_base64(location_1)
            sha_256_2 = SimpleHash.hash_file_base64(location_2)
            assert sha_256_1 == sha_256_2
