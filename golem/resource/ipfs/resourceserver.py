import logging

from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.ipfs.resourcesmanager import IPFSResourceManager

logger = logging.getLogger(__name__)


class IPFSResourceServer(BaseResourceServer):
    def __init__(self, dir_manager, keys_auth, client, client_config=None):
        resource_manager = IPFSResourceManager(dir_manager, config=client_config)
        BaseResourceServer.__init__(self, resource_manager, dir_manager, keys_auth, client)
