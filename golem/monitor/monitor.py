import logging
import queue
import threading
import time
from urllib.parse import urljoin

import requests
from pydispatch import dispatcher

from golem.core import variables
from golem.decorators import log_error
from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats
from .model import statssnapshotmodel
from .model.balancemodel import BalanceModel
from .model.loginlogoutmodel import LoginModel, LogoutModel
from .model.nodemetadatamodel import NodeInfoModel, NodeMetadataModel
from .model.paymentmodel import ExpenditureModel, IncomeModel
from .model.taskcomputersnapshotmodel import TaskComputerSnapshotModel
from .transport.sender import DefaultJSONSender as Sender

log = logging.getLogger('golem.monitor')


class SenderThread(threading.Thread):
    def __init__(self, node_info, monitor_host, monitor_request_timeout,
                 monitor_sender_thread_timeout, proto_ver):
        super(SenderThread, self).__init__()
        self.queue = queue.Queue()
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
            except queue.Empty:
                # send ping message
                self.sender.send(self.node_info)

    def join(self, timeout=None):
        self.stop_request.set()
        super(SenderThread, self).join(timeout)


class SystemMonitor(object):
    def __init__(self,
                 meta_data: NodeMetadataModel,
                 monitor_config: dict,
                 send_payment_info: bool = True) -> None:
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.config = monitor_config
        self.send_payment_info = send_payment_info
        dispatcher.connect(self.dispatch_listener, signal='golem.monitor')
        dispatcher.connect(self.p2p_listener, signal='golem.p2p')

    @property
    def sender_thread(self):
        if not hasattr(self, '_sender_thread'):
            host = self.config['HOST']
            request_timeout = self.config['REQUEST_TIMEOUT']
            sender_thread_timeout = self.config['SENDER_THREAD_TIMEOUT']
            proto_ver = self.config['PROTO_VERSION']
            self._sender_thread = SenderThread(
                self.node_info,
                host,
                request_timeout,
                sender_thread_timeout,
                proto_ver
            )
        return self._sender_thread

    def p2p_listener(self, event='default', ports=None, *_, **__):
        if event != 'listening':
            return
        result = self.ping_request(ports)

        if not result['success']:
            for port_status in result['port_statuses']:
                if not port_status['is_open']:
                    dispatcher.send(
                        signal='golem.p2p',
                        event='unreachable',
                        port=port_status['port'],
                        description=port_status['description']
                    )

        if result['time_diff'] > variables.MAX_TIME_DIFF:
            dispatcher.send(
                signal='golem.p2p',
                event='unsynchronized',
                time_diff=result['time_diff']
            )

    def ping_request(self, ports):
        timeout = 2.5  # seconds
        try:
            response = requests.post(
                urljoin(self.config['HOST'], 'ping-me'),
                data={
                    'ports': ports,
                    'timestamp': time.time()
                },
                timeout=timeout,
            )
            result = response.json()
            log.debug('Ping result: %r', result)
            return result
        except requests.ConnectionError:
            log.exception('Ping connection error')

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
        self.sender_thread.start()

    def shut_down(self):
        dispatcher.disconnect(self.dispatch_listener, signal='golem.monitor')
        dispatcher.disconnect(self.p2p_listener, signal='golem.p2p')
        self.sender_thread.join()

    # Public interface

    def on_shutdown(self):
        self.on_logout()
        self.shut_down()

    def on_login(self):
        self.sender_thread.send(LoginModel(self.meta_data))

    def on_config_update(self, meta_data):
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.sender_thread.send(LoginModel(self.meta_data))

    def on_computation_time_spent(self, success, value):
        msg = statssnapshotmodel.ComputationTime(
            self.meta_data,
            success,
            value
        )
        self.sender_thread.send(msg)

    def on_logout(self):
        self.sender_thread.send(LogoutModel(self.meta_data))

    def on_stats_snapshot(self, known_tasks, supported_tasks, stats):
        msg = statssnapshotmodel.StatsSnapshotModel(
            self.meta_data,
            known_tasks,
            supported_tasks,
            stats
        )
        self.sender_thread.send(msg)

    def on_vm_snapshot(self, vm_data):
        msg = statssnapshotmodel.VMSnapshotModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            vm_data
        )
        self.sender_thread.send(msg)

    def on_peer_snapshot(self, p2p_data):
        msg = statssnapshotmodel.P2PSnapshotModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            p2p_data
        )
        self.sender_thread.send(msg)

    def on_task_computer_snapshot(self, task_computer):
        msg = TaskComputerSnapshotModel(self.meta_data, task_computer)
        self.sender_thread.send(msg)

    def on_requestor_stats_snapshot(self,
                                    current_stats: CurrentStats,
                                    finished_stats: FinishedTasksStats):
        msg = statssnapshotmodel.RequestorStatsModel(
            self.meta_data, current_stats, finished_stats)
        self.sender_thread.send(msg)

    def on_payment(self, addr, value):
        if not self.send_payment_info:
            return
        self.sender_thread.send(
            ExpenditureModel(
                self.meta_data.cliid,
                self.meta_data.sessid,
                addr,
                value
            )
        )

    def on_income(self, addr, value):
        if not self.send_payment_info:
            return
        self.sender_thread.send(
            IncomeModel(
                self.meta_data.cliid,
                self.meta_data.sessid,
                addr,
                value
            )
        )

    def on_balance_snapshot(self, eth_balance: int, gnt_balance: int,
                            gntb_balance: int):
        if not self.send_payment_info:
            return
        self.sender_thread.send(
            BalanceModel(
                self.meta_data,
                eth_balance,
                gnt_balance,
                gntb_balance
            )
        )
