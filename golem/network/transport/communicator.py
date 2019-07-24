# import twisted.persisted. TODO
import threading
from collections import defaultdict

import twisted.internet.reactor
import twisted.internet.defer
from golem_messages.message import TaskToCompute
from twisted.internet import reactor, threads, task
from twisted.internet.task import Clock

from golem.task.tasksession import TaskSession


class Communicator:
    def __init__(self):
        self.task_sessions = {}
        self.pending_messages = defaultdict(list)
        self.computation_rejections = defaultdict(list)
        self.locks = defaultdict(threading.Lock) # is that dict threadsafe?

    def on_connection_established(self, node_id, task_session):
        with self.locks.get(node_id):
            self.task_sessions[node_id] = task_session
            self._send_pending_messages(node_id)

    def on_disconnect(self, node_id):
        with self.locks.get(node_id):
            del self.task_sessions[node_id]

    def _send_pending_messages(self, node_id):
        with self.locks.get(node_id):
            pending_messages = self.pending_messages.get(node_id)
            for pending_message in pending_messages:
                self.send()

    def on_computation_rejected(self, provider_id, msg : TaskToCompute):
        with self.locks.get(provider_id):
            self.computation_rejections.get(provider_id).append(hash(msg))


    def _send(self, task_session, message, callback, err_callback) -> twisted.Deferred:
        def __send(task_session, message):
            return task_session.send(message) # modify TaskSession::send to raise an exception
        d = threads.deferToThread(__send, task_session, message, err_callback)
        d.addCallbacks(callback, errback=err_callback, errbackArgs={'node_id': no})
        return d

    def nominate_provider_with_assurance(self, provider_id, task_id, timeout, callback_err, callback_success, msg : TaskToCompute):
        def on_timeout_error():
            '''
                Check if message was sent to provider. If yes and there is no rejection we treat it as acceptance
                If not, callback error,
            '''

        def sending_failed():

        def sending_succeded():

        with self.locks.get(provider_id):
            clock = Clock()  # TODO
            task_session : TaskSession = self.task_sessions.get(provider_id)
            if task_session:
                d\
                    = self._send(task_session, msg)
            else:
                self.pending_messages.get(provider_id, []).append(msg)

            def f():

            deferred = twisted.internet.defer.Deferred()
            deferred.addTimeout(timeout, clock, onTimeoutCancel=on_timeout_error)
            d = threads.deferToThread(self.logic.sendpp, msg, user, "np")
            deferred.callback(result)

            # tu trzymam deferred od wysłania

            d.chainDeferred(_await_for_acceptance(provider_id, task_id, hash(msg)))


    def _await_for_acceptance(self, node_id, task_id, task_to_compute_msg_hash):
        # TODO: how to identify taskToCompute
        def x():
            with self.locks.get(node_id):
                if task_to_compute_msg_hash in self.computation_rejections.get(node_id):
                    raise

        d = task.deferLater(reactor, 3.5, x, node_id, task_id)
        reactor
        twisted.internet.defer.execute(x, node_id, task_id)