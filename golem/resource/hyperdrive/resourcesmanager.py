import logging
import os
import uuid

from collections import Iterable

from golem.network.hyperdrive.client import HyperdriveClient, \
    HyperdriveClientOptions
from golem.resource.base.resourcesmanager import AbstractResourceManager, \
    ResourceBundle
from golem.resource.client import ClientHandler, ClientConfig, ClientCommands

logger = logging.getLogger(__name__)


class HyperdriveResourceManager(ClientHandler, AbstractResourceManager):

    def __init__(self, dir_manager, daemon_address=None, config=None, **kwargs):

        ClientHandler.__init__(self, ClientCommands, config or ClientConfig())
        AbstractResourceManager.__init__(self, dir_manager, **kwargs)

        self.peer_manager = HyperdrivePeerManager(daemon_address)

    def new_client(self):
        return HyperdriveClient(**self.config.client)

    def build_client_options(self, peers=None, **kwargs):
        return HyperdriveClient.build_options(peers=peers, **kwargs)

    def to_wire(self, resources):
        iterator = filter(None, resources)
        return list([r.hash, r.files_split] for r in iterator)

    def from_wire(self, resources):
        iterator = filter(lambda x: isinstance(x, Iterable) and len(x) > 1,
                          resources)
        results = []

        for entry in iterator:
            files = [os.path.join(*split) for split in entry[1] if split]
            if not files:
                logger.debug("Received an empty file list for hash %r",
                             entry[0])
                continue
            results.append([entry[0], files])

        return results

    def add_files(self, files, task_id, resource_hash=None,
                  absolute_path=False, client=None, client_options=None):

        if not files:
            logger.warning("Resource manager: trying to add an empty file "
                           "collection for task {}".format(task_id))
            return

        files = {path: self.storage.relative_path(path, task_id)
                 for path in files}

        return self._add_files(files, task_id,
                               resource_hash=resource_hash,
                               client=client,
                               client_options=client_options)

    def add_file(self, path, task_id,
                 absolute_path=False, client=None, client_options=None):

        files = {path: os.path.basename(path)}

        return self._add_files(files, task_id,
                               client=client,
                               client_options=client_options)

    def _add_files(self, files, task_id, resource_hash=None,
                   client=None, client_options=None):

        if not all(os.path.exists(f) for f in files.keys()):
            logger.error("Resource manager: missing files (task: %r)", task_id)
            return

        client = client or self.new_client()

        if resource_hash:
            args = (client.restore, self.commands.restore, resource_hash)
        else:
            args = (client.add, self.commands.add, files)

        response = self._handle_retries(*args,
                                        id=task_id,
                                        client_options=client_options,
                                        obj_id=str(uuid.uuid4()),
                                        raise_exc=bool(resource_hash))

        file_list = list(files.values())
        self._cache_response(file_list, response, task_id)
        return file_list, response

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

    def _parse_pull_response(self, response, task_id):
        # response -> [(path, hash, [file_1, file_2, ...])]
        relative = self.storage.relative_path
        if response and len(response[0]) >= 3:
            return [relative(f, task_id) for f in response[0][2]]
        return []


class HyperDriveMetadataManager(object):

    METADATA_KEY = 'hyperg'

    def __init__(self, daemon_address):
        self._daemon_address = daemon_address
        self._peers = dict()

    def get_metadata(self):
        return {self.METADATA_KEY: self._daemon_address}

    def interpret_metadata(self, metadata, address, port, node):
        if not isinstance(metadata, dict):
            return

        metadata_peer = metadata.get(self.METADATA_KEY)
        peer = HyperdriveClientOptions.filter_peer(metadata_peer,
                                                   forced_ip=address)
        if peer:

            self._peers[node.key] = peer


class HyperdrivePeerManager(HyperDriveMetadataManager):

    def __init__(self, daemon_address):
        super(HyperdrivePeerManager, self).__init__(daemon_address)
        self._tasks = dict()

    def add(self, task_id, key_id):
        entry = self._peers.get(key_id)
        if not entry:
            return logger.debug('No resource metadata for peer: %s', key_id)

        if task_id not in self._tasks:
            self._tasks[task_id] = dict()
        self._tasks[task_id][key_id] = entry

    def remove(self, task_id, key_id):
        try:
            self._peers.pop(key_id)
            return self._tasks[task_id].pop(key_id)
        except KeyError:
            return None

    def get(self, key_id):
        return self._peers.get(key_id)

    def get_for_task(self, task_id):
        peers = self._tasks.get(task_id, dict())
        return [self._daemon_address] + list(peers.values())
