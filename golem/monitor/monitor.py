import threading
import Queue

from model.nodemetadatamodel import NodeMetadataModel, NodeInfoModel
from model.loginlogoutmodel import LoginModel, LogoutModel
from model.statssnapshotmodel import StatsSnapshotModel
from model.taskcomputersnapshotmodel import TaskComputerSnapshotModel
from model.paymentmodel import PaymentModel, IncomeModel
from transport.sender import DefaultJSONSender as Sender

from config import MONITOR_PROTO_VERSION


class SenderThread(threading.Thread):

    def __init__(self, node_info, monitor_host, monitor_request_timeout, monitor_sender_thread_timeout):
        super(SenderThread, self).__init__()
        self.queue = Queue.Queue()
        self.stop_request = threading.Event()
        self.node_info = node_info
        self.sender = Sender(monitor_host, monitor_request_timeout, MONITOR_PROTO_VERSION)
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

    def __init__(self, meta_data):
        assert isinstance(meta_data, NodeMetadataModel)

        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.queue = None
        self.sender_thread = None

    # Private interface

    def _send(self, obj):
        return self.sender_thread.send(obj)

    @classmethod
    def _prepare_obj_with_metadata(cls, obj_type, *args):
        return obj_type(*args)

    def _send_with_args(self, obj_type, *args):
        obj = self._prepare_obj_with_metadata(obj_type, *args)

        return self._send(obj)

    # Initialization

    def start(self, monitor_host, monitor_request_timeout, monitor_sender_thread_timeout):
        self.sender_thread = SenderThread(self.node_info, monitor_host, monitor_request_timeout, monitor_sender_thread_timeout)
        self.sender_thread.start()

    def shut_down(self):
        self.sender_thread.join()

    # Public interface

    def on_login(self):
        return self._send_with_args(LoginModel, self.meta_data)

    def on_logout(self):
        return self._send_with_args(LogoutModel, self.meta_data)

    def on_stats_snapshot(self, known_tasks, supported_tasks, computed_tasks, tasks_with_errors, tasks_with_timeout):
        return self._send_with_args(StatsSnapshotModel, known_tasks, supported_tasks, computed_tasks, tasks_with_errors, tasks_with_timeout)

    def on_peer_snapshot(self, peer_sess_info):
        # TODO: implement
        pass

    def on_task_computer_snapshot(self, waiting_for_task, counting_task, task_requested, comput_task, assigned_subtasks):
        return self._send_with_args(TaskComputerSnapshotModel, waiting_for_task, counting_task, task_requested, comput_task, assigned_subtasks)

    def on_payment(self, payment_infos):
        return self._send_with_args(PaymentModel, payment_infos)

    def on_income(self, addr, value):
        return self._send_with_args(IncomeModel, addr, value)