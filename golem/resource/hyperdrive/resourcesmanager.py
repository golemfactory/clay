import logging
import os
import uuid
from collections import OrderedDict

from golem.network.hyperdrive.client import HyperdriveClient, \
    HyperdriveClientOptions
from golem.resource.base.resourcesmanager import AbstractResourceManager, ResourceBundle
from golem.resource.client import ClientHandler, ClientConfig, ClientCommands

logger = logging.getLogger(__name__)


class HyperdriveResourceManager(ClientHandler, AbstractResourceManager):

    def __init__(self, dir_manager, daemon_address=None, config=None, **kwargs):

        ClientHandler.__init__(self, ClientCommands, config or ClientConfig())
        AbstractResourceManager.__init__(self, dir_manager, **kwargs)

        self.peer_manager = HyperdrivePeerManager(daemon_address)

    def new_client(self):
        return HyperdriveClient(**self.config.client)

    def build_client_options(self, node_id, peers=None, **kwargs):
        return HyperdriveClient.build_options(node_id, peers=peers, **kwargs)

    def to_wire(self, resources):
        iterator = filter(None, resources)
        return list([r.hash, r.files_split] for r in iterator)

    def from_wire(self, resources):
        iterator = filter(lambda x: x and len(x) > 1, resources)
        return list([r[0], [os.path.join(*x) for x in r[1]]] for r in iterator)

    def add_files(self, files, task_id,
                  absolute_path=False, client=None, client_options=None):

        if not files:
            logger.warning("Resource manager: trying to add an empty file "
                           "collection for task {}".format(task_id))
            return

        files = {path: self.storage.relative_path(path, task_id)
                 for path in files}

        return self._add_files(files, task_id,
                               client=client,
                               client_options=client_options)

    def add_file(self, path, task_id,
                 absolute_path=False, client=None, client_options=None):

        files = {path: os.path.basename(path)}

        return self._add_files(files, task_id,
                               client=client,
                               client_options=client_options)

    def _add_files(self, files, task_id,
                   client=None, client_options=None):

        for f in files.keys():
            if not os.path.exists(f):
                logger.error("Resource manager: file '{}' does not exist"
                             .format(f))
                return

        client = client or self.new_client()
        response = self._handle_retries(client.add,
                                        self.commands.add,
                                        files,
                                        id=task_id,
                                        client_options=client_options,
                                        obj_id=str(uuid.uuid4()))

        self._cache_response(list(files.values()), response, task_id)

    def wrap_file(self, resource):
        resource_path, resource_hash = resource
        return resource_hash, [resource_path]

    def _wrap_resource(self, resource, task_id=None):
        resource_hash, files = resource
        path = self.storage.get_path('', task_id)
        return ResourceBundle(files, resource_hash,
                              task_id=task_id, path=path)

    def _cache_response(self, resources, resource_hash, task_id):
        res = self._wrap_resource((resource_hash, resources), task_id)
        self._cache_resource(res)


class HyperDriveMetadataManager(object):

    def __init__(self, daemon_address):
        self._daemon_address = daemon_address
        self._peers = dict()

    def get_metadata(self):
        return dict(hyperg=self._daemon_address)

    def interpret_metadata(self, metadata, address, port, node):
        address = metadata.get('hyperg')
        address = HyperdriveClientOptions.filter_peer(address)
        if address:
            self._peers[node.key] = address


class HyperdrivePeerManager(HyperDriveMetadataManager):

    def __init__(self, daemon_address):
        super(HyperdrivePeerManager, self).__init__(daemon_address)
        self._tasks = dict()

    def add(self, task_id, key_id):
        entry = self._peers.get(key_id)
        if not entry:
            return logger.debug('Unknown peer: %s', key_id)

        if task_id not in self._tasks:
            self._tasks[task_id] = OrderedDict()
        self._tasks[task_id][key_id] = entry

    def remove(self, task_id, key_id):
        try:
            self._peers.pop(key_id)
            return self._tasks[task_id].pop(key_id)
        except KeyError:
            return None

    def get(self, task_id):
        peers = [self._daemon_address]
        known_peers = self._tasks.get(task_id)

        if known_peers:
            return peers + known_peers.values()
        return peers
