import logging
import os

from golem.network.ipfs.client import IPFSClientHandler, IPFSClient, IPFSConfig
from golem.resource.base.resourcesmanager import AbstractResourceManager, dir_files

logger = logging.getLogger(__name__)


class IPFSResourceManager(AbstractResourceManager, IPFSClientHandler):

    def __init__(self, dir_manager,
                 config=None,
                 resource_dir_method=None):

        IPFSClientHandler.__init__(self, config or IPFSConfig())
        AbstractResourceManager.__init__(self, dir_manager, resource_dir_method)

    def index_resources(self, dir_name, client=None, client_options=None):
        dir_name = os.path.normpath(dir_name)
        task_ids = self.storage.list_dir(dir_name)

        for task_id in task_ids:
            # FIXME: review directory structure
            if 'benchmark' in task_id:
                continue
            try:
                task_root_dir = self.storage.dir_manager.get_task_resource_dir(task_id)
                self._add_task(dir_files(task_root_dir), task_id)
            except Exception as e:
                logger.warn("Couldn't load task resources ({}): {}"
                            .format(task_id, e))

    def pin_resource(self, multihash, client=None, client_options=None):
        if not client:
            client = self.new_client()
        return self._handle_retries(client.pin_add,
                                    self.commands.pin_add,
                                    multihash)

    def unpin_resource(self, multihash, client=None, client_options=None):
        if not client:
            client = self.new_client()
        return self._handle_retries(client.pin_rm,
                                    self.commands.pin_rm,
                                    multihash)

    def build_client_options(self, node_id, **kwargs):
        return IPFSClient.build_options(node_id, **kwargs)
