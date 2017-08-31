# -*- coding: utf-8 -*-
from collections import deque
import datetime
import itertools
import logging
import os
from pydispatch import dispatcher
import time

from golem import model
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcpnetwork import TCPNetwork, TCPConnectInfo, SocketAddress, MidAndFilesProtocol
from golem.network.transport.tcpserver import PendingConnectionsServer, PenConnStatus
from golem.ranking.helper.trust import Trust
from golem.task.deny import get_deny_set
from golem.task.taskbase import TaskHeader
from golem.task.taskconnectionshelper import TaskConnectionsHelper
from .taskcomputer import TaskComputer
from .taskkeeper import TaskHeaderKeeper
from .taskmanager import TaskManager
from .tasksession import TaskSession
import weakref

logger = logging.getLogger('golem.task.taskserver')


tmp_cycler = itertools.cycle(list(range(550)))


class TaskServer(PendingConnectionsServer):
    def __init__(self, node, config_desc, keys_auth, client,
                 use_ipv6=False, use_docker_machine_manager=True):
        self.client = client
        self.keys_auth = keys_auth
        self.config_desc = config_desc

        self.node = node
        self.task_keeper = TaskHeaderKeeper(client.environments_manager, min_price=config_desc.min_price)
        self.task_manager = TaskManager(config_desc.node_name, self.node, self.keys_auth,
                                        root_path=TaskServer.__get_task_manager_root(client.datadir),
                                        use_distributed_resources=config_desc.use_distributed_resource_management,
                                        tasks_dir=os.path.join(client.datadir, 'tasks'))
        self.task_computer = TaskComputer(config_desc.node_name, task_server=self,
                                          use_docker_machine_manager=use_docker_machine_manager)
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
        self.payments_to_send = set()
        self.payment_requests_to_send = set()

        self.use_ipv6 = use_ipv6

        self.forwarded_session_request_timeout = config_desc.waiting_for_task_session_timeout
        self.forwarded_session_requests = {}
        self.response_list = {}
        self.deny_set = get_deny_set(datadir=client.datadir)

        network = TCPNetwork(ProtocolFactory(MidAndFilesProtocol, self, SessionFactory(TaskSession)), use_ipv6)
        PendingConnectionsServer.__init__(self, config_desc, network)
        dispatcher.connect(self.paymentprocessor_listener, signal="golem.paymentprocessor")
        dispatcher.connect(self.transactions_listener, signal="golem.transactions")

    def paymentprocessor_listener(self, sender, signal, event='default', **kwargs):
        if event != 'payment.confirmed':
            return
        payment = kwargs.pop('payment')
        logging.debug('Notified about payment.confirmed: %r', payment)
        self.payments_to_send.add(payment)

    def transactions_listener(self, sender, signal, event='default', **kwargs):
        if event != 'expected_income':
            return
        expected_income = kwargs.pop('expected_income')
        logger.debug('REQUESTS_TO_SEND: expected_income')
        self.payment_requests_to_send.add(expected_income)

    def key_changed(self):
        """React to the fact that key id has been changed. Inform task manager about new key """
        self.task_manager.key_id = self.keys_auth.get_key_id()

    def sync_network(self):
        self._sync_pending()
        self.__send_waiting_results()
        self.send_waiting_payments()
        self.send_waiting_payment_requests()
        self.task_computer.run()
        self.task_connections_helper.sync()
        self._sync_forwarded_session_requests()
        self.__remove_old_tasks()
        self.__remove_old_sessions()
        self._remove_old_listenings()
        if next(tmp_cycler) == 0:
            logger.debug('TASK SERVER TASKS DUMP: %r', self.task_manager.tasks)
            logger.debug('TASK SERVER TASKS STATES: %r', self.task_manager.tasks_states)

    def get_environment_by_id(self, env_id):
        return self.task_keeper.environments_manager.get_environment_by_id(env_id)

    # This method chooses random task from the network to compute on our machine
    def request_task(self):
        theader = self.task_keeper.get_task()
        if theader is None:
            return None
        try:
            env = self.get_environment_by_id(theader.environment)
            if env is not None:
                performance = env.get_performance(self.config_desc)
            else:
                performance = 0.0
            if self.should_accept_requestor(theader.task_owner_key_id):
                self.task_manager.add_comp_task_request(theader, self.config_desc.min_price)
                args = {
                    'node_name': self.config_desc.node_name,
                    'key_id': theader.task_owner_key_id,
                    'task_id': theader.task_id,
                    'estimated_performance': performance,
                    'price': self.config_desc.min_price,
                    'max_resource_size': self.config_desc.max_resource_size,
                    'max_memory_size': self.config_desc.max_memory_size,
                    'num_cores': self.config_desc.num_cores
                }
                self._add_pending_request(TASK_CONN_TYPES['task_request'], theader.task_owner, theader.task_owner_port, theader.task_owner_key_id, args)

                return theader.task_id
        except Exception as err:
            logger.warning("Cannot send request for task: {}".format(err))
            self.task_keeper.remove_task_header(theader.task_id)

    def request_resource(self, subtask_id, resource_header, address, port, key_id, task_owner):
        if subtask_id in self.task_sessions:
            session = self.task_sessions[subtask_id]
            session.request_resource(subtask_id, resource_header)
        else:
            logger.error("Cannot map subtask_id {} to session".format(subtask_id))
        return subtask_id

    def pull_resources(self, task_id, resources, client_options=None):
        self.client.pull_resources(task_id, resources, client_options=client_options)

    def send_results(self, subtask_id, task_id, result, computing_time,
                     owner_address, owner_port, owner_key_id, owner,
                     node_name):

        if 'data' not in result or 'result_type' not in result:
            raise AttributeError("Wrong result format")

        Trust.REQUESTED.increase(owner_key_id)

        if subtask_id not in self.results_to_send:
            value = self.task_manager.comp_task_keeper.get_value(
                task_id,
                computing_time
            )
            if self.client.transaction_system:
                self.client.transaction_system.incomes_keeper.expect(
                    sender_node_id=owner_key_id,
                    p2p_node=owner,
                    task_id=task_id,
                    subtask_id=subtask_id,
                    value=value,
                )

            delay_time = 0.0
            last_sending_trial = 0

            self.results_to_send[subtask_id] = WaitingTaskResult(task_id, subtask_id, result['data'],
                                                                 result['result_type'], computing_time,
                                                                 last_sending_trial, delay_time,
                                                                 owner_address, owner_port, owner_key_id, owner)
        else:
            raise RuntimeError("Incorrect subtask_id: {}".format(subtask_id))

        return True

    def send_task_failed(self, subtask_id, task_id, err_msg, owner_address, owner_port, owner_key_id, owner, node_name):
        Trust.REQUESTED.decrease(owner_key_id)
        if subtask_id not in self.failures_to_send:
            self.failures_to_send[subtask_id] = WaitingTaskFailure(task_id, subtask_id, err_msg,
                                                                   owner_address, owner_port, owner_key_id, owner)

    def new_connection(self, session):
        if self.active:
            self.task_sessions_incoming.add(session)
        else:
            session.disconnect(TaskSession.DCRNoMoreMessages)

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

    def get_tasks_headers(self):
        ths = self.task_keeper.get_all_tasks() + \
              self.task_manager.get_tasks_headers()
        return ths #[th.to_dict() for th in ths]

    def add_task_header(self, th_dict_repr):
        try:
            if not self.verify_header_sig(th_dict_repr):
                raise Exception("Invalid signature")

            task_id = th_dict_repr["task_id"]
            key_id = th_dict_repr["task_owner_key_id"]
            task_ids = list(self.task_manager.tasks.keys())
            new_sig = True

            if task_id in self.task_keeper.task_headers:
                header = self.task_keeper.task_headers[task_id]
                new_sig = th_dict_repr["signature"] != header.signature

            if task_id not in task_ids and key_id != self.node.key and new_sig:
                self.task_keeper.add_task_header(th_dict_repr)

            return True
        except Exception as err:
            logger.warning("Wrong task header received {}".format(err))
            return False

    def verify_header_sig(self, th_dict_repr):
        _bin = TaskHeader.dict_to_binary(th_dict_repr)
        _sig = th_dict_repr["signature"]
        _key = th_dict_repr["task_owner_key_id"]
        return self.verify_sig(_sig, _bin, _key)

    def remove_task_header(self, task_id):
        self.task_keeper.remove_task_header(task_id)

    def add_task_session(self, subtask_id, session):
        self.task_sessions[subtask_id] = session

    def remove_task_session(self, task_session):
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
        return self.keys_auth.get_key_id()

    def encrypt(self, message, public_key):
        if public_key == 0:
            return message
        return self.keys_auth.encrypt(message, public_key)

    def decrypt(self, message):
        return self.keys_auth.decrypt(message)

    def sign(self, data):
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        return self.keys_auth.verify(sig, data, public_key)

    def get_resource_addr(self):
        return self.client.node.prv_addr

    def get_resource_port(self):
        return self.client.resource_port

    def get_subtask_ttl(self, task_id):
        return self.task_manager.comp_task_keeper.get_subtask_ttl(task_id)

    def add_resource_peer(self, node_name, addr, port, key_id, node_info):
        self.client.add_resource_peer(node_name, addr, port, key_id, node_info)

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
        self.task_manager.change_config(self.__get_task_manager_root(self.client.datadir),
                                        config_desc.use_distributed_resource_management)
        self.task_computer.change_config(config_desc, run_benchmarks=run_benchmarks)
        self.task_keeper.change_config(config_desc)

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout):
        self.task_manager.change_timeouts(task_id, full_task_timeout, subtask_timeout)

    def get_task_computer_root(self):
        return os.path.join(self.client.datadir, "ComputerRes")

    def subtask_rejected(self, subtask_id):
        logger.debug("Subtask {} result rejected".format(subtask_id))
        self.task_result_sent(subtask_id)
        task_id = self.task_manager.comp_task_keeper.get_task_id_for_subtask(subtask_id)
        if task_id is not None:
            self.decrease_trust_payment(task_id)
            # self.remove_task_header(task_id)
            # TODO Inform transaction system and task manager about failed payment
        else:
            logger.warning("Not my subtask rejected {}".format(subtask_id))

    def reward_for_subtask_paid(self, subtask_id, reward, transaction_id,
                                block_number):
        logger.info(
            "Received payment for subtask %r (val:%r, tid:%r, bn:%r)",
            subtask_id,
            reward,
            transaction_id,
            block_number
        )
        try:
            expected_income = model.ExpectedIncome.get(subtask=subtask_id)
        except model.ExpectedIncome.DoesNotExist:
            logger.warning(
                'Received unexpected payment for subtask %r'
                '(val:%rGNT, tid: %r, bn:%r)',
                subtask_id,
                reward,
                transaction_id,
                block_number
            )
            return
        if expected_income.value != reward:
            logger.error(
                "Reward mismatch for subtask: %r. expected: %r got: %r",
                subtask_id,
                expected_income.value,
                reward
            )
            return
        task_id = expected_income.task
        node_id = expected_income.sender_node
        self.client.transaction_system.incomes_keeper.received(
            sender_node_id=node_id,
            task_id=task_id,
            subtask_id=subtask_id,
            transaction_id=transaction_id,
            block_number=block_number,
            value=reward,
        )
        Trust.PAYMENT.increase(node_id, self.max_trust)

    def subtask_accepted(self, subtask_id, reward):
        logger.debug("Subtask {} result accepted".format(subtask_id))
        self.task_result_sent(subtask_id)

    def subtask_failure(self, subtask_id, err):
        logger.info("Computation for task {} failed: {}.".format(subtask_id, err))
        node_id = self.task_manager.get_node_id_for_subtask(subtask_id)
        Trust.COMPUTED.decrease(node_id)
        self.task_manager.task_computation_failure(subtask_id, err)

    def accept_result(self, subtask_id, account_info):
        mod = min(max(self.task_manager.get_trust_mod(subtask_id), self.min_trust), self.max_trust)
        Trust.COMPUTED.increase(account_info.key_id, mod)

        task_id = self.task_manager.get_task_id(subtask_id)
        value = self.task_manager.get_value(subtask_id)
        if not value:
            logger.info("Invaluable subtask: %r value: %r", subtask_id, value)
            return

        if not self.client.transaction_system:
            logger.info("Transaction system not ready. Ignoring payment for subtask: %r", subtask_id)
            return

        if not account_info.eth_account.address:
            logger.warning("Unknown payment address of %r (%r). Subtask: %r", account_info.node_name, account_info.addr, subtask_id)
            return

        payment = self.client.transaction_system.add_payment_info(task_id, subtask_id, value, account_info)
        logger.debug('Result accepted for subtask: %s Created payment: %r', subtask_id, payment)

    def increase_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(task_id)
        Trust.PAYMENT.increase(node_id, self.max_trust)

    def decrease_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(task_id)
        Trust.PAYMENT.decrease(node_id, self.max_trust)

    def reject_result(self, subtask_id, account_info):
        mod = min(max(self.task_manager.get_trust_mod(subtask_id), self.min_trust), self.max_trust)
        Trust.WRONG_COMPUTED.decrease(account_info.key_id, mod)

    def unpack_delta(self, dest_dir, delta, task_id):
        self.client.resource_server.unpack_delta(dest_dir, delta, task_id)

    def get_computing_trust(self, node_id):
        return self.client.get_computing_trust(node_id)

    def start_task_session(self, node_info, super_node_info, conn_id):
        args = {'key_id': node_info.key, 'node_info': node_info, 'super_node_info': super_node_info,
                'ans_conn_id': conn_id}
        self._add_pending_request(TASK_CONN_TYPES['start_session'], node_info, node_info.prv_port, node_info.key, args)

    def respond_to(self, key_id, session, conn_id):
        self.remove_pending_conn(conn_id)
        responses = self.response_list.get(conn_id, None)

        if responses:
            while responses:
                res = responses.popleft()
                res(session)
        else:
            session.dropped()

    def respond_to_middleman(self, key_id, session, conn_id, dest_key_id):
        if conn_id in self.response_list:
            self.respond_to(dest_key_id, session, conn_id)
        else:
            logger.warning("No response for {}".format(dest_key_id))
            session.dropped()

    def be_a_middleman(self, key_id, open_session, conn_id, asking_node, dest_node, ask_conn_id):
        key_id = asking_node.key
        response = lambda session: self.__asking_node_for_middleman_connection_established(session, conn_id, key_id,
                                                                                           open_session, asking_node,
                                                                                           dest_node, ask_conn_id)
        if key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)
        open_session.is_middleman = True

    def wait_for_nat_traverse(self, port, session):
        session.close_now()
        args = {'super_node': session.extra_data['super_node'],
                'asking_node': session.extra_data['asking_node'],
                'dest_node': session.extra_data['dest_node'],
                'ask_conn_id': session.extra_data['ans_conn_id']}
        self._add_pending_listening(TaskListenTypes.StartSession, port, args)

    def organize_nat_punch(self, addr, port, client_key_id, asking_node, dest_node, ans_conn_id):
        self.client.inform_about_task_nat_hole(asking_node.key, client_key_id, addr, port, ans_conn_id)

    def traverse_nat(self, key_id, addr, port, conn_id, super_key_id):
        connect_info = TCPConnectInfo([SocketAddress(addr, port)], self.__connection_for_traverse_nat_established,
                                      self.__connection_for_traverse_nat_failure)
        self.network.connect(connect_info, client_key_id=key_id, conn_id=conn_id, super_key_id=super_key_id)

    def traverse_nat_failure(self, conn_id):
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.failure(conn_id, *pc.args)

    def get_socket_addresses(self, node_info, port, key_id):
        if self.client.get_suggested_conn_reverse(key_id):
            return []
        socket_addresses = PendingConnectionsServer.get_socket_addresses(self, node_info, port, key_id)
        addr = self.client.get_suggested_addr(key_id)
        if addr:
            socket_addresses = [SocketAddress(addr, port)] + socket_addresses
        return socket_addresses

    def quit(self):
        self.task_computer.quit()

    def receive_subtask_computation_time(self, subtask_id, computation_time):
        self.task_manager.set_computation_time(subtask_id, computation_time)

    def remove_responses(self, conn_id):
        self.response_list.pop(conn_id, None)

    def final_conn_failure(self, conn_id):
        self.remove_responses(conn_id)
        super(TaskServer, self).final_conn_failure(conn_id)

    # TODO: extend to multiple sessions
    def add_forwarded_session_request(self, key_id, conn_id):
        if self.task_computer.waiting_for_task:
            self.task_computer.wait(ttl=self.forwarded_session_request_timeout)
        self.forwarded_session_requests[key_id] = dict(
            conn_id=conn_id,
            time=time.time()
        )

    def remove_forwarded_session_request(self, key_id):
        return self.forwarded_session_requests.pop(key_id, None)

    def should_accept_provider(self, node_id):
        if node_id in self.deny_set:
            return False
        trust = self.get_computing_trust(node_id)
        logger.debug("Computing trust level: {}".format(trust))
        return trust >= self.config_desc.computing_trust

    def should_accept_requestor(self, node_id):
        if node_id in self.deny_set:
            return False
        trust = self.client.get_requesting_trust(node_id)
        logger.debug("Requesting trust level: {}".format(trust))
        return trust >= self.config_desc.requesting_trust

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
        logger.error("Listening on ports {} to {} failure".format(self.config_desc.start_port,
                                                                  self.config_desc.end_port))
        # FIXME: some graceful terminations should take place here
        # sys.exit(0)

    def _listening_for_start_session_established(self, port, listen_id, super_node, asking_node, dest_node,
                                                 ask_conn_id):
        logger.debug("_listening_for_start_session_established()")
        logger.debug("Listening on port {}".format(port))
        listening = self.open_listenings.get(listen_id)
        if listening:
            self.listening.time = time.time()
            self.listening.listening_port = port
        else:
            logger.warning("Listening {} not in open listenings list".format(listen_id))

    def _listening_for_start_session_failure(self, listen_id, super_node, asking_node, dest_node, ask_conn_id):
        if listen_id in self.open_listenings:
            del self.open_listenings['listen_id']

        self.__connection_for_nat_punch_failure(listen_id, super_node, asking_node, dest_node, ask_conn_id)

    #############################
    #   CONNECTION REACTIONS    #
    #############################
    def __connection_for_task_request_established(self, session, conn_id, node_name, key_id, task_id,
                                                  estimated_performance, price, max_resource_size, max_memory_size,
                                                  num_cores):
        self.remove_forwarded_session_request(key_id)
        session.task_id = task_id
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[task_id] = session
        session.send_hello()
        session.request_task(node_name, task_id, estimated_performance, price, max_resource_size, max_memory_size, num_cores)

    def __connection_for_task_request_failure(self, conn_id, node_name, key_id, task_id, estimated_performance, price,
                                              max_resource_size, max_memory_size, num_cores, *args):

        response = lambda session: self.__connection_for_task_request_established(session, conn_id, node_name, key_id,
                                                                                  task_id, estimated_performance, price,
                                                                                  max_resource_size, max_memory_size,
                                                                                  num_cores)
        if key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_task_result_established(self, session, conn_id, waiting_task_result):
        self.remove_forwarded_session_request(waiting_task_result.owner_key_id)
        session.key_id = waiting_task_result.owner_key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[waiting_task_result.subtask_id] = session

        session.send_hello()
        payment_addr = (self.client.transaction_system.get_payment_address()
                        if self.client.transaction_system else None)
        session.send_report_computed_task(waiting_task_result, self.node.prv_addr, self.cur_port,
                                          payment_addr,
                                          self.node)

    def __connection_for_task_result_failure(self, conn_id, waiting_task_result):

        def response(session):
            self.__connection_for_task_result_established(session, conn_id, waiting_task_result)

        if waiting_task_result.owner_key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(waiting_task_result.owner_key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_task_failure_established(self, session, conn_id, key_id, subtask_id, err_msg):
        self.remove_forwarded_session_request(key_id)
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[subtask_id] = session
        session.send_hello()
        session.send_task_failure(subtask_id, err_msg)

    def __connection_for_task_failure_failure(self, conn_id, key_id, subtask_id, err_msg):

        response = lambda session: self.__connection_for_task_failure_established(session, conn_id, key_id, subtask_id,
                                                                                  err_msg)

        if key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_resource_request_established(self, session, conn_id, key_id, subtask_id, resource_header):

        session.key_id = key_id
        session.task_id = subtask_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[subtask_id] = session
        session.send_hello()
        session.request_resource(subtask_id, resource_header)

    def __connection_for_resource_request_failure(self, conn_id, key_id, subtask_id, resource_header):

        response = lambda session: self.__connection_for_resource_request_established(session, conn_id, key_id,
                                                                                      subtask_id, resource_header)
        if key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_result_rejected_established(self, session, conn_id, key_id, subtask_id):
        self.remove_forwarded_session_request(key_id)
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_result_rejected(subtask_id)

    def __connection_for_result_rejected_failure(self, conn_id, key_id, subtask_id):

        response = lambda session: self.__connection_for_result_rejected_established(session, conn_id, key_id,
                                                                                     subtask_id)
        if key_id in self.response_list:
            self.response_list[conn_id].append(response)
        else:
            self.response_list[conn_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_start_session_established(self, session, conn_id, key_id, node_info, super_node_info,
                                                   ans_conn_id):
        self.remove_forwarded_session_request(key_id)
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_start_session_response(ans_conn_id)

    def __connection_for_start_session_failure(self, conn_id, key_id, node_info, super_node_info, ans_conn_id):
        logger.info("Failed to start requested task session for node {}".format(key_id))
        self.final_conn_failure(conn_id)
        # self.__initiate_nat_traversal(key_id, node_info, super_node_info, ans_conn_id)

    def __initiate_nat_traversal(self, key_id, node_info, super_node_info, ans_conn_id):
        if super_node_info is None:
            logger.info("Permanently can't connect to node {}".format(key_id))
            return

        if self.node.nat_type in TaskServer.supported_nat_types:
            args = {
                'super_node': super_node_info,
                'asking_node': node_info,
                'dest_node': self.node,
                'ans_conn_id': ans_conn_id
            }
            self._add_pending_request(TASK_CONN_TYPES['nat_punch'], super_node_info, super_node_info.prv_port,
                                      super_node_info.key, args)
        else:
            args = {
                'key_id': super_node_info.key,
                'asking_node_info': node_info,
                'self_node_info': self.node,
                'ans_conn_id': ans_conn_id
            }
            self._add_pending_request(TASK_CONN_TYPES['middleman'], super_node_info, super_node_info.prv_port,
                                      super_node_info.key, args)

    def __connection_for_nat_punch_established(self, session, conn_id, super_node, asking_node, dest_node, ans_conn_id):
        session.key_id = super_node.key
        session.conn_id = conn_id
        session.extra_data = {'super_node': super_node, 'asking_node': asking_node, 'dest_node': dest_node,
                              'ans_conn_id': ans_conn_id}
        session.send_hello()
        session.send_nat_punch(asking_node, dest_node, ans_conn_id)

    def __connection_for_nat_punch_failure(self, conn_id, super_node, asking_node, dest_node, ans_conn_id):
        self.final_conn_failure(conn_id)
        args = {
            'key_id': super_node.key,
            'asking_node_info': asking_node,
            'self_node_info': dest_node,
            'ans_conn_id': ans_conn_id
        }
        self._add_pending_request(TASK_CONN_TYPES['middleman'], super_node, super_node.prv_port,
                                  super_node.key, args)

    def __connection_for_traverse_nat_established(self, session, client_key_id, conn_id, super_key_id):
        self.respond_to(client_key_id, session, conn_id)  # FIXME

    def __connection_for_traverse_nat_failure(self, client_key_id, conn_id, super_key_id):
        logger.error("Connection for traverse nat failure")
        self.client.inform_about_nat_traverse_failure(super_key_id, client_key_id, conn_id)

    def __connection_for_middleman_established(self, session, conn_id, key_id, asking_node_info, self_node_info,
                                               ans_conn_id):
        session.key_id = key_id
        session.conn_id = conn_id
        session.send_hello()
        session.send_middleman(asking_node_info, self_node_info, ans_conn_id)

    def __connection_for_middleman_failure(self, conn_id, key_id, asking_node_info, self_node_info, ans_conn_id):
        self.final_conn_failure(conn_id)
        logger.info("Permanently can't connect to node {}".format(key_id))
        return

    def __asking_node_for_middleman_connection_established(self, session, conn_id, key_id, open_session, asking_node,
                                                           dest_node, ans_conn_id):
        session.key_id = key_id
        session.conn_id = conn_id
        session.send_hello()
        session.send_join_middleman_conn(key_id, ans_conn_id, dest_node.key)
        session.open_session = open_session
        open_session.open_session = session

    def __connection_for_task_request_final_failure(self, conn_id, node_name,
                                                    key_id, task_id,
                                                    estimated_performance,
                                                    price, max_resource_size,
                                                    max_memory_size, num_cores,
                                                    *args):
        logger.info("Cannot connect to task {} owner".format(task_id))
        logger.info("Removing task {} from task list".format(task_id))

        self.task_computer.task_request_rejected(task_id, "Connection failed")
        self.task_keeper.request_failure(task_id)
        self.task_manager.comp_task_keeper.request_failure(task_id)
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_resource_request_final_failure(self, conn_id, key_id,
                                                        subtask_id,
                                                        resource_header):
        logger.info("Cannot connect to task {} owner".format(subtask_id))
        logger.info("Removing task {} from task list".format(subtask_id))

        self.task_computer.resource_request_rejected(subtask_id,
                                                     "Connection failed")
        self.remove_task_header(subtask_id)
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_result_rejected_final_failure(self, conn_id, key_id,
                                                       subtask_id):
        logger.info("Cannot connect to deliver information about rejected "
                    "result for task {}".format(subtask_id))
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_task_result_final_failure(self, conn_id,
                                                   waiting_task_result):
        logger.info("Cannot connect to task {} owner".format(
            waiting_task_result.subtask_id))

        waiting_task_result.lastSendingTrial = time.time()
        waiting_task_result.delayTime = self.config_desc.max_results_sending_delay
        waiting_task_result.alreadySending = False
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_task_failure_final_failure(self, conn_id, key_id,
                                                    subtask_id, err_msg):
        logger.info("Cannot connect to task {} owner".format(subtask_id))
        self.task_computer.session_timeout()
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_start_session_final_failure(self, conn_id, key_id, node_info, super_node_info, ans_conn_id):
        logger.warning("Impossible to start session with {}".format(node_info))
        self.task_computer.session_timeout()
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)
        self.remove_pending_conn(ans_conn_id)
        self.remove_responses(ans_conn_id)

    def new_session_prepare(self, session, subtask_id, key_id, conn_id):
        session.task_id = subtask_id
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[subtask_id] = session

    def connection_for_payment_established(self, session, conn_id, obj):
        # obj - Payment
        logger.debug('connection_for_payment_established(%r)', obj)

        self.new_session_prepare(
            session=session,
            subtask_id=obj.subtask,
            key_id=obj.get_sender_node().key,
            conn_id=conn_id
        )
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.inform_worker_about_payment(obj)

    def connection_for_payment_request_established(self, session, conn_id, obj):
        # obj - ExpectedIncome
        logger.debug('connection_for_payment_request_established(%r)', obj)

        self.new_session_prepare(
            session=session,
            subtask_id=obj.subtask,
            key_id=obj.get_sender_node().key,
            conn_id=conn_id
        )
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.request_payment(obj)

    def noop(self, *args, **kwargs):
        args_, kwargs_ = args, kwargs  # avoid params name collision in logger
        logger.debug('Noop(%r, %r)', args_, kwargs_)

    # SYNC METHODS
    #############################
    def __remove_old_tasks(self):
        self.task_keeper.remove_old_tasks()
        nodes_with_timeouts = self.task_manager.check_timeouts()
        for node_id in nodes_with_timeouts:
            Trust.COMPUTED.decrease(node_id)

    def __remove_old_sessions(self):
        cur_time = time.time()
        sessions_to_remove = []
        for subtask_id, session in self.task_sessions.items():
            if cur_time - session.last_message_time > self.last_message_time_threshold:
                sessions_to_remove.append(subtask_id)
        for subtask_id in sessions_to_remove:
            if self.task_sessions[subtask_id].task_computer is not None:
                self.task_sessions[subtask_id].task_computer.session_timeout()
            self.task_sessions[subtask_id].dropped()

    def _find_sessions(self, subtask):
        if subtask in self.task_sessions:
            return [self.task_sessions[subtask]]
        for s in self.task_sessions_incoming:
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

    def _send_waiting(self, elems_set, subtask_id_getter, req_type, session_cbk, p2p_node_getter):
        for elem in elems_set.copy():
            if hasattr(elem, '_last_try') and (datetime.datetime.now() - elem._last_try) < datetime.timedelta(seconds=30):
                continue
            logger.debug('_send_waiting(): %r', elem)
            elem._last_try = datetime.datetime.now()
            subtask_id = subtask_id_getter(elem)
            sessions = self._find_sessions(subtask_id)

            logger.debug('_send_waiting() len(sessions):%r', len(sessions))
            if not sessions:
                p2p_node = p2p_node_getter(elem)
                if p2p_node is None:
                    logger.debug('Empty node info in %r', elem)
                    elems_set.remove(elem)
                    continue
                self._add_pending_request(
                    req_type=req_type,
                    task_owner=p2p_node,
                    port=p2p_node.prv_port,
                    key_id=None,
                    args={'obj': elem}
                )
                return
            for session in sessions:
                if isinstance(session, weakref.ref):
                    session = session()
                    if session is None:
                        continue
                session_cbk(session, elem)
            elems_set.remove(elem)

    def send_waiting_payment_requests(self):
        self._send_waiting(
            elems_set=self.payment_requests_to_send,
            subtask_id_getter=lambda expected_income: expected_income.subtask,
            p2p_node_getter=lambda expected_income: expected_income.get_sender_node(),
            req_type=TASK_CONN_TYPES['payment_request'],
            session_cbk=lambda session, expected_income: session.request_payment(expected_income)
        )

    def send_waiting_payments(self):
        self._send_waiting(
            elems_set=self.payments_to_send,
            subtask_id_getter=lambda payment: payment.subtask,
            p2p_node_getter=lambda payment: payment.get_sender_node(),
            req_type=TASK_CONN_TYPES['payment'],
            session_cbk=lambda session, payment: session.inform_worker_about_payment(payment)
        )

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
                        self.__connection_for_task_result_established(session, session.conn_id, wtr)
                    else:
                        args = {'waiting_task_result': wtr}
                        self._add_pending_request(TASK_CONN_TYPES['task_result'],
                                                  wtr.owner, wtr.owner_port,
                                                  wtr.owner_key_id, args)

        for subtask_id in list(self.failures_to_send.keys()):
            wtf = self.failures_to_send[subtask_id]

            session = self.task_sessions.get(subtask_id, None)
            if session:
                self.__connection_for_task_failure_established(session, session.conn_id,
                                                               wtf.owner_key_id, subtask_id,
                                                               wtf.err_msg)
            else:
                args = {'key_id': wtf.owner_key_id, 'subtask_id': wtf.subtask_id, 'err_msg': wtf.err_msg}
                self._add_pending_request(TASK_CONN_TYPES['task_failure'],
                                          wtf.owner, wtf.owner_port,
                                          wtf.owner_key_id, args)

        self.failures_to_send.clear()

    def __connection_for_payment_failure(self, *args, **kwargs):
        if 'conn_id' in kwargs:
            self.final_conn_failure(kwargs['conn_id'])
        else:
            logger.warning("There is no connection id for handle failure")

    def __connection_for_payment_request_failure(self, *args, **kwargs):
        if 'conn_id' in kwargs:
            self.final_conn_failure(kwargs['conn_id'])
        else:
            logger.warning("There is no connection id for handle failure")

    # CONFIGURATION METHODS
    #############################
    @staticmethod
    def __get_task_manager_root(datadir):
        return os.path.join(datadir, "res")

    def _set_conn_established(self):
        self.conn_established_for_type.update({
            TASK_CONN_TYPES['task_request']: self.__connection_for_task_request_established,
            TASK_CONN_TYPES['task_result']: self.__connection_for_task_result_established,
            TASK_CONN_TYPES['task_failure']: self.__connection_for_task_failure_established,
            TASK_CONN_TYPES['start_session']: self.__connection_for_start_session_established,
            TASK_CONN_TYPES['middleman']: self.__connection_for_middleman_established,
            TASK_CONN_TYPES['nat_punch']: self.__connection_for_nat_punch_established,
            TASK_CONN_TYPES['payment']: self.connection_for_payment_established,
            TASK_CONN_TYPES['payment_request']: self.connection_for_payment_request_established,
        })

    def _set_conn_failure(self):
        self.conn_failure_for_type.update({
            TASK_CONN_TYPES['task_request']: self.__connection_for_task_request_failure,
            TASK_CONN_TYPES['task_result']: self.__connection_for_task_result_failure,
            TASK_CONN_TYPES['task_failure']: self.__connection_for_task_failure_failure,
            TASK_CONN_TYPES['start_session']: self.__connection_for_start_session_failure,
            TASK_CONN_TYPES['middleman']: self.__connection_for_middleman_failure,
            TASK_CONN_TYPES['nat_punch']: self.__connection_for_nat_punch_failure,
            TASK_CONN_TYPES['payment']:
                self.__connection_for_payment_failure,
            TASK_CONN_TYPES['payment_request']:
                self.__connection_for_payment_request_failure,
        })

    def _set_conn_final_failure(self):
        self.conn_final_failure_for_type.update({
            TASK_CONN_TYPES['task_request']: self.__connection_for_task_request_final_failure,
            TASK_CONN_TYPES['task_result']: self.__connection_for_task_result_final_failure,
            TASK_CONN_TYPES['task_failure']: self.__connection_for_task_failure_final_failure,
            TASK_CONN_TYPES['start_session']: self.__connection_for_start_session_final_failure,
            TASK_CONN_TYPES['middleman']: self.noop,
            TASK_CONN_TYPES['nat_punch']: self.noop,
            TASK_CONN_TYPES['payment']:self.noop,
            TASK_CONN_TYPES['payment_request']: self.noop,
        })

    def _set_listen_established(self):
        self.listen_established_for_type.update({
            TaskListenTypes.StartSession: self._listening_for_start_session_established
        })

    def _set_listen_failure(self):
        self.listen_failure_for_type.update({
            TaskListenTypes.StartSession: self._listening_for_start_session_failure
        })


class WaitingTaskResult(object):
    def __init__(self, task_id, subtask_id, result, result_type, computing_time, last_sending_trial, delay_time,
                 owner_address, owner_port, owner_key_id, owner):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.result = result
        self.result_type = result_type
        self.computing_time = computing_time
        self.last_sending_trial = last_sending_trial
        self.delay_time = delay_time
        self.owner_address = owner_address
        self.owner_port = owner_port
        self.owner_key_id = owner_key_id
        self.owner = owner
        self.already_sending = False


class WaitingTaskFailure(object):
    def __init__(self, task_id, subtask_id, err_msg, owner_address, owner_port, owner_key_id, owner):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.owner_address = owner_address
        self.owner_port = owner_port
        self.owner_key_id = owner_key_id
        self.owner = owner
        self.err_msg = err_msg


# TODO: Get rid of archaic int labels and use plain strings instead.
TASK_CONN_TYPES = {
    'task_request': 1,
    # unused: 'pay_for_task': 4,
    'task_result': 5,
    'task_failure': 6,
    'start_session': 7,
    'middleman': 8,
    'nat_punch': 9,
    'payment': 10,
    'payment_request': 11,
}


class TaskListenTypes(object):
    StartSession = 1
