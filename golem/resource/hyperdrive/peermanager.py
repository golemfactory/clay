import logging

from golem.network.hyperdrive.client import HyperdriveClientOptions


logger = logging.getLogger("golem.resource.peermanager")


class HyperdriveMetadataManager(object):

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


class HyperdrivePeerManager(HyperdriveMetadataManager):

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
