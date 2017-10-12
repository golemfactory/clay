import uuid
from unittest import skipIf, TestCase

from mock import Mock
from requests import ConnectionError

from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.base.resourcetest import AddGetResources
from golem.resource.hyperdrive.resourcesmanager import \
    HyperdriveResourceManager, HyperdrivePeerManager


def running():
    try:
        return HyperdriveClient().id()
    except ConnectionError:
        return False


class TestHyperdrivePeerManager(TestCase):

    def test(self):
        own_address = {'TCP': ('1.1.1.1', 3282)}
        peer_address = {'TCP': ('1.2.3.4', 3282)}

        metadata = {'hyperg': peer_address}
        task_id = str(uuid.uuid4())

        node = Mock()
        node.key = str(uuid.uuid4())

        peer_manager = HyperdrivePeerManager(own_address)
        peer_manager.interpret_metadata(metadata, None, None, node)

        assert len(peer_manager._peers) == 1
        assert len(peer_manager._tasks) == 0
        assert len(peer_manager.get_for_task(task_id)) == 1

        peer_manager.interpret_metadata(metadata, None, None, node)

        assert len(peer_manager._peers) == 1
        assert len(peer_manager._tasks) == 0
        assert len(peer_manager.get_for_task(task_id)) == 1

        peer_manager.add(task_id, node.key)

        assert len(peer_manager._peers) == 1
        assert len(peer_manager._tasks) == 1
        assert len(peer_manager.get_for_task(task_id)) == 2

        peer_manager.remove(task_id, node.key)

        assert len(peer_manager._peers) == 0
        assert len(peer_manager._tasks) == 1
        assert len(peer_manager.get_for_task(task_id)) == 1


@skipIf(not running(), "Hyperdrive daemon isn't running")
class TestHyperdriveResources(AddGetResources):
    __test__ = True
    _resource_manager_class = HyperdriveResourceManager

