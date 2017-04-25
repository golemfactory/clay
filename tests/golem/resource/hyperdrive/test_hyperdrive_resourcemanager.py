from unittest import skipIf

from requests import ConnectionError

from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.base.resourcetest import AddGetResources
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager


def running():
    try:
        return HyperdriveClient().id()
    except ConnectionError:
        return False


@skipIf(not running(), "Hyperdrive daemon isn't running")
class TestHyperdriveResources(AddGetResources):
    __test__ = True
    _resource_manager_class = HyperdriveResourceManager
