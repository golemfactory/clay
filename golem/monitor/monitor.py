import threading
import Queue

from model.nodemetadatamodel import NodeMetadataModel
from model.loginlogoutmodel import LoginModel, LogoutModel
from model.statssnapshotmodel import StatsSnapshotModel
from model.taskcomputersnapshotmodel import TaskComputerSnapshotModel
from model.paymentmodel import PaymentModel, IncomeModel
from transport.sender import DefaultJSONSender as Sender

from config import MONITOR_SENDER_THREAD_TIMEOUT, MONITOR_HOST, MONITOR_REQUEST_TIMEOUT, MONITOR_PROTO_VERSION


class SenderThread(threading.Thread):

    def __init__(self, meta_data):
        super(SenderThread, self).__init__()
        self.queue = Queue.Queue()
        self.stop_request = threading.Event()
        self.meta_data = meta_data
        self.sender = Sender(MONITOR_HOST, MONITOR_REQUEST_TIMEOUT, MONITOR_PROTO_VERSION)

    def send(self, o):
        self.queue.put(o)

    def run(self):

        while not self.stop_request.isSet():
            try:
                msg = self.queue.get(True, MONITOR_SENDER_THREAD_TIMEOUT)
                self.sender.send(msg)
            except Queue.Empty:
                # send ping message
                self.sender.send(self.meta_data)

    def join(self, timeout=None):
        self.stop_request.set()
        super(SenderThread, self).join(timeout)


class SystemMonitor(object):

    def __init__(self, meta_data):
        assert isinstance(meta_data, NodeMetadataModel)

        self.meta_data = meta_data
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

    def start(self):
        self.sender_thread = SenderThread(self.meta_data)
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


if __name__ == "__main__":

    import random
    import time

    num_test_passes = 10
    max_sleep_time = 3.5

    max_num_comp_tasks = 10
    max_payment_infos = 10

    metadata = NodeMetadataModel(1, 1, "Windows 7", 0.1)

    m = SystemMonitor(metadata)
    m.start()

    print "Starting tests with {} passes".format(num_test_passes)

    for i in range(num_test_passes):
        rv = random.random()
        st = rv * max_sleep_time

        time.sleep(st)

        if rv < 0.15:
            print "Login"
            m.on_login()
        elif rv < 0.3:
            print "Logout"
            m.on_logout()
        elif rv < 0.45:
            print "Stats"

            kt = int(10 * random.random())
            st = int(100 * random.random())
            ct = int(20 * random.random())
            twe = int(10 * random.random())
            twt = int(20 * random.random())

            m.on_stats_snapshot(kt, st, ct, twe, twt)
        elif rv < 0.6:
            print "CompTasks"

            comp_tasks = int(max_num_comp_tasks * random.random()) + 1
            tasks = ["task{}".format(i) for i in range(comp_tasks)]

            m.on_task_computer_snapshot('some_task_str', False, True, False, tasks)
        elif rv < 0.8:
            print "Payment"

            payment_infos = int(random.random() * max_payment_infos) + 1

            payment_infos = [{'addr': 'host'.format(i), 'value': i} for i in range(payment_infos)]
            m.on_payment(payment_infos)
        else:
            print "Income"

            addr = 'host'.format(int(random.random() * 100000))
            value = int(random.random() * 5000)

            m.on_income(addr, value)

    print "Tests finished"

    m.shut_down()
