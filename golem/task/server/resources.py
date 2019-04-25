import logging
import os
from typing import (
    Dict,
    Iterable,
    Optional,
    TYPE_CHECKING,
    Union,
)
import requests

from golem_messages import message

from golem.core import common
from golem.core import variables
from golem.core.common import deadline_to_timeout
from golem.core.hostaddress import ip_address_private
from golem.network.hyperdrive.client import HyperdriveClientOptions, \
    to_hyperg_peer
from golem.network.transport import msg_queue
from golem.resource.hyperdrive import resource as hpd_resource
from golem.resource.resourcehandshake import ResourceHandshake


if TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.task import taskmanager


logger = logging.getLogger(__name__)


class TaskResourcesMixin:
    """Resource management functionality of TaskServer"""

    HANDSHAKE_TIMEOUT = 20  # s
    NONCE_TASK = 'nonce'

    resource_handshakes: Dict[str, ResourceHandshake]
    task_manager: 'taskmanager.TaskManager'

    @property
    def resource_manager(self):
        resource_server = self.client.resource_server
        return resource_server.resource_manager

    def get_resources(self, task_id):
        resources = self.resource_manager.get_resources(task_id)
        return self.resource_manager.to_wire(resources)

    def restore_resources(self) -> None:
        task_manager = getattr(self, 'task_manager')

        if not task_manager.task_persistence:
            return

        states = dict(task_manager.tasks_states)
        tasks = dict(task_manager.tasks)

        for task_id, task_state in states.items():
            # 'package_path' does not exist in version pre 0.15.1
            package_path = getattr(task_state, 'package_path', None)
            # There is a single zip package to restore
            files = [package_path] if package_path else None
            # Calculate timeout
            task = tasks[task_id]
            timeout = deadline_to_timeout(task.header.deadline)

            logger.info("Restoring task '%s' resources (timeout: %r s)",
                        task_id, timeout)
            logger.debug("%r", files)

            self._restore_resources(files, task_id,
                                    resource_hash=task_state.resource_hash,
                                    timeout=timeout)

    def _restore_resources(self,
                           files: Optional[Iterable[str]],
                           task_id: str,
                           resource_hash: Optional[str] = None,
                           timeout: Optional[int] = None):

        options = self.get_share_options(task_id, None)
        options.timeout = timeout

        try:
            resource_hash, _ = self.resource_manager.add_resources(
                files, task_id, resource_hash=resource_hash,
                client_options=options, async_=False
            )
        except ConnectionError as exc:
            self._restore_resources_error(task_id, exc)
        except (hpd_resource.ResourceError, requests.HTTPError) as exc:
            if resource_hash:
                return self._restore_resources(files, task_id, timeout=timeout)
            self._restore_resources_error(task_id, exc)
        else:
            task_state = self.task_manager.tasks_states[task_id]
            task_state.resource_hash = resource_hash
            self.task_manager.notify_update_task(task_id)
        return None

    def _restore_resources_error(self, task_id, error):
        logger.error("Cannot restore task '%s' resources: %r", task_id, error)
        self.task_manager.delete_task(task_id)

    def request_resource(self, task_id, subtask_id, resources):
        if not self.client.resource_server:
            logger.error("ResourceManager not ready")
            return False
        resources = self.resource_manager.from_wire(resources)

        task_keeper = self.task_manager.comp_task_keeper
        options = task_keeper.get_resources_options(subtask_id)
        client_options = self.get_download_options(options)
        self.pull_resources(task_id, resources, client_options)
        return True

    def pull_resources(self, task_id, resources, client_options=None):
        self.client.pull_resources(
            task_id, resources, client_options=client_options)

    def get_download_options(
            self,
            received_options: Optional[Union[dict, HyperdriveClientOptions]],
            size: Optional[int] = None):

        options: Optional[HyperdriveClientOptions] = None

        def _filter_options(_options):
            result = None

            try:
                result = _options.filtered(verify_peer=self._verify_peer)
            except Exception as _exc:  # pylint: disable=broad-except
                logger.warning('Failed to filter received hyperg connection '
                               'options; falling back to defaults: %r', _exc)

            return result or self.resource_manager.build_client_options()

        if isinstance(received_options, dict):
            try:
                options = HyperdriveClientOptions(**received_options)
            except (AttributeError, TypeError) as exc:
                logger.warning('Failed to deserialize received hyperg '
                               'connection options: %r', exc)
        else:
            options = received_options

        options = _filter_options(options)

        if size and options:
            options.set(size=size)
        return options

    def get_share_options(self, task_id: str,  # noqa # pylint: disable=unused-argument
                          address: Optional[str]) -> HyperdriveClientOptions:
        """
        Builds share options with a list of peers in HyperG format.
        If the given address is a private one, put the list of private addresses
        before own public address.

        :param _task_id: Task id (unused)
        :param address: IP address of the node we're currently connected to
        """

        node = getattr(self, 'node')

        # Create a list of private addresses
        prv_addresses = [node.prv_addr] + node.prv_addresses
        peers = [
            to_hyperg_peer(a, node.hyperdrive_prv_port)
            for a in prv_addresses[:variables.MAX_CONNECT_SOCKET_ADDRESSES - 1]
        ]

        # If connected to a private address, pub_peer is the least important one
        prefer_prv = ip_address_private(address) if address else False
        pub_peer = to_hyperg_peer(node.pub_addr, node.hyperdrive_pub_port)

        peers.insert(-1 if prefer_prv else 0, pub_peer)

        return self.resource_manager.build_client_options(peers=peers)

    def _verify_peer(self, ip_address, _port):
        is_accessible = self.is_address_in_network  # noqa # pylint: disable=no-member

        # Make an exception for localhost (local tests)
        if ip_address in ['127.0.0.1', '::1']:
            return True
        if ip_address_private(ip_address) and not is_accessible(ip_address):
            return False

        return True

    def start_handshake(self, key_id, task_id: Optional[str] = None):
        logger.info('Starting resource handshake with %r',
                    common.short_node_id(key_id))

        handshake = ResourceHandshake()
        handshake.task_id = task_id
        directory = self.resource_manager.storage.get_dir(self.NONCE_TASK)

        try:
            handshake.start(directory)
        except Exception as err:  # pylint: disable=broad-except
            logger.info(
                "Can't start handshake. key_id=%s, err=%s",
                common.short_node_id(key_id),
                err,
            )
            logger.debug("Can't start handshake", exc_info=True)
            handshake.local_result = False
            return

        self.resource_handshakes[key_id] = handshake
        self._start_handshake_timer(key_id)
        self._share_handshake_nonce(key_id)

    def _start_handshake_timer(self, key_id):
        from twisted.internet import task
        from twisted.internet import reactor

        task.deferLater(
            reactor,
            self.HANDSHAKE_TIMEOUT,
            lambda *_: self._handshake_timeout(key_id)
        )

    def _handshake_timeout(self, key_id):
        try:
            handshake = self.resource_handshakes[key_id]
        except KeyError:
            return
        if handshake.success():
            return
        logger.info(
            'Resource handshake timeout. node=%s',
            common.short_node_id(key_id),
        )
        self.disallow_node(
            node_id=key_id,
            timeout_seconds=variables.ACL_BLOCK_TIMEOUT_RESOURCE,
            persist=False,
        )
        del self.resource_handshakes[key_id]

    # ########################
    #       SHARE NONCE
    # ########################

    def _nonce_shared(self, key_id, result, options):
        handshake = self.resource_handshakes.get(key_id)
        if not handshake:
            logger.debug('Resource handshake: nonce shared after '
                         'handshake failure with peer %r',
                         common.short_node_id(key_id))
            return

        handshake.hash, _ = result

        logger.debug(
            "Resource handshake: sending resource hash."
            "hash=%r, to_peer=%r",
            handshake.hash,
            common.short_node_id(key_id),
        )

        os.remove(handshake.file)
        msg_queue.put(
            node_id=key_id,
            msg=message.resources.ResourceHandshakeStart(
                resource=handshake.hash, options=options.__dict__,
            ),
        )

    def _share_handshake_nonce(self, key_id):
        handshake = self.resource_handshakes.get(key_id)
        options = self.get_share_options(handshake.nonce, None)
        options.timeout = self.HANDSHAKE_TIMEOUT

        deferred = self.resource_manager.add_file(handshake.file,
                                                  self.NONCE_TASK,
                                                  client_options=options,
                                                  async_=True)
        deferred.addCallbacks(
            lambda res: self._nonce_shared(key_id, res, options),
            lambda exc: self._handshake_error(key_id, exc)
        )
