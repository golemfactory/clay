from golem.decorators import log_error
import logging
from pydispatch import dispatcher
import threading
import queue

from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats
from .model.nodemetadatamodel import NodeMetadataModel, NodeInfoModel
from .model.loginlogoutmodel import LoginModel, LogoutModel
from .model.taskcomputersnapshotmodel import TaskComputerSnapshotModel
from .model.paymentmodel import ExpenditureModel, IncomeModel
from .transport.sender import DefaultJSONSender as Sender
from .model import statssnapshotmodel

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
    def __init__(self, meta_data, monitor_config):
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.config = monitor_config
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

    def p2p_listener(self, sender, signal, event='default', **kwargs):
        if event != 'listening':
            return
        try:
            result = self.ping_request(kwargs['port'])
            if not result['success']:
                status = result['description'].replace('\n', ', ')
                log.warning('Port status: {}'.format(status))
                dispatcher.send(
                    'golem.p2p',
                    event='unreachable',
                    port=kwargs['port'],
                    description=result['description']
                )
        except Exception:
            log.exception('Port reachability check error')

    def ping_request(self, port):
        import requests
        timeout = 1  # seconds
        try:
            response = requests.post(
                '%sping-me' % (self.config['HOST'],),
                data={'port': port, },
                timeout=timeout,
            )
            result = response.json()
        except requests.ConnectionError as e:
            result = {'success': False, 'description': 'Local error: %s' % e}
        log.debug('ping result %r', result)
        return result

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
        msg = ExpenditureModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            addr,
            value
        )
        self.sender_thread.send(msg)

    def on_income(self, addr, value):
        msg = IncomeModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            addr,
            value
        )
        self.sender_thread.send(msg)
