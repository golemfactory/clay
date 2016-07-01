import logging
import os

from golem.network.ipfs.client import IPFSClientHandler, IPFSClient, IPFSConfig
from golem.resource.base.resourcesmanager import BaseAbstractResourceManager

logger = logging.getLogger(__name__)


def to_unicode(source):
    if not isinstance(source, unicode):
        return unicode(source)
    return source


class IPFSResourceManager(BaseAbstractResourceManager, IPFSClientHandler):

    def __init__(self, dir_manager,
                 config=None,
                 resource_dir_method=None):

        IPFSClientHandler.__init__(self, config or IPFSConfig())
        BaseAbstractResourceManager.__init__(self, dir_manager, resource_dir_method)

    def add_resource_dir(self, dir_name,
                         client=None, client_options=None):
        if not client:
            client = self.new_client()

        dir_name = os.path.normpath(dir_name)
        task_ids = self.dir_manager.list_task_ids_in_dir(dir_name)

        for task_id in task_ids:
            self.add_resource(task_id,
                              task_id=task_id,
                              client=client,
                              client_options=client_options)

    def pin_resource(self, multihash, client=None, client_options=None):
        if not client:
            client = self.new_client()
        return self._handle_retries(client.pin_add,
                                    self.commands.pin,
                                    multihash)

    def unpin_resource(self, multihash, client=None, client_options=None):
        if not client:
            client = self.new_client()
        return self._handle_retries(client.pin_rm,
                                    self.commands.unpin,
                                    multihash)

    def build_client_options(self, node_id, **kwargs):
        return IPFSClient.build_options(node_id, **kwargs)

