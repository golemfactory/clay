# -*- coding: utf-8 -*-
import functools
import itertools
import logging
import os
import shutil
import time
import weakref
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
)

from golem_messages import exceptions as msg_exceptions
from golem_messages import message
from golem_messages.datastructures import tasks as dt_tasks
from pydispatch import dispatcher
from twisted.internet.defer import inlineCallbacks

from apps.appsmanager import AppsManager
from apps.core.task.coretask import CoreTask
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.variables import MAX_CONNECT_SOCKET_ADDRESSES
from golem.core.common import node_info_str, short_node_id
from golem.environments.environment import SupportStatus, UnsupportReason
from golem.marketplace import OfferPool
from golem.network.transport import msg_queue
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcpnetwork import (
    TCPNetwork, SocketAddress, SafeProtocol)
from golem.network.transport.tcpserver import (
    PendingConnectionsServer,
)
from golem.ranking.helper.trust import Trust
from golem.ranking.manager.database_manager import (
    get_requestor_efficiency,
    get_requestor_assigned_sum,
    get_requestor_paid_sum,
    update_requestor_paid_sum,
    update_requestor_assigned_sum,
    update_requestor_efficiency,
)
from golem.rpc import utils as rpc_utils
from golem.task import timer
from golem.task.acl import get_acl, _DenyAcl as DenyAcl
from golem.task.benchmarkmanager import BenchmarkManager
from golem.task.taskbase import Task, AcceptClientVerdict
from golem.task.taskconnectionshelper import TaskConnectionsHelper
from golem.task.taskstate import TaskOp
from golem.utils import decode_hex

from .server import concent
from .server import helpers
from .server import queue_ as srv_queue
from .server import resources
from .server import verification as srv_verification
from .taskcomputer import TaskComputer
from .taskkeeper import TaskHeaderKeeper
from .taskmanager import TaskManager
from .tasksession import TaskSession


logger = logging.getLogger(__name__)

tmp_cycler = itertools.cycle(list(range(550)))


def _calculate_price(min_price: int, requestor_id: str) -> int:
    """
    Provider's subtask price function as proposed in
    https://docs.golem.network/About/img/Brass_Golem_Marketplace.pdf
    """
    r = min_price * (1.0 + timer.ProviderTimer.profit_factor)
    v_paid = get_requestor_paid_sum(requestor_id)
    v_assigned = get_requestor_assigned_sum(requestor_id)
    c = min_price
    Q = min(1.0, (min_price + 1 + v_paid + c) / (min_price + 1 + v_assigned))
    R = get_requestor_efficiency(requestor_id)
    S = Q * R
    return max(int(r / S), min_price)


class TaskServer(
        PendingConnectionsServer,
        resources.TaskResourcesMixin,
        srv_queue.TaskMessagesQueueMixin,
        srv_verification.VerificationMixin,
):
    def __init__(self,
                 node,
                 config_desc: ClientConfigDescriptor,
                 client,
                 use_ipv6=False,
                 use_docker_manager=True,
                 task_archiver=None,
                 apps_manager=AppsManager(),
                 task_finished_cb=None) -> None:
        self.client = client
        self.keys_auth = client.keys_auth
        self.config_desc = config_desc

        self.node = node
        self.task_archiver = task_archiver
        self.task_keeper = TaskHeaderKeeper(
            environments_manager=client.environments_manager,
            node=self.node,
            min_price=config_desc.min_price,
            task_archiver=task_archiver)
        self.task_manager = TaskManager(
            self.node,
            self.keys_auth,
            root_path=TaskServer.__get_task_manager_root(client.datadir),
            config_desc=config_desc,
            tasks_dir=os.path.join(client.datadir, 'tasks'),
            apps_manager=apps_manager,
            finished_cb=task_finished_cb,
        )
        benchmarks = self.task_manager.apps_manager.get_benchmarks()
        self.benchmark_manager = BenchmarkManager(
            node_name=config_desc.node_name,
            task_server=self,
            root_path=self.get_task_computer_root(),
            benchmarks=benchmarks
        )
        self.task_computer = TaskComputer(
            task_server=self,
            use_docker_manager=use_docker_manager,
            finished_cb=task_finished_cb)
        self.task_connections_helper = TaskConnectionsHelper()
        self.task_connections_helper.task_server = self
        self.sessions: Dict[str, TaskSession] = {}
        self.task_sessions_incoming: weakref.WeakSet = weakref.WeakSet()

        OfferPool.change_interval(self.config_desc.offer_pooling_interval)

        self.max_trust = 1.0
        self.min_trust = 0.0

        self.last_messages = []

        self.results_to_send = {}
        self.failures_to_send = {}

        self.use_ipv6 = use_ipv6

        self.forwarded_session_request_timeout = \
            config_desc.waiting_for_task_session_timeout
        self.forwarded_session_requests = {}
        self.acl = get_acl(Path(client.datadir),
                           max_times=config_desc.disallow_id_max_times)
        self.acl_ip = DenyAcl([], max_times=config_desc.disallow_ip_max_times)
        self.resource_handshakes = {}
        self.requested_tasks: Set[str] = set()

        network = TCPNetwork(
            ProtocolFactory(SafeProtocol, self, SessionFactory(TaskSession)),
            use_ipv6)
        PendingConnectionsServer.__init__(self, config_desc, network)
        srv_queue.TaskMessagesQueueMixin.__init__(self)
        # instantiate ReceivedMessageHandler connected to self
        # to register in golem.network.concent.handlers_library
        from golem.network.concent import \
            received_handler as concent_received_handler
        self.concent_handler = \
            concent_received_handler.TaskServerMessageHandler(self)

        dispatcher.connect(
            self.income_listener,
            signal='golem.income'
        )
        dispatcher.connect(
            self.finished_subtask_listener,
            signal='golem.taskcomputer'
        )
        dispatcher.connect(
            self.finished_task_listener,
            signal='golem.taskmanager'
        )

    def sync_network(self, timeout=None):
        if timeout is None:
            timeout = self.config_desc.task_session_timeout
        jobs = (
            functools.partial(
                super().sync_network,
                timeout=timeout,
            ),
            self._sync_pending,
            self._send_waiting_results,
            self.task_computer.run,
            self.task_connections_helper.sync,
            self._sync_forwarded_session_requests,
            self.__remove_old_tasks,
            functools.partial(
                concent.process_messages_received_from_concent,
                concent_service=self.client.concent_service,
            ),
            self.sweep_sessions,
            self.connect_to_nodes,
        )

        for job in jobs:
            try:
                #logger.debug("TServer sync running: job=%r", job)
                job()
            except Exception:  # pylint: disable=broad-except
                logger.exception("TaskServer.sync_network job %r failed", job)

        if next(tmp_cycler) == 0:
            logger.debug('TASK SERVER TASKS DUMP: %r', self.task_manager.tasks)
            logger.debug('TASK SERVER TASKS STATES: %r',
                         self.task_manager.tasks_states)

    @inlineCallbacks
    def pause(self):
        super().pause()
        yield CoreTask.VERIFICATION_QUEUE.pause()

    def resume(self):
        super().resume()
        CoreTask.VERIFICATION_QUEUE.resume()

    def get_environment_by_id(self, env_id):
        return self.task_keeper.environments_manager.get_environment_by_id(
            env_id)

    def request_task_by_id(self, task_id: str) -> None:
        """Requests task possibly after successful resource handshake.
        """
        try:
            task_header: dt_tasks.TaskHeader = self.task_keeper.task_headers[
                task_id
            ]
        except KeyError:
            logger.debug("Task missing in TaskKeeper. task_id=%s", task_id)
            return
        self._request_task(task_header)

    def request_task(self) -> Optional[str]:
        """Chooses random task from network to compute on our machine"""
        task_header: dt_tasks.TaskHeader = \
            self.task_keeper.get_task(self.requested_tasks)
        if task_header is None:
            return None
        return self._request_task(task_header)

    def _request_task(self, theader: dt_tasks.TaskHeader) -> Optional[str]:
        try:
            env = self.get_environment_by_id(theader.environment)
            if env is not None:
                performance = env.get_performance()
            else:
                performance = 0.0

            supported = self.should_accept_requestor(theader.task_owner.key)
            if self.config_desc.min_price > theader.max_price:
                supported = supported.join(SupportStatus.err({
                    UnsupportReason.MAX_PRICE: theader.max_price}))

            if self.client.concent_service.enabled:
                if not theader.concent_enabled:
                    supported = supported.join(
                        SupportStatus.err({
                            UnsupportReason.CONCENT_REQUIRED: True,
                        }),
                    )

            if not supported.is_ok():
                logger.debug(
                    "Support status. task_id=%s supported=%s",
                    theader.task_id,
                    supported,
                )
                if self.task_archiver:
                    self.task_archiver.add_support_status(
                        theader.task_id,
                        supported,
                    )
                return None

            # Check handshake
            handshake = self.resource_handshakes.get(theader.task_owner.key)
            if not handshake:
                logger.debug(
                    "Starting handshake. key_id=%r, task_id=%r",
                    theader.task_owner.key,
                    theader.task_id,
                )
                self.start_handshake(
                    key_id=theader.task_owner.key,
                    task_id=theader.task_id,
                )
                return None
            if not handshake.success():
                logger.debug(
                    "Handshake still in progress. key_id=%r, task_id=%r",
                    theader.task_owner.key,
                    theader.task_id,
                )
                return None

            # Send WTCT
            price = _calculate_price(
                self.config_desc.min_price,
                theader.task_owner.key,
            )
            price = min(price, theader.max_price)
            self.task_manager.add_comp_task_request(
                theader=theader, price=price)
            wtct = message.tasks.WantToComputeTask(
                node_name=self.config_desc.node_name,
                perf_index=performance,
                price=price,
                max_resource_size=self.config_desc.max_resource_size,
                max_memory_size=self.config_desc.max_memory_size,
                concent_enabled=self.client.concent_service.enabled,
                provider_public_key=self.get_key_id(),
                provider_ethereum_public_key=self.get_key_id(),
                task_header=theader,
            )
            msg_queue.put(
                node_id=theader.task_owner.key,
                msg=wtct,
            )
            timer.ProviderTTCDelayTimers.start(wtct.task_id)
            self.requested_tasks.add(theader.task_id)
            return theader.task_id
        except Exception as err:  # pylint: disable=broad-except
            logger.warning("Cannot send request for task: %s", err)
            logger.debug("Detailed traceback", exc_info=True)
            self.remove_task_header(theader.task_id)

        return None

    def task_given(self, node_id: str, ctd: message.ComputeTaskDef,
                   price: int) -> bool:
        if not self.task_computer.task_given(ctd):
            return False
        self.requested_tasks.clear()
        update_requestor_assigned_sum(node_id, price)
        dispatcher.send(
            signal='golem.subtask',
            event='started',
            subtask_id=ctd['subtask_id'],
            price=price,
        )
        return True

    def send_results(self, subtask_id, task_id, result):

        if 'data' not in result:
            raise AttributeError("Wrong result format")

        if subtask_id in self.results_to_send:
            raise RuntimeError("Incorrect subtask_id: {}".format(subtask_id))

        # this is purely for tests
        if self.config_desc.overwrite_results:
            for file_path in result['data']:
                shutil.copyfile(
                    src=self.config_desc.overwrite_results,
                    dst=file_path)

        header = self.task_keeper.task_headers[task_id]

        delay_time = 0.0
        last_sending_trial = 0

        wtr = WaitingTaskResult(
            task_id=task_id,
            subtask_id=subtask_id,
            result=result['data'],
            last_sending_trial=last_sending_trial,
            delay_time=delay_time,
            owner=header.task_owner)

        self._create_and_set_result_package(wtr)
        self.results_to_send[subtask_id] = wtr

        Trust.REQUESTED.increase(header.task_owner.key)

    def _create_and_set_result_package(self, wtr):
        task_result_manager = self.task_manager.task_result_manager

        wtr.result_secret = task_result_manager.gen_secret()
        result = task_result_manager.create(wtr, wtr.result_secret)
        (
            wtr.result_hash,
            wtr.result_path,
            wtr.package_sha1,
            wtr.result_size,
            wtr.package_path,
        ) = \
            result

    def send_task_failed(
            self, subtask_id: str, task_id: str, err_msg: str) -> None:

        header = self.task_keeper.task_headers[task_id]

        if subtask_id not in self.failures_to_send:
            Trust.REQUESTED.decrease(header.task_owner.key)

            self.failures_to_send[subtask_id] = WaitingTaskFailure(
                task_id=task_id,
                subtask_id=subtask_id,
                err_msg=err_msg,
                owner=header.task_owner)

    def new_connection(self, session):
        if not self.active:
            session.disconnect(message.base.Disconnect.REASON.NoMoreMessages)
            return
        logger.debug(
            'Incoming TaskSession. address=%s:%d',
            session.address,
            session.port,
        )
        self.task_sessions_incoming.add(session)

    def disconnect(self):
        for node_id in list(self.sessions):
            try:
                task_session = self.sessions[node_id]
                if task_session is None:
                    # Pending connection
                    continue
                task_session.dropped()
                del self.sessions[node_id]
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Error closing session: %s", exc)

    def get_own_tasks_headers(self):
        return self.task_manager.get_tasks_headers()

    def get_others_tasks_headers(self) -> List[dt_tasks.TaskHeader]:
        return self.task_keeper.get_all_tasks()

    def add_task_header(self, task_header: dt_tasks.TaskHeader) -> bool:
        if not self.verify_header_sig(task_header):
            logger.info(
                'Invalid signature task_header:%r, signature: %r',
                task_header,
                task_header.signature,
            )
            return False
        if task_header.deadline < time.time():
            logger.info(
                "Task's deadline already in the past. task_header: %r",
                task_header
            )
            return False
        try:
            if self.task_manager.is_my_task(task_header.task_id) or \
                    task_header.task_owner.key == self.node.key:
                return True  # Own tasks are not added to task keeper

            return self.task_keeper.add_task_header(task_header)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Task header validation failed")
            return False

    @classmethod
    def verify_header_sig(cls, header: dt_tasks.TaskHeader):
        try:
            header.verify(public_key=decode_hex(header.task_owner.key))
        except msg_exceptions.CryptoError:
            logger.debug(
                'hdr verification failed. hdr.task_owner.key: %r',
                header.task_owner.key,
                exc_info=True,
            )
            return False
        return True

    @rpc_utils.expose('comp.tasks.known.delete')
    def remove_task_header(self, task_id) -> bool:
        self.requested_tasks.discard(task_id)
        return self.task_keeper.remove_task_header(task_id)

    def set_last_message(self, type_, t, msg, address, port):
        if len(self.last_messages) >= 5:
            self.last_messages = self.last_messages[-4:]

        self.last_messages.append([type_, t, address, port, msg])

    def get_node_name(self):
        return self.config_desc.node_name

    def get_key_id(self):
        return self.keys_auth.key_id

    def sign(self, data):
        return self.keys_auth.sign(data)

    def get_resource_addr(self):
        return self.client.node.prv_addr

    def get_resource_port(self):
        return self.client.resource_port

    def task_result_sent(self, subtask_id):
        return self.results_to_send.pop(subtask_id, None)

    def retry_sending_task_result(self, subtask_id):
        wtr = self.results_to_send.get(subtask_id, None)
        if wtr:
            wtr.already_sending = False

    def change_config(self, config_desc, run_benchmarks=False):
        PendingConnectionsServer.change_config(self, config_desc)
        self.config_desc = config_desc
        self.task_keeper.change_config(config_desc)
        return self.task_computer.change_config(
            config_desc, run_benchmarks=run_benchmarks)

    def get_task_computer_root(self):
        return os.path.join(self.client.datadir, "ComputerRes")

    def subtask_rejected(self, sender_node_id, subtask_id):
        """My (providers) results were rejected"""
        logger.debug("Subtask %r result rejected", subtask_id)
        self.task_result_sent(subtask_id)

        self.decrease_trust_payment(sender_node_id)
        # self.remove_task_header(task_id)
        # TODO Inform transaction system and task manager about rejected
        # subtask. Issue #2405

    # pylint:disable=too-many-arguments
    def subtask_accepted(
            self,
            sender_node_id: str,
            subtask_id: str,
            payer_address: str,
            value: int,
            accepted_ts: int):
        """My (providers) results were accepted"""
        logger.debug("Subtask %r result accepted", subtask_id)
        self.task_result_sent(subtask_id)
        self.client.transaction_system.expect_income(
            sender_node_id,
            subtask_id,
            payer_address,
            value,
            accepted_ts,
        )

    def subtask_settled(self, sender_node_id, subtask_id, settled_ts):
        """My (provider's) results were accepted by the Concent"""
        logger.debug("Subtask %r settled by the Concent", subtask_id)
        self.task_result_sent(subtask_id)
        self.client.transaction_system.settle_income(
            sender_node_id, subtask_id, settled_ts)

    def subtask_waiting(self, task_id, subtask_id=None):
        logger.debug(
            "Requestor waits for subtask results."
            " task_id=%(task_id)s subtask_id=%(subtask_id)s",
            {
                'task_id': task_id,
                'subtask_id': subtask_id,
            },
        )
        # We can still try to request a subtask for this task next time.
        self.requested_tasks.discard(task_id)

    def subtask_failure(self, subtask_id, err):
        logger.info("Computation for task %r failed: %r.", subtask_id, err)
        node_id = self.task_manager.get_node_id_for_subtask(subtask_id)
        Trust.COMPUTED.decrease(node_id)
        self.task_manager.task_computation_failure(subtask_id, err)

    def accept_result(self, subtask_id, key_id, eth_address: str, value: int,
                      *, unlock_funds=True):
        mod = min(
            max(self.task_manager.get_trust_mod(subtask_id), self.min_trust),
            self.max_trust)
        Trust.COMPUTED.increase(key_id, mod)

        task_id = self.task_manager.get_task_id(subtask_id)

        payment_processed_ts = self.client.transaction_system.add_payment_info(
            subtask_id,
            value,
            eth_address,
        )
        if unlock_funds:
            self.client.funds_locker.remove_subtask(task_id)
        logger.debug('Result accepted for subtask: %s Created payment ts: %r',
                     subtask_id, payment_processed_ts)
        return payment_processed_ts

    def income_listener(self, event='default', node_id=None, **kwargs):
        if event == 'confirmed':
            self.increase_trust_payment(node_id, kwargs['amount'])
        elif event == 'overdue_single':
            self.decrease_trust_payment(node_id)

    def finished_subtask_listener(self,  # pylint: disable=too-many-arguments
                                  event='default', subtask_id=None,
                                  min_performance=None, **_kwargs):

        if event != 'subtask_finished':
            return

        keeper = self.task_manager.comp_task_keeper

        try:

            task_id = keeper.get_task_id_for_subtask(subtask_id)
            header = keeper.get_task_header(task_id)
            environment = self.get_environment_by_id(header.environment)
            computation_time = timer.ProviderTimer.time

            update_requestor_efficiency(
                node_id=keeper.get_node_for_task_id(task_id),
                timeout=header.subtask_timeout,
                computation_time=computation_time,
                performance=environment.get_performance(),
                min_performance=min_performance,
            )

        except (KeyError, ValueError, AttributeError) as exc:
            logger.error("Finished subtask listener: %r", exc)
            return

    def finished_task_listener(self, event='default', task_id=None, op=None,
                               **_kwargs):
        if not (event == 'task_status_updated'
                and self.client.p2pservice):
            return
        if not (op in [TaskOp.FINISHED, TaskOp.TIMEOUT]):
            return
        self.client.p2pservice.remove_task(task_id)
        self.client.funds_locker.remove_task(task_id)

    def increase_trust_payment(self, node_id: str, amount: int):
        Trust.PAYMENT.increase(node_id, self.max_trust)
        update_requestor_paid_sum(node_id, amount)

    def decrease_trust_payment(self, node_id: str):
        Trust.PAYMENT.decrease(node_id, self.max_trust)

    def reject_result(self, subtask_id, key_id):
        mod = min(
            max(self.task_manager.get_trust_mod(subtask_id), self.min_trust),
            self.max_trust)
        Trust.WRONG_COMPUTED.decrease(key_id, mod)

    def get_computing_trust(self, node_id):
        return self.client.get_computing_trust(node_id)

    def get_socket_addresses(self, node_info, prv_port=None, pub_port=None):
        """ Change node info into tcp addresses. Adds a suggested address.
        :param Node node_info: node information
        :param prv_port: private port that should be used
        :param pub_port: public port that should be used
        :return:
        """
        prv_port = prv_port or node_info.prv_port
        pub_port = pub_port or node_info.pub_port

        socket_addresses = super().get_socket_addresses(
            node_info=node_info,
            prv_port=prv_port,
            pub_port=pub_port
        )

        address = self.client.get_suggested_addr(node_info.key)
        if not address:
            return socket_addresses

        if self._is_address_valid(address, prv_port):
            socket_address = SocketAddress(address, prv_port)
            self._prepend_address(socket_addresses, socket_address)

        if self._is_address_valid(address, pub_port):
            socket_address = SocketAddress(address, pub_port)
            self._prepend_address(socket_addresses, socket_address)

        return socket_addresses[:MAX_CONNECT_SOCKET_ADDRESSES]

    def quit(self):
        self.task_computer.quit()

    def add_forwarded_session_request(self, key_id, conn_id):
        self.forwarded_session_requests[key_id] = dict(
            conn_id=conn_id, time=time.time())

    def get_min_performance_for_task(self, task: Task) -> float:
        env = self.get_environment_by_id(task.header.environment)
        return env.get_min_accepted_performance()

    class RejectedReason(Enum):
        not_my_task = 'not my task'
        performance = 'performance'
        disk_size = 'disk size'
        memory_size = 'memory size'
        acl = 'acl'
        trust = 'trust'
        netmask = 'netmask'
        not_accepted = 'not accepted'

    def should_accept_provider(  # noqa pylint: disable=too-many-arguments,too-many-return-statements,unused-argument
            self,
            node_id,
            address,
            node_name,
            task_id,
            provider_perf,
            max_resource_size,
            max_memory_size):

        node_name_id = node_info_str(node_name, node_id)
        ids = f'provider={node_name_id}, task_id={task_id}'

        if task_id not in self.task_manager.tasks:
            logger.info('Cannot find task in my tasks: %s', ids)
            self.notify_provider_rejected(
                node_id=node_id, task_id=task_id,
                reason=self.RejectedReason.not_my_task)
            return False

        task = self.task_manager.tasks[task_id]
        min_accepted_perf = self.get_min_performance_for_task(task)

        if min_accepted_perf > int(provider_perf):
            logger.info(f'insufficient provider performance: {provider_perf}'
                        f' < {min_accepted_perf}; {ids}')
            self.notify_provider_rejected(
                node_id=node_id, task_id=task_id,
                reason=self.RejectedReason.performance,
                details={
                    'provider_perf': provider_perf,
                    'min_accepted_perf': min_accepted_perf,
                })
            return False

        if task.header.estimated_memory > (int(max_memory_size) * 1024):
            logger.info('insufficient provider memory size: '
                        f'{task.header.estimated_memory} B < {max_memory_size} '
                        f'KiB; {ids}')
            self.notify_provider_rejected(
                node_id=node_id, task_id=task_id,
                reason=self.RejectedReason.memory_size,
                details={
                    'memory_size': task.header.estimated_memory,
                    'max_memory_size': max_memory_size * 1024,
                })
            return False

        allowed, reason = self.acl.is_allowed(node_id)
        if allowed:
            allowed, reason = self.acl_ip.is_allowed(address)
        if not allowed:
            logger.info(f'provider is {reason.value}; {ids}')
            self.notify_provider_rejected(
                node_id=node_id, task_id=task_id,
                reason=self.RejectedReason.acl,
                details={'acl_reason': reason.value})
            return False

        trust = self.get_computing_trust(node_id)
        if trust < self.config_desc.computing_trust:
            logger.info(f'insufficient provider trust level: {trust} < '
                        f'{self.config_desc.computing_trust}; {ids}')
            self.notify_provider_rejected(
                node_id=node_id, task_id=task_id,
                reason=self.RejectedReason.trust,
                details={
                    'trust': trust,
                    'required_trust': self.config_desc.computing_trust,
                })
            return False

        if not task.header.mask.matches(decode_hex(node_id)):
            logger.info(f'network mask mismatch: {ids}')
            self.notify_provider_rejected(
                node_id=node_id, task_id=task_id,
                reason=self.RejectedReason.netmask)
            return False

        accept_client_verdict: AcceptClientVerdict \
            = task.should_accept_client(node_id)
        if accept_client_verdict != AcceptClientVerdict.ACCEPTED:
            logger.info(f'provider {node_id} is not allowed'
                        f' for this task at this moment '
                        f'(either waiting for results or previously failed)')
            self.notify_provider_rejected(
                node_id=node_id, task_id=task_id,
                reason=self.RejectedReason.not_accepted,
                details={
                    'verdict': accept_client_verdict.value,
                })
            return False

        logger.debug('provider can be accepted %s', ids)
        return True

    @classmethod
    def notify_provider_rejected(cls, node_id: str, task_id: str,
                                 reason: RejectedReason,
                                 details: Optional[Dict[str, Any]] = None):
        dispatcher.send(
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id=task_id,
            reason=reason.value,
            details=details,
        )

    def should_accept_requestor(self, node_id):
        allowed, reason = self.acl.is_allowed(node_id)
        if not allowed:
            short_id = short_node_id(node_id)
            logger.info('requestor is %s. node=%s', reason, short_id)
            return SupportStatus.err({UnsupportReason.DENY_LIST: node_id})
        trust = self.client.get_requesting_trust(node_id)
        logger.debug("Requesting trust level: %r", trust)
        if trust >= self.config_desc.requesting_trust:
            return SupportStatus.ok()
        return SupportStatus.err({UnsupportReason.REQUESTOR_TRUST: trust})

    def disallow_node(self, node_id: str, timeout_seconds: int, persist: bool) \
            -> None:
        self.acl.disallow(node_id, timeout_seconds, persist)

    @rpc_utils.expose('net.peer.block_ip')
    def disallow_ip(self, ip: str, timeout_seconds: int) -> None:
        self.acl_ip.disallow(ip, timeout_seconds)

    def _sync_forwarded_session_requests(self):
        now = time.time()
        for key_id, data in list(self.forwarded_session_requests.items()):
            if not data:
                del self.forwarded_session_requests[key_id]
                continue
            if now - data['time'] >= self.forwarded_session_request_timeout:
                logger.debug('connection timeout: %s', data)
                del self.forwarded_session_requests[key_id]
                self.final_conn_failure(data['conn_id'])

    def _get_factory(self):
        return self.factory(self)

    def _listening_established(self, port, **kwargs):
        logger.debug('_listening_established(%r)', port)
        self.cur_port = port
        logger.info(" Port {} opened - listening".format(self.cur_port))
        self.node.prv_port = self.cur_port
        self.task_manager.node = self.node

    def _listening_failure(self, **kwargs):
        logger.error("Listening on ports {} to {} failure".format(
            self.config_desc.start_port, self.config_desc.end_port))
        # FIXME: some graceful terminations should take place here. #1287
        # sys.exit(0)

    #############################
    # SYNC METHODS
    #############################
    def __remove_old_tasks(self):
        self.task_keeper.remove_old_tasks()
        self.task_manager.comp_task_keeper.remove_old_tasks()
        nodes_with_timeouts = self.task_manager.check_timeouts()
        for node_id in nodes_with_timeouts:
            Trust.COMPUTED.decrease(node_id)

    def _send_waiting_results(self):
        for subtask_id in list(self.results_to_send.keys()):
            wtr: WaitingTaskResult = self.results_to_send[subtask_id]
            now = time.time()

            if not wtr.already_sending:
                if now - wtr.last_sending_trial > wtr.delay_time:
                    wtr.already_sending = True
                    wtr.last_sending_trial = now
                    helpers.send_report_computed_task(
                        task_server=self,
                        waiting_task_result=wtr,
                    )

        for wtf in list(self.failures_to_send.values()):
            helpers.send_task_failure(
                waiting_task_failure=wtf,
            )
        self.failures_to_send.clear()

    # CONFIGURATION METHODS
    #############################
    @staticmethod
    def __get_task_manager_root(datadir):
        return os.path.join(datadir, "ComputerRes")


# TODO: https://github.com/golemfactory/golem/issues/2633
#       and remove linter switch offs
# pylint: disable=too-many-arguments, too-many-locals
class WaitingTaskResult(object):
    def __init__(self, task_id, subtask_id, result,
                 last_sending_trial, delay_time, owner, result_path=None,
                 result_hash=None, result_secret=None, package_sha1=None,
                 result_size=None, package_path=None):

        self.task_id = task_id
        self.subtask_id = subtask_id
        self.last_sending_trial = last_sending_trial
        self.delay_time = delay_time
        self.owner = owner

        self.result = result
        self.result_path = result_path
        self.result_hash = result_hash
        self.result_secret = result_secret
        self.package_sha1 = package_sha1
        self.package_path = package_path
        self.result_size = result_size

        self.already_sending = False
# pylint: enable=too-many-arguments, too-many-locals


class WaitingTaskFailure(object):
    def __init__(self, task_id, subtask_id, err_msg, owner):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.owner = owner
        self.err_msg = err_msg
