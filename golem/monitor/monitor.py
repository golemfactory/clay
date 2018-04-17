import logging
import queue
import threading

import requests
from pydispatch import dispatcher

from golem.config.active import SEND_PAYMENT_INFO_TO_MONITOR
from golem.core import variables
from golem.decorators import log_error
from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats
from golem.core.service import LoopingCallService
from .model.modelbase import ModelBase
from .model import statssnapshotmodel
from .model.balancemodel import BalanceModel
from .model.loginlogoutmodel import LoginModel, LogoutModel
from .model.nodemetadatamodel import NodeInfoModel, NodeMetadataModel
from .model.paymentmodel import ExpenditureModel, IncomeModel
from .model.pingmodel import PingModel
from .model.taskcomputersnapshotmodel import TaskComputerSnapshotModel
from .transport.sender import DefaultJSONSender as Sender

log = logging.getLogger('golem.monitor')


class SenderAction:  # pylint: disable=too-few-public-methods
    def __init__(self, action: str, args: dict) -> None:
        self.action = action
        self.args = args


class SenderThread(threading.Thread):
    def __init__(self, node_info, config, sender):
        super().__init__()
        self.queue = queue.Queue()
        self.stop_request = threading.Event()
        self.node_info = node_info
        self.sender = sender
        self.config = config

    def process(self, action: str, **args):
        self.queue.put(SenderAction(action, args))

    def run(self):
        while not self.stop_request.isSet():
            try:
                action = self.queue.get(True,
                                        self.config['SENDER_THREAD_TIMEOUT'])
                action_handler = \
                    getattr(self, 'do_'+action.action,
                            lambda **_:  # default handler
                            log.warning('Unsupported action %s arguments: %s',
                                        action.action, action.args))
                action_handler(**action.args)
            except queue.Empty:
                # send ping message
                self.do_send(self.node_info)
            # TODO: handle more errors to prevent sender from stopping

    def do_send(self, msg: ModelBase):
        self.sender.send(msg)

    def do_finish(self):
        self.stop_request.set()

    def do_ping_me(self, ports):
        try:
            for host in self.config['PING_ME_HOSTS']:
                result = self.sender.send(
                    PingModel(self.node_info.cliid,
                              self.node_info.sessid, ports),
                    host=host, url_path='ping-me')
                if result:
                    self.process_ping_result(result.json())
                log.debug('Ping result: %r', result)
        except requests.ConnectionError:
            log.exception('Ping connection error')

    def do_update_node_info(self, node_info):
        self.node_info = node_info

    @staticmethod
    def process_ping_result(result):
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

    def join(self, timeout=None):
        self.process('finish')
        super().join(timeout)


class PingService(LoopingCallService):
    ports: tuple = ()

    def __init__(self,
                 interval_seconds: int,
                 ports: tuple = ()) -> None:
        super().__init__(interval_seconds)
        self.ports = ports

    def _run(self):
        dispatcher.send(
            signal='golem.monitor',
            event='ping_me',
            ports=self.ports)

    def start(self, now: bool = True):
        if self.ports:
            super().start(now)

    def stop(self):
        if self.running:
            super().stop()

    def reconfigure(self,
                    interval_seconds=None,
                    ports=None):
        self.stop()

        if interval_seconds is not None:
            self.__interval_seconds = interval_seconds
        if ports is not None:
            self.ports = ports

        self.start()


class SystemMonitor:
    def __init__(self,
                 meta_data: NodeMetadataModel,
                 monitor_config: dict) -> None:
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.config = monitor_config
        self.send_payment_info = SEND_PAYMENT_INFO_TO_MONITOR
        dispatcher.connect(self.dispatch_listener, signal='golem.monitor')
        dispatcher.connect(self.p2p_listener, signal='golem.p2p')
        self.sender_thread = self._create_sender_thread()
        self.ping_service = PingService(
            interval_seconds=self.config['PING_INTERVAL'])

    def _create_sender_thread(self) -> SenderThread:
        host = self.config['HOST']
        request_timeout = self.config['REQUEST_TIMEOUT']
        proto_ver = self.config['PROTO_VERSION']
        return SenderThread(
            node_info=self.node_info,
            config=self.config,
            sender=Sender(host, request_timeout, proto_ver)
        )

    def p2p_listener(self, event='default', ports=None, *_, **__):
        if event != 'listening':
            return
        self.ping_service.reconfigure(ports=ports)

    @log_error()
    def dispatch_listener(self, sender, signal, event='default',
                          **kwargs):  # pylint: disable=unused-argument
        """ Main PubSub listener for golem_monitor channel """
        method_name = "on_%s" % (event,)
        if not hasattr(self, method_name):
            log.warning('Unrecognized event received: golem_monitor %s', event)
            return
        getattr(self, method_name)(**kwargs)

    # Initialization

    def start(self):
        self.sender_thread.start()
        self.ping_service.start()

    def shut_down(self):
        dispatcher.disconnect(self.dispatch_listener, signal='golem.monitor')
        dispatcher.disconnect(self.p2p_listener, signal='golem.p2p')
        self.ping_service.stop()
        self.sender_thread.join()

    # Public interface

    def stop(self):
        self.on_logout()
        self.shut_down()

    def send_model(self, model: ModelBase):
        self.sender_thread.process('send', msg=model)

    def on_ping_me(self, ports):
        self.sender_thread.process(
            'ping_me',
            ports=ports)

    def on_shutdown(self):
        self.stop()

    def on_login(self):
        self.send_model(LoginModel(self.meta_data))

    def on_config_update(self, meta_data):
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.sender_thread.process('update_node_info', node_info=self.node_info)
        self.send_model(LoginModel(self.meta_data))
        self.ping_service.reconfigure(
            interval_seconds=self.config['PING_INTERVAL'])

    def on_computation_time_spent(self, success, value):
        msg = statssnapshotmodel.ComputationTime(
            self.meta_data,
            success,
            value
        )
        self.send_model(msg)

    def on_logout(self):
        self.send_model(LogoutModel(self.meta_data))

    def on_stats_snapshot(self, known_tasks, supported_tasks, stats):
        msg = statssnapshotmodel.StatsSnapshotModel(
            self.meta_data,
            known_tasks,
            supported_tasks,
            stats
        )
        self.send_model(msg)

    def on_vm_snapshot(self, vm_data):
        msg = statssnapshotmodel.VMSnapshotModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            vm_data
        )
        self.send_model(msg)

    def on_peer_snapshot(self, p2p_data):
        msg = statssnapshotmodel.P2PSnapshotModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            p2p_data
        )
        self.send_model(msg)

    def on_task_computer_snapshot(self, task_computer):
        msg = TaskComputerSnapshotModel(self.meta_data, task_computer)
        self.send_model(msg)

    def on_requestor_stats_snapshot(self,
                                    current_stats: CurrentStats,
                                    finished_stats: FinishedTasksStats):
        msg = statssnapshotmodel.RequestorStatsModel(
            self.meta_data, current_stats, finished_stats)
        self.send_model(msg)

    def on_payment(self, addr, value):
        if not self.send_payment_info:
            return
        self.send_model(
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
        self.send_model(
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
        self.send_model(
            BalanceModel(
                self.meta_data,
                eth_balance,
                gnt_balance,
                gntb_balance
            )
        )
