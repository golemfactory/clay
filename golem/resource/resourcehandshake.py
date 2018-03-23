import logging
import os
import uuid

from golem_messages import message

logger = logging.getLogger('golem.resources')


class ResourceHandshake:

    __slots__ = ('nonce', 'file', 'hash', 'message',
                 'started', 'local_result', 'remote_result')

    def __init__(self, message_=None):
        self.nonce = str(uuid.uuid4())
        self.file = None
        self.hash = None
        self.message = message_

        self.started = False
        self.local_result = None
        self.remote_result = None

    @staticmethod
    def read_nonce(nonce_file):
        with open(nonce_file, 'r') as f:
            return f.read().strip()

    def start(self, directory):
        self.local_result = None
        self.remote_result = None
        self.file = os.path.join(directory, str(uuid.uuid4()))
        self.hash = None
        self.started = True

        with open(self.file, 'w') as f:
            f.write(self.nonce)

    def verify_local(self, nonce):
        self.local_result = nonce == self.nonce
        return self.local_result

    def remote_verdict(self, verdict):
        self.remote_result = verdict

    def finished(self):
        return None not in [self.local_result, self.remote_result]

    def success(self):
        return all([self.local_result, self.remote_result])


class ResourceHandshakeSessionMixin:

    HANDSHAKE_TIMEOUT = 20  # s
    NONCE_TASK = 'nonce'

    def __init__(self):
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
        msg_d = dict(
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
            self._task_request_message = msg_d
            self._start_handshake(key_id)

        else:
            self.send(message.WantToComputeTask(**msg_d))

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
            self._start_handshake(key_id)
        elif handshake.success():  # handle inconsistent state between peers
            options = self.task_server.get_share_options(handshake.nonce,
                                                         self.address)
            self.send(message.ResourceHandshakeStart(resource=handshake.hash,
                                                     options=options.__dict__))

        self._download_handshake_nonce(key_id, msg.resource, msg.options)

    def _react_to_resource_handshake_nonce(self, msg):
        key_id = self.key_id
        handshake = self._get_handshake(key_id)
        accepted = handshake and handshake.verify_local(msg.nonce)
        nonce = handshake.nonce if handshake else None

        self.send(message.ResourceHandshakeVerdict(
            nonce=msg.nonce,
            accepted=accepted,
        ))

        if accepted:
            self._finalize_handshake(key_id)
        else:
            error = 'nonce mismatch: {} != {}'.format(nonce, msg.nonce)
            self._handshake_error(key_id, error)

    def _react_to_resource_handshake_verdict(self, msg):
        key_id = self.key_id
        handshake = self._get_handshake(key_id)

        if handshake:
            handshake.remote_verdict(msg.accepted)
            self._finalize_handshake(key_id)
        else:
            self._handshake_error(key_id, 'handshake not started')
            self.disconnect(message.Disconnect.REASON.ResourceHandshakeTimeout)

    # ########################
    #     START HANDSHAKE
    # ########################

    def _handshake_required(self, key_id):
        if not key_id:
            self._handshake_error(key_id, 'empty key_id')
            return False

        handshake = self._get_handshake(key_id)
        blocked = self._is_peer_blocked(key_id)

        return not (blocked or handshake)

    def _handshake_in_progress(self, key_id):
        if not key_id:
            self._handshake_error(key_id, 'empty key_id')
            return False

        handshake = self._get_handshake(key_id)
        return handshake and not handshake.finished()

    def _start_handshake(self, key_id):
        logger.info('Starting resource handshake with %r', key_id)

        handshake = ResourceHandshake(self._task_request_message)
        directory = self.resource_manager.storage.get_dir(self.NONCE_TASK)

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

        self._handshake_timer = task.deferLater(
            reactor,
            self.HANDSHAKE_TIMEOUT,
            lambda *_: self._handshake_timeout(self.key_id)
        )

    # ########################
    #    FINALIZE HANDSHAKE
    # ########################

    def _finalize_handshake(self, key_id):
        handshake = self._get_handshake(key_id)
        if not handshake:
            return

        if handshake.finished():
            logger.info('Finished resource handshake with %r', key_id)
        if handshake.success() and handshake.message:
            self.send(message.WantToComputeTask(**handshake.message))

    def _stop_handshake_timer(self):
        if self._handshake_timer:
            self._handshake_timer.cancel()

    # ########################
    #       SHARE NONCE
    # ########################

    def _share_handshake_nonce(self, key_id):
        handshake = self._get_handshake(key_id)
        options = self.task_server.get_share_options(handshake.nonce,
                                                     self.address)
        deferred = self.resource_manager.add_file(handshake.file,
                                                  self.NONCE_TASK,
                                                  async_=True)
        deferred.addCallbacks(
            lambda res: self._nonce_shared(key_id, res, options),
            lambda exc: self._handshake_error(key_id, exc)
        )

    def _nonce_shared(self, key_id, result, options):
        handshake = self._get_handshake(key_id)
        handshake.hash, _ = result

        logger.debug("Resource handshake: sending resource hash: "
                     "%r to peer %r", handshake.hash, key_id)

        os.remove(handshake.file)
        self.send(message.ResourceHandshakeStart(resource=handshake.hash,
                                                 options=options.__dict__))

    # ########################
    #      DOWNLOAD NONCE
    # ########################

    def _download_handshake_nonce(self, key_id, resource, options):
        entry = resource, ''

        self.resource_manager.pull_resource(
            entry, self.NONCE_TASK,
            success=lambda res, files, _: self._nonce_downloaded(key_id, files),
            error=lambda exc, *_: self._handshake_error(key_id, exc),
            client_options=self.task_server.get_download_options(
                options,
                self.NONCE_TASK
            )
        )

    def _nonce_downloaded(self, key_id, files):
        handshake = self._get_handshake(key_id)

        try:
            path = files[0]
            nonce = handshake.read_nonce(path)
        except Exception as err:
            self._handshake_error(key_id, 'reading nonce from file "{}": {}'
                                  .format(files, err))
        else:
            os.remove(path)
            self.send(message.ResourceHandshakeNonce(nonce=nonce))

    # ########################
    #     ERROR HANDLERS
    # ########################

    def _handshake_error(self, key_id, error):
        logger.info("Resource handshake error (%r): %r", key_id, error)
        self._block_peer(key_id)
        self._finalize_handshake(key_id)
        self.task_server.task_computer.session_closed()
        self.dropped()

    def _handshake_timeout(self, key_id):
        handshake = self._get_handshake(key_id)
        if handshake and not handshake.success():
            self._handshake_error(key_id, 'timeout')

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
        self.task_server.acl.disallow(key_id)
        self._remove_handshake(key_id)

    def _is_peer_blocked(self, key_id):
        return not self.task_server.acl.is_allowed(key_id)

    # ########################
    #         MESSAGES
    # ########################

    def __set_msg_interpretations(self):
        self._interpretation.update({
            message.ResourceHandshakeStart.TYPE:
                self._react_to_resource_handshake_start,
            message.ResourceHandshakeNonce.TYPE:
                self._react_to_resource_handshake_nonce,
            message.ResourceHandshakeVerdict.TYPE:
                self._react_to_resource_handshake_verdict
        })
