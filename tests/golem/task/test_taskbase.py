import unittest
import warnings
from golem.task.taskbase import TaskHeader
from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.environments.environment import Environment


class TaskHeaderTest(unittest.TestCase):

    def setUp(self):
        self.env = Environment()
        self.env.accept_tasks = True
        self.client = Client(ClientConfigDescriptor())
        self.client.environments_manager.add_environment(self.env)

    def test_min_version_accepted(self):
        self.client.config_desc.app_version = 111
        th = TaskHeader(0, 0, "addr", 0, 0, self.env.get_id(), min_version=111)
        assert self.client.supported_task(th.__dict__)

    def test_min_version_accepted_long(self):
        self.client.config_desc.app_version = 111
        th = TaskHeader(0, 0, "addr", 0, 0, self.env.get_id(), min_version=99L)
        assert self.client.supported_task(th.__dict__)

    def test_min_version_rejected(self):
        self.client.config_desc.app_version = 99
        th = TaskHeader(0, 0, "addr", 0, 0, self.env.get_id(), min_version=100)
        assert not self.client.supported_task(th.__dict__)

    def test_min_version_invalid(self):
        """Do not accept min_version not being integer"""
        with self.assertRaises(AssertionError):
            TaskHeader(0, 0, "addr", 0, 0, self.env.get_id(), min_version=1.1)


class TaskHeaderDeprecatedTest(unittest.TestCase):
    def test_owner_key_id_deprecated(self):
        th = TaskHeader(0, 0, "addr", 0, 0, 'env')
        with warnings.catch_warnings(record=True) as w:
            th.task_owner_key_id = 'deprecated'
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            key = th.task_owner_key_id
            assert len(w) == 2
            assert issubclass(w[-1].category, DeprecationWarning)
        assert key == 'deprecated'

    def test_owner_address_deprecated(self):
        th = TaskHeader(0, 0, "addr", 0, 0, 'env')
        with warnings.catch_warnings(record=True) as w:
            th.task_owner_address = 'deprecated-addr'
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            addr = th.task_owner_address
            assert len(w) == 2
            assert issubclass(w[-1].category, DeprecationWarning)
        assert addr == 'deprecated-addr'

    def test_owner_port_deprecated(self):
        th = TaskHeader(0, 0, "addr", 0, 0, 'env')
        with warnings.catch_warnings(record=True) as w:
            th.task_owner_port = 8080
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            addr = th.task_owner_port
            assert len(w) == 2
            assert issubclass(w[-1].category, DeprecationWarning)
        assert addr == 8080
