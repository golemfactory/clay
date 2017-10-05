import logging
import os
import uuid
from enum import Enum

from golem.core.async import AsyncRequest, async_run
from golem.network.transport.message import MessageWantToComputeTask, \
    MessageResourceHandshakeVerdict, MessageResourceHandshakeNonce, \
    MessageResourceHandshakeStart
from golem.resource.base.resourcesmanager import FileResource

logger = logging.getLogger(__name__)


class ResourceHandshakeStatus(Enum):

    INITIAL = 0
    STARTED = 1
    SUCCESS = 2
    FAILURE = 3


class ResourceHandshake:

    __slots__ = ('nonce', 'status', 'file', 'message',
                 'local_verified', 'remote_verified')

    def __init__(self, message=None):
        self.status = ResourceHandshakeStatus.INITIAL
        self.message = None
        self.file = message

        self.nonce = None
        self.local_verified = None
        self.remote_verified = None

    @staticmethod
    def read_nonce(nonce_file):
        with open(nonce_file, 'r') as f:
            return f.read().strip()

    def start(self, directory, nonce=None):
        self.local_verified = None
        self.remote_verified = None
        self.nonce = nonce or str(uuid.uuid4())
        self.file = os.path.join(directory, self.nonce)
        self.status = ResourceHandshakeStatus.STARTED

        with open(self.file, 'w') as f:
            f.write(self.nonce)

    def verify_local(self, nonce):
        self.local_verified = nonce == self.nonce
        return self.local_verified

    def remote_verdict(self, verdict):
        self.remote_verified = verdict

    def started(self):
        return self.status != ResourceHandshakeStatus.INITIAL

    def finished(self):
        return None not in [self.local_verified, self.remote_verified]

    def success(self):
        return all([self.local_verified, self.remote_verified])


class ResourceHandshakeSessionMixin:

    HANDSHAKE_TIMEOUT = 20  # s

    DCRResourceHandshakeTimeout = 'Resource handshake timeout'
    DCRResourceHandshakeFailure = 'Resource handshake failure'

    __sub_dir = 'nonces'
    __task_id = 'nonce'

    def __init__(self):
        self.key_id = None
        self.task_server = getattr(self, 'task_server', None)
        self._interpretation = getattr(self, '_interpretation', dict())
        self.__set_msg_interpretations()

        self._task_request_message = None
        self._handshake_timer = None

    def request_task(self, node_name, task_id, perf_index, price,
                     max_resource_size, max_memory_size, num_cores):

        """ Inform that node wants to compute given task
        :param str node_name: name of that node
        :param uuid task_id: if of a task that node wants to compute
        :param float perf_index: benchmark result for this task type
        :param float price: price for an hour
        :param int max_resource_size: how much disk space can this node offer
        :param int max_memory_size: how much ram can this node offer
        :param int num_cores: how many cpu cores this node can offer
        :return:
        """

        key_id = self.key_id
        message = dict(
            node_name=node_name,
            task_id=task_id,
            perf_index=perf_index,
            price=price,
            max_resource_size=max_resource_size,
            max_memory_size=max_memory_size,
            num_cores=num_cores
        )

        if self._is_peer_blocked(key_id):
            self._handshake_error(key_id, 'Peer blocked')

        elif self._handshake_required(key_id):
            self._task_request_message = message
            self._start_handshake(key_id)

        else:
            self.send(MessageWantToComputeTask(**message))

    # ########################
    #     MESSAGE HANDLERS
    # ########################

    def _react_to_resource_handshake_start(self, msg):
        key_id = self.key_id
        handshake = self._get_handshake(key_id)

        if self._is_peer_blocked(key_id):
            self._handshake_error(key_id, 'Peer blocked')
            return

        if not handshake:
            self._start_handshake(key_id, self._task_request_message)
        self._download_handshake_nonce(key_id, msg.resource)

    def _react_to_resource_handshake_nonce(self, msg):
        key_id = self.key_id
        handshake = self._get_handshake(key_id)
        accepted = handshake and handshake.verify_local(msg.nonce)

        if accepted:
            self._finalize_handshake(key_id)
        else:
            nonce = handshake.nonce if handshake else None
            self._handshake_error(key_id, 'nonce mismatch')
            self.send(MessageResourceHandshakeVerdict(nonce, accepted=False))

    def _react_to_resource_handshake_verdict(self, msg):
        key_id = self.key_id
        handshake = self._get_handshake(key_id)

        if handshake:
            handshake.remote_verdict(msg.accepted)
            self._finalize_handshake(key_id)
        else:
            self._handshake_error(key_id, 'handshake not started')
            self.disconnect(self.DCRResourceHandshakeTimeout)

    # ########################
    #     START HANDSHAKE
    # ########################

    def _handshake_required(self, key_id):
        if not key_id:
            self._handshake_error(key_id, 'empty key_id')
            return False

        handshake = self._get_handshake(key_id)
        blocked = self._is_peer_blocked(key_id)
        return not (handshake or blocked)

    def _handshake_in_progress(self, key_id):
        if not key_id:
            self._handshake_error(key_id, 'empty key_id')
            return False

        handshake = self._get_handshake(key_id)
        return handshake and not handshake.finished()

    def _start_handshake(self, key_id, message=None):
        handshake = ResourceHandshake(message)
        directory = self.resource_manager.storage.get_dir(self.__sub_dir)

        try:
            handshake.start(directory)
        except Exception as err:
            self._handshake_error(key_id, 'writing nonce to dir "{}": {}'
                                  .format(directory, err))
            return

        self._set_handshake(key_id, handshake)
        self._start_handshake_timer()
        self._share_handshake_nonce(key_id)

    def _start_handshake_timer(self):
        from twisted.internet import task
        from twisted.internet import reactor

        self._handshake_timer = task.deferLater(reactor,
                                                self.HANDSHAKE_TIMEOUT,
                                                self._handshake_timeout)

    # ########################
    #    FINALIZE HANDSHAKE
    # ########################

    def _finalize_handshake(self, key_id):
        self._task_request_message = None
        handshake = self._get_handshake(key_id)
        if handshake and handshake.success() and handshake.message:
            self.send(MessageWantToComputeTask(**handshake.message))

    def _stop_handshake_timer(self):
        if self._handshake_timer:
            self._handshake_timer.cancel()

    # ########################
    #       SHARE NONCE
    # ########################

    def _share_handshake_nonce(self, key_id):
        handshake = self._get_handshake(key_id)
        client_options = self.task_server.get_share_options(self.__task_id,
                                                            key_id)
        async_req = AsyncRequest(self.resource_manager.add_file,
                                 handshake.file, self.__task_id,
                                 absolute_path=True,
                                 client_options=client_options)
        async_run(async_req,
                  success=lambda res: self._nonce_shared(key_id, res),
                  error=lambda exc: self._handshake_error(key_id, exc))

    def _nonce_shared(self, key_id, result):
        result_path, result_hash = result
        logger.debug("Resource handshake: sending resource hash: "
                     "%r (%r) to %r", result_path, result_hash, key_id)

        self.send(MessageResourceHandshakeStart(result_hash))

    # ########################
    #      DOWNLOAD NONCE
    # ########################

    def _download_handshake_nonce(self, key_id, resource):
        task_id = self.__task_id
        file_resource = FileResource(file_name=key_id, resource_hash=resource,
                                     task_id=task_id),

        self.resource_manager.pull_resource(
            file_resource, task_id,
            success=lambda res, _: self._nonce_downloaded(key_id, res),
            error=lambda exc: self._handshake_error(key_id, exc),
            client_options=self.task_server.get_download_options(key_id)
        )

    def _nonce_downloaded(self, key_id, result):
        handshake = self._get_handshake(key_id)
        result_path, result_hash = result

        try:
            handshake.read_nonce(result_path)
        except OSError as err:
            self._handshake_error(key_id, 'reading nonce from file "{}": {}'
                                  .format(result_path, err))
        else:
            self.send(MessageResourceHandshakeNonce(
                handshake.remote_nonce)
            )

    # ########################
    #     ERROR HANDLERS
    # ########################

    def _handshake_error(self, key_id, error):
        logger.debug("Resource handshake error (%r): %r", key_id, error)
        self._block_peer(key_id)
        self._finalize_handshake(key_id)
        self.task_server.task_computer.session_closed()

    def _handshake_timeout(self, key_id):
        self._handshake_error(key_id, 'timeout')
        self.disconnect(self.DCRResourceHandshakeTimeout)

    # ########################
    #      ACCESS HELPERS
    # ########################

    @property
    def resource_manager(self):
        task_result_manager = self.task_server.task_manager.task_result_manager
        return task_result_manager.resource_manager

    def _set_handshake(self, key_id, handshake):
        self.task_server.resource_handshakes[key_id] = handshake

    def _get_handshake(self, key_id):
        return self.task_server.resource_handshakes.get(key_id)

    def _remove_handshake(self, key_id):
        self.task_server.resource_handshakes.pop(key_id, None)

    def _block_peer(self, key_id):
        self.task_server.deny_set.add(key_id)
        self._remove_handshake(key_id)

    def _is_peer_blocked(self, key_id):
        return key_id in self.task_server.deny_set

    # ########################
    #         MESSAGES
    # ########################

    def __set_msg_interpretations(self):
        self._interpretation.update({
            MessageResourceHandshakeStart.TYPE:
                self._react_to_resource_handshake_start,
            MessageResourceHandshakeNonce.TYPE:
                self._react_to_resource_handshake_nonce,
            MessageResourceHandshakeVerdict.TYPE:
                self._react_to_resource_handshake_verdict
        })
