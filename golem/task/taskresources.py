import logging
from typing import Iterable, Optional

import requests

from golem.network.hyperdrive.client import DEFAULT_HYPERDRIVE_PORT
from golem.resource import resource
from golem.resource.hyperdrive import resource as hpd_resource


logger = logging.getLogger(__name__)


class TaskResourcesMixin(object):
    def add_resource_peer(self, node_name, addr, port, key_id, node_info):
        self.client.add_resource_peer(node_name, addr, port, key_id, node_info)

    def get_resource_peer(self, key_id):
        peer_manager = self._get_peer_manager()
        if peer_manager:
            return peer_manager.get(key_id)
        return None

    def get_resource_peers(self, task_id):
        peer_manager = self._get_peer_manager()
        if peer_manager:
            return peer_manager.get_for_task(task_id)
        return []

    def remove_resource_peer(self, task_id, key_id):
        peer_manager = self._get_peer_manager()
        if peer_manager:
            return peer_manager.remove(task_id, key_id)
        return None

    def get_resources(self, task_id):
        resource_manager = self._get_resource_manager()
        resources = resource_manager.get_resources(task_id)
        return resource_manager.to_wire(resources)

    def restore_resources(self) -> None:

        if not self.task_manager.task_persistence:
            return

        states = dict(self.task_manager.tasks_states)

        for task_id, task_state in states.items():
            task = self.task_manager.tasks[task_id]
            files = resource.get_resources_for_task(
                None,
                resources=task.get_resources(),
                tmp_dir=task.tmp_dir,
                resource_type=resource.ResourceType.HASHES,
            )

            logger.info("Restoring task '%s' resources", task_id)
            self._restore_resources(files, task_id, task_state.resource_hash)

    def _restore_resources(self,
                           files: Iterable[str],
                           task_id: str,
                           resource_hash: Optional[str] = None):

        resource_manager = self._get_resource_manager()

        try:
            resource_hash, _ = resource_manager.add_task(
                files, task_id, resource_hash=resource_hash, async_=False
            )
        except ConnectionError as exc:
            self._restore_resources_error(task_id, exc)
        except (hpd_resource.ResourceError, requests.HTTPError) as exc:
            if resource_hash:
                return self._restore_resources(files, task_id)
            self._restore_resources_error(task_id, exc)
        else:
            task_state = self.task_manager.tasks_states[task_id]
            task_state.resource_hash = resource_hash
            self.task_manager.notify_update_task(task_id)
        return None

    def _restore_resources_error(self, task_id, error):
        logger.error("Cannot restore task '%s' resources: %r", task_id, error)
        self.task_manager.delete_task(task_id)

    def get_download_options(self, key_id, address=None):
        resource_manager = self._get_resource_manager()
        peers = []

        if address:
            peers.append({'TCP': [address, DEFAULT_HYPERDRIVE_PORT]})
        else:
            peer = self.get_resource_peer(key_id)
            if peer:
                peers.append(peer)
        return resource_manager.build_client_options(peers=peers)

    def get_share_options(self, task_id, key_id):
        resource_manager = self._get_resource_manager()
        peers = self.get_resource_peers(task_id)
        return resource_manager.build_client_options(peers=peers)

    def request_resource(self, task_id, subtask_id):
        if subtask_id not in self.task_sessions:
            logger.error("Cannot map subtask_id %r to session", subtask_id)
            return False

        session = self.task_sessions[subtask_id]
        session.request_resource(task_id)
        return True

    def pull_resources(self, task_id, resources, client_options=None):
        self.client.pull_resources(
            task_id, resources, client_options=client_options)

    def _get_resource_manager(self):
        resource_server = self.client.resource_server
        return resource_server.resource_manager

    def _get_peer_manager(self):
        resource_manager = self._get_resource_manager()
        return getattr(resource_manager, 'peer_manager', None)
