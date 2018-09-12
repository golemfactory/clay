# -*- coding: utf-8 -*-
import functools
import itertools
import logging
import os
import time
import weakref
from collections import deque
from pathlib import Path
from typing import Optional

from golem_messages import message
from pydispatch import dispatcher
from twisted.internet.defer import inlineCallbacks

from apps.appsmanager import AppsManager
from apps.core.task.coretask import CoreTask, AcceptClientVerdict
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.variables import MAX_CONNECT_SOCKET_ADDRESSES
from golem.environments.environment import SupportStatus, UnsupportReason
from golem.network.p2p import node as p2p_node
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcpnetwork import (
    TCPNetwork, SocketAddress, SafeProtocol)
from golem.network.transport.tcpserver import (
    PendingConnectionsServer, PenConnStatus)
from golem.ranking.helper.trust import Trust
from golem.task.acl import get_acl
from golem.task.benchmarkmanager import BenchmarkManager
from golem.task.taskbase import TaskHeader, Task
from golem.task.taskconnectionshelper import TaskConnectionsHelper
from golem.task.taskstate import TaskOp
from golem.utils import decode_hex, pubkeytoaddr

from . import exceptions
from .result.resultmanager import ExtractedPackage
from .server import resources
from .server import concent
from .taskcomputer import TaskComputer
from .taskkeeper import TaskHeaderKeeper
from .taskmanager import TaskManager
from .tasksession import TaskSession


logger = logging.getLogger('golem.task.taskserver')

tmp_cycler = itertools.cycle(list(range(550)))


class TaskServer(
        PendingConnectionsServer,
        resources.TaskResourcesMixin):
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
            config_desc.node_name,
            self.node,
            self.keys_auth,
            root_path=TaskServer.__get_task_manager_root(client.datadir),
            use_distributed_resources=config_desc.
            use_distributed_resource_management,
            tasks_dir=os.path.join(client.datadir, 'tasks'),
            apps_manager=apps_manager,
            finished_cb=task_finished_cb,
        )
        benchmarks = self.task_manager.apps_manager.get_benchmarks()
        self.benchmark_manager = BenchmarkManager(config_desc.node_name, self,
                                                  client.datadir, benchmarks)
        self.task_computer = TaskComputer(
            task_server=self,
            use_docker_manager=use_docker_manager,
            finished_cb=task_finished_cb)
        self.task_connections_helper = TaskConnectionsHelper()
        self.task_connections_helper.task_server = self
        self.task_sessions = {}
        self.task_sessions_incoming = weakref.WeakSet()

        self.max_trust = 1.0
        self.min_trust = 0.0

        self.last_messages = []
        self.last_message_time_threshold = config_desc.task_session_timeout

        self.results_to_send = {}
        self.failures_to_send = {}

        self.use_ipv6 = use_ipv6

        self.forwarded_session_request_timeout = \
            config_desc.waiting_for_task_session_timeout
        self.forwarded_session_requests = {}
        self.response_list = {}
        self.acl = get_acl(Path(client.datadir))
        self.resource_handshakes = {}

        network = TCPNetwork(
            ProtocolFactory(SafeProtocol, self, SessionFactory(TaskSession)),
            use_ipv6)
        PendingConnectionsServer.__init__(self, config_desc, network)
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
            self.finished_task_listener,
            signal='golem.taskmanager'
        )

    def sync_network(self, timeout=None):
        if timeout is None:
            timeout = self.last_message_time_threshold
        jobs = (
            functools.partial(
                super().sync_network,
                timeout=timeout,
            ),
            self._sync_pending,
            self.__send_waiting_results,
            self.task_computer.run,
            self.task_connections_helper.sync,
            self._sync_forwarded_session_requests,
            self.__remove_old_tasks,
            self.__remove_old_sessions,
            functools.partial(
                concent.process_messages_received_from_concent,
                concent_service=self.client.concent_service,
            ),
        )

        for job in jobs:
            try:
                logger.debug("TServer sync running: job=%r", job)
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

    # This method chooses random task from the network to compute on our machine
    def request_task(self) -> Optional[str]:
        theader = self.task_keeper.get_task()
        if theader is None:
            return None
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
                if not theader.fixed_header.concent_enabled:
                    supported = supported.join(
                        SupportStatus.err({
                            UnsupportReason.CONCENT_REQUIRED: True,
                        }),
                    )

            if supported.is_ok():
                price = int(theader.max_price)
                self.task_manager.add_comp_task_request(
                    theader=theader, price=price)
                args = {
                    'node_name': self.config_desc.node_name,
                    'key_id': theader.task_owner.key,
                    'task_id': theader.task_id,
                    'estimated_performance': performance,
                    'price': self.config_desc.min_price,
                    'max_resource_size': self.config_desc.max_resource_size,
                    'max_memory_size': self.config_desc.max_memory_size,
                    'num_cores': self.config_desc.num_cores
                }

                node = theader.task_owner
                added = self._add_pending_request(
                    TASK_CONN_TYPES['task_request'],
                    node,
                    prv_port=node.prv_port,
                    pub_port=node.pub_port,
                    args=args
                )
                if added:
                    return theader.task_id

                supported = supported.join(SupportStatus.err({
                    UnsupportReason.NODE_INFORMATION: node.__dict__
                }))

            if self.task_archiver:
                self.task_archiver.add_support_status(theader.task_id,
                                                      supported)
        except Exception as err:
            logger.warning("Cannot send request for task: {}".format(err))
            self.task_keeper.remove_task_header(theader.task_id)

        return None

    def send_results(self, subtask_id, task_id, result):

        if 'data' not in result or 'result_type' not in result:
            raise AttributeError("Wrong result format")

        header = self.task_keeper.task_headers[task_id]

        if subtask_id not in self.results_to_send:
            value = self.task_manager.comp_task_keeper.get_value(task_id)
            self.client.transaction_system.expect_income(
                sender_node=header.task_owner.key,
                subtask_id=subtask_id,
                payer_address=pubkeytoaddr(header.task_owner.key),
                value=value,
            )

            delay_time = 0.0
            last_sending_trial = 0

            wtr = WaitingTaskResult(
                task_id=task_id,
                subtask_id=subtask_id,
                result=result['data'],
                result_type=result['result_type'],
                last_sending_trial=last_sending_trial,
                delay_time=delay_time,
                owner=header.task_owner)

            self.create_and_set_result_package(wtr)
            self.results_to_send[subtask_id] = wtr

            Trust.REQUESTED.increase(header.task_owner.key)
        else:
            raise RuntimeError("Incorrect subtask_id: {}".format(subtask_id))

        return True

    def create_and_set_result_package(self, wtr):
        task_result_manager = self.task_manager.task_result_manager

        wtr.result_secret = task_result_manager.gen_secret()
        result = task_result_manager.create(self.node, wtr, wtr.result_secret)
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
        if self.active:
            self.task_sessions_incoming.add(session)
        else:
            session.disconnect(message.base.Disconnect.REASON.NoMoreMessages)

    def disconnect(self):
        task_sessions = dict(self.task_sessions)
        sessions_incoming = weakref.WeakSet(self.task_sessions_incoming)

        for task_session in list(task_sessions.values()):
            task_session.dropped()

        for task_session in sessions_incoming:
            try:
                task_session.dropped()
            except Exception as exc:
                logger.error("Error closing incoming session: %s", exc)

    def get_own_tasks_headers(self):
        ths_tm = self.task_manager.get_tasks_headers()
        return [th.to_dict() for th in ths_tm]

    def get_others_tasks_headers(self):
        ths_tk = self.task_keeper.get_all_tasks()
        return [th.to_dict() for th in ths_tk]

    def add_task_header(self, th_dict_repr: dict) -> bool:
        try:
            TaskHeader.validate(th_dict_repr)
            header = TaskHeader.from_dict(th_dict_repr)
            if not self.verify_header_sig(header):
                raise ValueError("Invalid signature")

            if self.task_manager.is_this_my_task(header):
                return True  # Own tasks are not added to task keeper

            return self.task_keeper.add_task_header(header)

        except exceptions.TaskHeaderError as e:
            logger.warning("Wrong task header received: %s", e)
            return False
        except Exception:  # pylint: disable=broad-except
            logger.exception("Task header validation failed")
            return False

    def verify_header_sig(self, header: TaskHeader):
        _bin = header.to_binary()
        _sig = header.signature
        _key = header.task_owner.key
        return self.verify_sig(_sig, _bin, _key)

    def remove_task_header(self, task_id) -> bool:
        return self.task_keeper.remove_task_header(task_id)

    def add_task_session(self, subtask_id, session: TaskSession):
        self.task_sessions[subtask_id] = session

    def remove_task_session(self, task_session: TaskSession):
        self.remove_pending_conn(task_session.conn_id)
        self.remove_responses(task_session.conn_id)

        for tsk in list(self.task_sessions.keys()):
            if self.task_sessions[tsk] == task_session:
                del self.task_sessions[tsk]

    def set_last_message(self, type_, t, msg, address, port):
        if len(self.last_messages) >= 5:
            self.last_messages = self.last_messages[-4:]

        self.last_messages.append([type_, t, address, port, msg])

    def get_last_messages(self):
        return self.last_messages

    def get_waiting_task_result(self, subtask_id):
        return self.results_to_send.get(subtask_id, None)

    def get_node_name(self):
        return self.config_desc.node_name

    def get_key_id(self):
        return self.keys_auth.key_id

    def sign(self, data):
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        return self.keys_auth.verify(sig, data, public_key)

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
        self.last_message_time_threshold = config_desc.task_session_timeout
        self.task_manager.change_config(
            self.__get_task_manager_root(self.client.datadir),
            config_desc.use_distributed_resource_management)
        self.task_keeper.change_config(config_desc)
        return self.task_computer.change_config(
            config_desc, run_benchmarks=run_benchmarks)

    def get_task_computer_root(self):
        return os.path.join(self.client.datadir, "ComputerRes")

    def subtask_rejected(self, sender_node_id, subtask_id):
        """My (providers) results were rejected"""
        logger.debug("Subtask %r result rejected", subtask_id)
        self.task_result_sent(subtask_id)
        task_id = self.task_manager.comp_task_keeper.get_task_id_for_subtask(
            subtask_id)
        if task_id is None:
            logger.warning("Not my subtask rejected %r", subtask_id)
            return

        self.client.transaction_system.reject_income(
            sender_node_id,
            subtask_id,
        )
        self.decrease_trust_payment(task_id)
        # self.remove_task_header(task_id)
        # TODO Inform transaction system and task manager about rejected
        # subtask. Issue #2405

    def subtask_accepted(self, sender_node_id, subtask_id, accepted_ts):
        """My (providers) results were accepted"""
        logger.debug("Subtask %r result accepted", subtask_id)
        self.task_result_sent(subtask_id)
        self.client.transaction_system.accept_income(
            sender_node_id,
            subtask_id,
            accepted_ts,
        )

    def subtask_settled(self, sender_node_id, subtask_id, settled_ts):
        """My (provider's) results were accepted by the Concent"""
        logger.debug("Subtask %r settled by the Concent", subtask_id)
        self.task_result_sent(subtask_id)
        self.client.transaction_system.settle_income(
            sender_node_id, subtask_id, settled_ts)

    def subtask_failure(self, subtask_id, err):
        logger.info("Computation for task %r failed: %r.", subtask_id, err)
        node_id = self.task_manager.get_node_id_for_subtask(subtask_id)
        Trust.COMPUTED.decrease(node_id)
        self.task_manager.task_computation_failure(subtask_id, err)

    def accept_result(self, subtask_id, key_id, eth_address: str):
        mod = min(
            max(self.task_manager.get_trust_mod(subtask_id), self.min_trust),
            self.max_trust)
        Trust.COMPUTED.increase(key_id, mod)

        task_id = self.task_manager.get_task_id(subtask_id)
        value = self.task_manager.get_value(subtask_id)

        if not value:
            logger.info("Invaluable subtask: %r value: %r", subtask_id, value)
            return

        payment_processed_ts = self.client.transaction_system.add_payment_info(
            subtask_id,
            value,
            eth_address,
        )
        self.client.funds_locker.remove_subtask(task_id)
        logger.debug('Result accepted for subtask: %s Created payment ts: %r',
                     subtask_id, payment_processed_ts)
        return payment_processed_ts

    def income_listener(self, event='default', subtask_id=None, **_kwargs):
        task_id = self.task_manager.comp_task_keeper.get_task_id_for_subtask(
            subtask_id)
        if not task_id:
            return

        if event == 'confirmed':
            self.increase_trust_payment(task_id)
        elif event == 'overdue_single':
            self.decrease_trust_payment(task_id)

    def finished_task_listener(self, event='default', task_id=None, op=None,
                               **_kwargs):
        if not (event == 'task_status_updated'
                and self.client.p2pservice):
            return
        if not (op in [TaskOp.FINISHED, TaskOp.TIMEOUT]):
            return
        self.client.p2pservice.remove_task(task_id)
        self.client.funds_locker.remove_task(task_id)

    def increase_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(
            task_id)
        Trust.PAYMENT.increase(node_id, self.max_trust)

    def decrease_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(
            task_id)
        Trust.PAYMENT.decrease(node_id, self.max_trust)

    def reject_result(self, subtask_id, key_id):
        mod = min(
            max(self.task_manager.get_trust_mod(subtask_id), self.min_trust),
            self.max_trust)
        Trust.WRONG_COMPUTED.decrease(key_id, mod)

    def unpack_delta(self, dest_dir, delta, task_id):
        self.client.resource_server.unpack_delta(dest_dir, delta, task_id)

    def get_computing_trust(self, node_id):
        return self.client.get_computing_trust(node_id)

    def start_task_session(self, node_info, super_node_info, conn_id):
        args = {
            'key_id': node_info.key,
            'node_info': node_info,
            'super_node_info': super_node_info,
            'ans_conn_id': conn_id
        }
        node = node_info
        self._add_pending_request(
            TASK_CONN_TYPES['start_session'],
            node,
            prv_port=node.prv_port,
            pub_port=node.pub_port,
            args=args
        )

    def respond_to(self, key_id, session, conn_id):
        self.remove_pending_conn(conn_id)
        responses = self.response_list.get(conn_id, None)

        if responses:
            while responses:
                res = responses.popleft()
                res(session)
        else:
            session.dropped()

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

    def remove_responses(self, conn_id):
        self.response_list.pop(conn_id, None)

    def final_conn_failure(self, conn_id):
        self.remove_responses(conn_id)
        super(TaskServer, self).final_conn_failure(conn_id)

    def add_forwarded_session_request(self, key_id, conn_id):
        if self.task_computer.waiting_for_task:
            self.task_computer.wait(ttl=self.forwarded_session_request_timeout)
        self.forwarded_session_requests[key_id] = dict(
            conn_id=conn_id, time=time.time())

    def remove_forwarded_session_request(self, key_id):
        return self.forwarded_session_requests.pop(key_id, None)

    def get_min_performance_for_task(self, task: Task) -> float:
        env = self.get_environment_by_id(task.header.environment)
        return env.get_min_accepted_performance()

    def should_accept_provider(  # noqa pylint: disable=too-many-arguments,too-many-return-statements,unused-argument
            self,
            node_id,
            task_id,
            provider_perf,
            max_resource_size,
            max_memory_size,
            num_cores):

        ids = f'provider_id: {node_id}, task_id: {task_id}'

        if task_id not in self.task_manager.tasks:
            logger.info(f'Cannot find task in my tasks: {ids}')
            return False

        task = self.task_manager.tasks[task_id]
        min_accepted_perf = self.get_min_performance_for_task(task)

        if min_accepted_perf > int(provider_perf):
            logger.info(f'insufficient provider performance: {provider_perf}'
                        f' < {min_accepted_perf}; {ids}')
            return False

        if task.header.resource_size > (int(max_resource_size) * 1024):
            logger.info('insufficient provider disk size: '
                        f'{max_resource_size} KiB; {ids}')
            return False

        if task.header.estimated_memory > (int(max_memory_size) * 1024):
            logger.info('insufficient provider memory size: '
                        f'{max_memory_size} KiB; {ids}')
            return False

        allowed, reason = self.acl.is_allowed(node_id)
        if not allowed:
            logger.info(f'provider {reason}; {ids}')
            return False

        trust = self.get_computing_trust(node_id)
        if trust < self.config_desc.computing_trust:
            logger.info(f'insufficient provider trust level: {trust}; {ids}')
            return False

        if not task.header.mask.matches(decode_hex(node_id)):
            logger.info(f'network mask mismatch: {ids}')
            return False

        if task.should_accept_client(node_id) != AcceptClientVerdict.ACCEPTED:
            logger.info(f'provider {node_id} is not allowed'
                        f' for this task at this moment '
                        f'(either waiting for results or previously failed)')
            return False

        logger.debug(f'provider {node_id} can be accepted')
        return True

    def should_accept_requestor(self, node_id):
        allowed, reason = self.acl.is_allowed(node_id)
        if not allowed:
            logger.info(f'requestor {reason}; {node_id}')
            return SupportStatus.err({UnsupportReason.DENY_LIST: node_id})
        trust = self.client.get_requesting_trust(node_id)
        logger.debug("Requesting trust level: {}".format(trust))
        if trust >= self.config_desc.requesting_trust:
            return SupportStatus.ok()
        else:
            return SupportStatus.err({UnsupportReason.REQUESTOR_TRUST: trust})

    def _sync_forwarded_session_requests(self):
        now = time.time()
        for key_id, data in list(self.forwarded_session_requests.items()):
            if data:
                if now - data['time'] >= self.forwarded_session_request_timeout:
                    logger.debug('connection timeout: %s', data)
                    self.final_conn_failure(data['conn_id'])
                    self.remove_forwarded_session_request(key_id)
            else:
                self.forwarded_session_requests.pop(key_id)

    def _get_factory(self):
        return self.factory(self)

    def _listening_established(self, port, **kwargs):
        logger.debug('_listening_established(%r)', port)
        self.cur_port = port
        logger.info(" Port {} opened - listening".format(self.cur_port))
        self.node.prv_port = self.cur_port
        self.task_manager.listen_address = self.node.prv_addr
        self.task_manager.listen_port = self.cur_port
        self.task_manager.node = self.node

    def _listening_failure(self, **kwargs):
        logger.error("Listening on ports {} to {} failure".format(
            self.config_desc.start_port, self.config_desc.end_port))
        # FIXME: some graceful terminations should take place here. #1287
        # sys.exit(0)

    #############################
    #   CONNECTION REACTIONS    #
    #############################
    def __connection_for_task_request_established(
            self, session: TaskSession, conn_id, node_name, key_id, task_id,
            estimated_performance, price, max_resource_size, max_memory_size,
            num_cores):
        self.new_session_prepare(
            session=session,
            subtask_id=task_id,
            key_id=key_id,
            conn_id=conn_id,
        )
        session.send_hello()
        session.request_task(node_name, task_id, estimated_performance, price,
                             max_resource_size, max_memory_size, num_cores)

    def __connection_for_task_request_failure(
            self, conn_id, node_name, key_id, task_id, estimated_performance,
            price, max_resource_size, max_memory_size, num_cores, *args):
        def response(session):
            return self.__connection_for_task_request_established(
                session, conn_id, node_name, key_id, task_id,
                estimated_performance, price, max_resource_size,
                max_memory_size, num_cores)

        if key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_task_result_established(self, session, conn_id,
                                                 waiting_task_result):
        self.new_session_prepare(
            session=session,
            subtask_id=waiting_task_result.subtask_id,
            key_id=waiting_task_result.owner.key,
            conn_id=conn_id,
        )

        session.send_hello()
        payment_addr = self.client.transaction_system.get_payment_address()
        session.send_report_computed_task(waiting_task_result,
                                          self.node.prv_addr, self.cur_port,
                                          payment_addr, self.node)

    def __connection_for_task_result_failure(self, conn_id,
                                             waiting_task_result):
        def response(session):
            self.__connection_for_task_result_established(
                session, conn_id, waiting_task_result)

        if waiting_task_result.owner.key in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(
            waiting_task_result.owner.key, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_task_failure_established(self, session, conn_id,
                                                  key_id, subtask_id, err_msg):
        self.new_session_prepare(
            session=session,
            subtask_id=subtask_id,
            key_id=key_id,
            conn_id=conn_id,
        )
        session.send_hello()
        session.send_task_failure(subtask_id, err_msg)

    def __connection_for_task_failure_failure(self, conn_id, key_id,
                                              subtask_id, err_msg):
        def response(session):
            return self.__connection_for_task_failure_established(
                session, conn_id, key_id, subtask_id, err_msg)

        if key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_start_session_established(
            self, session, conn_id, key_id, node_info, super_node_info,
            ans_conn_id):
        self.new_session_prepare(
            session=session,
            subtask_id=None,
            key_id=key_id,
            conn_id=conn_id,
        )
        session.send_hello()
        session.send_start_session_response(ans_conn_id)

    def __connection_for_start_session_failure(
            self, conn_id, key_id, node_info, super_node_info, ans_conn_id):
        logger.info(
            "Failed to start requested task session for node {}".format(
                key_id))
        self.final_conn_failure(conn_id)
        # self.__initiate_nat_traversal(
        #     key_id, node_info, super_node_info, ans_conn_id)

    def __connection_for_task_request_final_failure(
            self, conn_id, node_name, key_id, task_id, estimated_performance,
            price, max_resource_size, max_memory_size, num_cores, *args):
        logger.info("Cannot connect to task {} owner".format(task_id))
        logger.info("Removing task {} from task list".format(task_id))

        self.task_computer.task_request_rejected(task_id, "Connection failed")
        self.task_keeper.request_failure(task_id)
        self.task_manager.comp_task_keeper.request_failure(task_id)
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_task_result_final_failure(self, conn_id,
                                                   waiting_task_result):
        logger.info("Cannot connect to task {} owner".format(
            waiting_task_result.subtask_id))

        waiting_task_result.lastSendingTrial = time.time()
        waiting_task_result.delayTime = \
            self.config_desc.max_results_sending_delay
        waiting_task_result.alreadySending = False
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_task_failure_final_failure(self, conn_id, key_id,
                                                    subtask_id, err_msg):
        logger.info("Cannot connect to task {} owner".format(subtask_id))
        self.task_computer.session_timeout()
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_start_session_final_failure(
            self, conn_id, key_id, node_info, super_node_info, ans_conn_id):
        logger.warning("Impossible to start session with {}".format(node_info))
        self.task_computer.session_timeout()
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)
        self.remove_pending_conn(ans_conn_id)
        self.remove_responses(ans_conn_id)

    def new_session_prepare(self,
                            session: TaskSession,
                            subtask_id: str,
                            key_id: str,
                            conn_id: str):
        self.remove_forwarded_session_request(key_id)
        session.task_id = subtask_id
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[subtask_id] = session

    def noop(self, *args, **kwargs):
        args_, kwargs_ = args, kwargs  # avoid params name collision in logger
        logger.debug('Noop(%r, %r)', args_, kwargs_)

    def __connection_for_task_verification_result_established(
            self,
            session: TaskSession,
            conn_id,
            extracted_package: ExtractedPackage,
            key_id):

        extra_data = extracted_package.to_extra_data()
        self.new_session_prepare(
            session=session,
            subtask_id=extra_data.get('subtask_id'),
            key_id=key_id,
            conn_id=conn_id,
        )

        session.send_hello()
        session.result_received(extra_data)

    def __connection_for_task_verification_result_failure(  # noqa pylint:disable=no-self-use
            self, conn_id, extracted_package, key_id):
        subtask_id = extracted_package.to_extra_data().get('subtask_id')
        logger.warning("Failed to establish a session to deliver "
                       "the verification result for %s to the provider %s",
                       subtask_id, key_id)

    # SYNC METHODS
    #############################
    def __remove_old_tasks(self):
        self.task_keeper.remove_old_tasks()
        self.task_manager.comp_task_keeper.remove_old_tasks()
        nodes_with_timeouts = self.task_manager.check_timeouts()
        for node_id in nodes_with_timeouts:
            Trust.COMPUTED.decrease(node_id)

    def __remove_old_sessions(self):
        cur_time = time.time()
        sessions_to_remove = []
        sessions = dict(self.task_sessions)

        for subtask_id, session in sessions.items():
            dt = cur_time - session.last_message_time
            if dt > self.last_message_time_threshold:
                sessions_to_remove.append(subtask_id)
        for subtask_id in sessions_to_remove:
            if sessions[subtask_id].task_computer is not None:
                sessions[subtask_id].task_computer.session_timeout()
            sessions[subtask_id].dropped()

    def _find_sessions(self, subtask):
        if subtask in self.task_sessions:
            return [self.task_sessions[subtask]]
        for s in set(self.task_sessions_incoming):
            logger.debug('Checking session: %r', s)
            if s.subtask_id == subtask:
                return [s]
            try:
                task_id = self.task_manager.subtask2task_mapping[subtask]
            except KeyError:
                pass
            else:
                if s.task_id == task_id:
                    return [s]
        return []

    def __send_waiting_results(self):
        for subtask_id in list(self.results_to_send.keys()):
            wtr = self.results_to_send[subtask_id]
            now = time.time()

            if not wtr.already_sending:
                if now - wtr.last_sending_trial > wtr.delay_time:
                    wtr.already_sending = True
                    wtr.last_sending_trial = now
                    session = self.task_sessions.get(subtask_id, None)
                    if session:
                        self.__connection_for_task_result_established(
                            session, session.conn_id, wtr)
                    else:
                        args = {'waiting_task_result': wtr}
                        node = wtr.owner
                        self._add_pending_request(
                            TASK_CONN_TYPES['task_result'],
                            node,
                            prv_port=node.prv_port,
                            pub_port=node.pub_port,
                            args=args
                        )

        for subtask_id in list(self.failures_to_send.keys()):
            wtf = self.failures_to_send[subtask_id]

            session = self.task_sessions.get(subtask_id, None)
            if session:
                self.__connection_for_task_failure_established(
                    session, session.conn_id, wtf.owner.key, subtask_id,
                    wtf.err_msg)
            else:
                args = {
                    'key_id': wtf.owner.key,
                    'subtask_id': wtf.subtask_id,
                    'err_msg': wtf.err_msg
                }
                node = wtf.owner
                self._add_pending_request(
                    TASK_CONN_TYPES['task_failure'],
                    node,
                    prv_port=node.prv_port,
                    pub_port=node.pub_port,
                    args=args
                )

        self.failures_to_send.clear()

    def verify_results(
            self,
            report_computed_task: message.tasks.ReportComputedTask,
            extracted_package: ExtractedPackage) -> None:

        kwargs = {
            'extracted_package': extracted_package,
            'key_id': report_computed_task.key_id,
        }

        node = p2p_node.Node.from_dict(report_computed_task.node_info)

        self._add_pending_request(
            TASK_CONN_TYPES['task_verification_result'],
            node,
            prv_port=node.prv_port,
            pub_port=node.pub_port,
            args=kwargs,
        )

    # CONFIGURATION METHODS
    #############################
    @staticmethod
    def __get_task_manager_root(datadir):
        return os.path.join(datadir, "res")

    def _set_conn_established(self):
        self.conn_established_for_type.update({
            TASK_CONN_TYPES['task_request']:
            self.__connection_for_task_request_established,
            TASK_CONN_TYPES['task_result']:
            self.__connection_for_task_result_established,
            TASK_CONN_TYPES['task_failure']:
            self.__connection_for_task_failure_established,
            TASK_CONN_TYPES['start_session']:
            self.__connection_for_start_session_established,
            TASK_CONN_TYPES['task_verification_result']:
                self.__connection_for_task_verification_result_established,
        })

    def _set_conn_failure(self):
        self.conn_failure_for_type.update({
            TASK_CONN_TYPES['task_request']:
            self.__connection_for_task_request_failure,
            TASK_CONN_TYPES['task_result']:
            self.__connection_for_task_result_failure,
            TASK_CONN_TYPES['task_failure']:
            self.__connection_for_task_failure_failure,
            TASK_CONN_TYPES['start_session']:
            self.__connection_for_start_session_failure,
            TASK_CONN_TYPES['task_verification_result']:
                self.__connection_for_task_verification_result_failure,
        })

    def _set_conn_final_failure(self):
        self.conn_final_failure_for_type.update({
            TASK_CONN_TYPES['task_request']:
            self.__connection_for_task_request_final_failure,
            TASK_CONN_TYPES['task_result']:
            self.__connection_for_task_result_final_failure,
            TASK_CONN_TYPES['task_failure']:
            self.__connection_for_task_failure_final_failure,
            TASK_CONN_TYPES['start_session']:
            self.__connection_for_start_session_final_failure,
            TASK_CONN_TYPES['task_verification_result']:
                self.__connection_for_task_verification_result_failure,
        })


# TODO: https://github.com/golemfactory/golem/issues/2633
#       and remove linter switch offs
# pylint: disable=too-many-arguments, too-many-locals
class WaitingTaskResult(object):
    def __init__(self, task_id, subtask_id, result, result_type,
                 last_sending_trial, delay_time, owner, result_path=None,
                 result_hash=None, result_secret=None, package_sha1=None,
                 result_size=None, package_path=None):

        self.task_id = task_id
        self.subtask_id = subtask_id
        self.last_sending_trial = last_sending_trial
        self.delay_time = delay_time
        self.owner = owner

        self.result = result
        self.result_type = result_type
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


# TODO: Get rid of archaic int labels and use plain strings instead. issue #2404
TASK_CONN_TYPES = {
    'task_request': 1,
    # unused: 'pay_for_task': 4,
    'task_result': 5,
    'task_failure': 6,
    'start_session': 7,
    'task_verification_result': 8,
}


class TaskListenTypes(object):
    StartSession = 1
