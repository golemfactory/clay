from golem.decorators import log_error
import logging
from pydispatch import dispatcher
import threading
import Queue

from model.nodemetadatamodel import NodeMetadataModel, NodeInfoModel
from model.loginlogoutmodel import LoginModel, LogoutModel
from model.statssnapshotmodel import StatsSnapshotModel, VMSnapshotModel, P2PSnapshotModel
from model.taskcomputersnapshotmodel import TaskComputerSnapshotModel
from model.paymentmodel import ExpenditureModel, IncomeModel
from transport.sender import DefaultJSONSender as Sender

log = logging.getLogger('golem.monitor')


class SenderThread(threading.Thread):

    def __init__(self, node_info, monitor_host, monitor_request_timeout, monitor_sender_thread_timeout, proto_ver):
        super(SenderThread, self).__init__()
        self.queue = Queue.Queue()
        self.stop_request = threading.Event()
        self.node_info = node_info
        self.sender = Sender(monitor_host, monitor_request_timeout, proto_ver)
        self.monitor_sender_thread_timeout = monitor_sender_thread_timeout

    def send(self, o):
        self.queue.put(o)

    def run(self):

        while not self.stop_request.isSet():
            try:
                msg = self.queue.get(True, self.monitor_sender_thread_timeout)
                self.sender.send(msg)
            except Queue.Empty:
                # send ping message
                self.sender.send(self.node_info)

    def join(self, timeout=None):
        self.stop_request.set()
        super(SenderThread, self).join(timeout)


class SystemMonitor(object):

    def __init__(self, meta_data, monitor_config):
        if not isinstance(meta_data, NodeMetadataModel):
            raise TypeError("Incorrect meta_data type {}, should be NodeMetadataModel".format(type(meta_data)))

        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.config = monitor_config
        self.queue = None
        self.sender_thread = None

        dispatcher.connect(self.dispatch_listener, signal='golem.monitor')

    # Private interface

    def _send_with_args(self, obj_type, *args):
        log.debug('_send_with_args(%r, %r)', obj_type, args)
        obj = obj_type(*args)
        return self.sender_thread.send(obj)

    @log_error()
    def dispatch_listener(self, sender, signal, event='default', **kwargs):
        """ Main PubSub listener for golem_monitor channel """
        method_name = "on_%s" % (event,)
        if not hasattr(self, method_name):
            log.warning('Unrecognized event received: golem_monitor %s', event)
            return
        getattr(self, method_name)(**kwargs)

    # Initialization

    def start(self):
        host = self.config['HOST']
        request_timeout = self.config['REQUEST_TIMEOUT']
        sender_thread_timeout = self.config['SENDER_THREAD_TIMEOUT']
        proto_ver = self.config['PROTO_VERSION']

        self.sender_thread = SenderThread(self.node_info, host, request_timeout, sender_thread_timeout, proto_ver)
        self.sender_thread.start()

    def shut_down(self):
        self.sender_thread.join()

    # Public interface

    def on_login(self):
        self._send_with_args(LoginModel, self.meta_data)

    def on_config_update(self, meta_data):
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        return self._send_with_args(LoginModel, self.meta_data)

    def on_logout(self):
        return self._send_with_args(LogoutModel, self.meta_data)

    def on_stats_snapshot(self, known_tasks, supported_tasks, computed_tasks, tasks_with_errors, tasks_with_timeout):
        return self._send_with_args(StatsSnapshotModel, self.meta_data.cliid, self.meta_data.sessid, known_tasks,
                                    supported_tasks, computed_tasks, tasks_with_errors, tasks_with_timeout)

    def on_vm_snapshot(self, vm_data):
        return self._send_with_args(VMSnapshotModel, self.meta_data.cliid, self.meta_data.sessid, vm_data)

    def on_peer_snapshot(self, p2p_data):
        return self._send_with_args(P2PSnapshotModel, self.meta_data.cliid, self.meta_data.sessid, p2p_data)

    def on_task_computer_snapshot(self, waiting_for_task, counting_task, task_requested, comput_task, assigned_subtasks):
        return self._send_with_args(TaskComputerSnapshotModel, self.meta_data.cliid, self.meta_data.sessid,
                                    waiting_for_task, counting_task, task_requested, comput_task, assigned_subtasks)

    def on_payment(self, addr, value):
        return self._send_with_args(ExpenditureModel, self.meta_data.cliid, self.meta_data.sessid, addr, value)

    def on_income(self, addr, value):
        return self._send_with_args(IncomeModel, self.meta_data.cliid, self.meta_data.sessid, addr, value)
