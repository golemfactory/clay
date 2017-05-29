import itertools
import logging
import os
import time
from collections import deque

from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcpnetwork import TCPNetwork, TCPConnectInfo, SocketAddress, MidAndFilesProtocol
from golem.network.transport.tcpserver import PendingConnectionsServer, PenConnStatus
from golem.ranking.helper.trust import Trust
from golem.task.deny import get_deny_set
from golem.task.taskbase import TaskHeader
from golem.task.taskconnectionshelper import TaskConnectionsHelper
from taskcomputer import TaskComputer
from taskkeeper import TaskHeaderKeeper
from taskmanager import TaskManager
from tasksession import TaskSession
from weakreflist.weakreflist import WeakList

logger = logging.getLogger('golem.task.taskserver')


tmp_cycler = itertools.cycle(range(550))


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
        self.task_sessions_incoming = WeakList()

        self.max_trust = 1.0
        self.min_trust = 0.0

        self.last_messages = []
        self.last_message_time_threshold = config_desc.task_session_timeout

        self.results_to_send = {}
        self.failures_to_send = {}

        self.use_ipv6 = use_ipv6

        self.forwarded_session_request_timeout = config_desc.waiting_for_task_session_timeout
        self.forwarded_session_requests = {}
        self.response_list = {}
        self.deny_set = get_deny_set(datadir=client.datadir)

        network = TCPNetwork(ProtocolFactory(MidAndFilesProtocol, self, SessionFactory(TaskSession)), use_ipv6)
        PendingConnectionsServer.__init__(self, config_desc, network)

    def key_changed(self):
        """React to the fact that key id has been changed. Inform task manager about new key """
        self.task_manager.key_id = self.keys_auth.get_key_id()

    def sync_network(self):
        self._sync_pending()
        self.__send_waiting_results()
        self.task_computer.run()
        self.task_connections_helper.sync()
        self._sync_forwarded_session_requests()
        self.__remove_old_tasks()
        # self.__remove_old_sessions()
        self._remove_old_listenings()
        if tmp_cycler.next() == 0:
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

    def send_results(self, subtask_id, task_id, result, computing_time, owner_address, owner_port, owner_key_id, owner,
                     node_name):

        if 'data' not in result or 'result_type' not in result:
            raise AttributeError("Wrong result format")

        Trust.REQUESTED.increase(owner_key_id)

        if subtask_id not in self.results_to_send:
            value = self.task_manager.comp_task_keeper.get_value(task_id, computing_time)
            if self.client.transaction_system:
                self.client.transaction_system.add_to_waiting_payments(task_id, owner_key_id, value)

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
        self.task_sessions_incoming.append(session)

    def get_tasks_headers(self):
        ths = self.task_keeper.get_all_tasks() + self.task_manager.get_tasks_headers()
        return [th.to_dict() for th in ths]

    def add_task_header(self, th_dict_repr):
        try:
            if not self.verify_header_sig(th_dict_repr):
                raise Exception("Invalid signature")

            task_id = th_dict_repr["task_id"]
            key_id = th_dict_repr["task_owner_key_id"]
            task_ids = self.task_manager.tasks.keys()
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

        for tsk in self.task_sessions.keys():
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

    def reward_for_subtask_paid(self, subtask_id):
        logger.info("Receive payment for subtask {}".format(subtask_id))
        task_id = self.task_manager.comp_task_keeper.get_task_id_for_subtask(subtask_id)
        if task_id is None:
            logger.warning("Received payment for unknown subtask {}".format(subtask_id))
            return
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(task_id)
        if node_id is None:
            logger.warning("Unknown node try to make a payment for task {}".format(task_id))
            return
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
            logger.info(u"Invaluable subtask: %r value: %r", subtask_id, value)
            return

        if not self.client.transaction_system:
            logger.info(u"Transaction system not ready. Ignoring payment for subtask: %r", subtask_id)
            return

        if not account_info.eth_account.address:
            logger.warning(u"Unknown payment address of %r (%r). Subtask: %r", account_info.node_name, account_info.addr, subtask_id)
            return

        payment = self.client.transaction_system.add_payment_info(task_id, subtask_id, value, account_info)
        logger.debug(u'Result accepted for subtask: %s Created payment: %r', subtask_id, payment)

    def increase_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(task_id)
        Trust.PAYMENT.increase(node_id, self.max_trust)

    def decrease_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(task_id)
        Trust.PAYMENT.decrease(node_id, self.max_trust)

    def pay_for_task(self, task_id, payments):
        if not self.client.transaction_system:
            return

        all_payments = {eth_account: desc.value for eth_account, desc in payments.items()}
        try:
            self.client.transaction_system.pay_for_task(task_id, all_payments)
        except Exception as err:
            # FIXME: Decide what to do when payment failed
            logger.error("Can't pay for task: {}".format(err))

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
        for key_id, data in self.forwarded_session_requests.items():
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

    def __connection_for_task_request_final_failure(self, conn_id, node_name, key_id, task_id, estimated_performance,
                                                    price, max_resource_size, max_memory_size, num_cores, *args):
        logger.warning("Cannot connect to task {} owner".format(task_id))
        logger.warning("Removing task {} from task list".format(task_id))

        self.task_computer.task_request_rejected(task_id, "Connection failed")
        self.task_keeper.request_failure(task_id)
        self.task_manager.comp_task_keeper.request_failure(task_id)
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_resource_request_final_failure(self, conn_id, key_id, subtask_id, resource_header):
        logger.warning("Cannot connect to task {} owner".format(subtask_id))
        logger.warning("Removing task {} from task list".format(subtask_id))

        self.task_computer.resource_request_rejected(subtask_id, "Connection failed")
        self.remove_task_header(subtask_id)
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_result_rejected_final_failure(self, conn_id, key_id, subtask_id):
        logger.warning("Cannot connect to deliver information about rejected result for task {}".format(subtask_id))
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_task_result_final_failure(self, conn_id, key_id, waiting_task_result):
        logger.warning("Cannot connect to task {} owner".format(waiting_task_result.subtask_id))

        waiting_task_result.lastSendingTrial = time.time()
        waiting_task_result.delayTime = self.config_desc.max_results_sending_delay
        waiting_task_result.alreadySending = False
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)

    def __connection_for_task_failure_final_failure(self, conn_id, key_id, subtask_id, err_msg):
        logger.warning("Cannot connect to task {} owner".format(subtask_id))
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

    def __connection_for_middleman_final_failure(self, *args, **kwargs):
        pass

    def __connection_for_nat_punch_final_failure(self, *args, **kwargs):
        pass

    def noop(self, *args, **kwargs):
        logger.debug('Noop(%r, %r)', args, kwargs)

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
        for subtask_id, session in self.task_sessions.iteritems():
            if cur_time - session.last_message_time > self.last_message_time_threshold:
                sessions_to_remove.append(subtask_id)
        for subtask_id in sessions_to_remove:
            if self.task_sessions[subtask_id].task_computer is not None:
                self.task_sessions[subtask_id].task_computer.session_timeout()
            self.task_sessions[subtask_id].dropped()

    def __send_waiting_results(self):
        for subtask_id in self.results_to_send.keys():
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

        for subtask_id in self.failures_to_send.keys():
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

    # CONFIGURATION METHODS
    #############################
    @staticmethod
    def __get_task_manager_root(datadir):
        return os.path.join(datadir, "res")

    def _set_conn_established(self):
        self.conn_established_for_type.update({
            TASK_CONN_TYPES['task_request']: self.__connection_for_task_request_established,
            #TASK_CONN_TYPES['resource_request']: self.__connection_for_resource_request_established,
            #TASK_CONN_TYPES['result_rejected']: self.__connection_for_result_rejected_established,
            TASK_CONN_TYPES['task_result']: self.__connection_for_task_result_established,
            TASK_CONN_TYPES['task_failure']: self.__connection_for_task_failure_established,
            TASK_CONN_TYPES['start_session']: self.__connection_for_start_session_established,
            TASK_CONN_TYPES['middleman']: self.__connection_for_middleman_established,
            TASK_CONN_TYPES['nat_punch']: self.__connection_for_nat_punch_established,
        })

    def _set_conn_failure(self):
        self.conn_failure_for_type.update({
            TASK_CONN_TYPES['task_request']: self.__connection_for_task_request_failure,
            #TASK_CONN_TYPES['resource_request']: self.__connection_for_resource_request_failure,
            #TASK_CONN_TYPES['result_rejected']: self.__connection_for_result_rejected_failure,
            TASK_CONN_TYPES['task_result']: self.__connection_for_task_result_failure,
            TASK_CONN_TYPES['task_failure']: self.__connection_for_task_failure_failure,
            TASK_CONN_TYPES['start_session']: self.__connection_for_start_session_failure,
            TASK_CONN_TYPES['middleman']: self.__connection_for_middleman_failure,
            TASK_CONN_TYPES['nat_punch']: self.__connection_for_nat_punch_failure,
        })

    def _set_conn_final_failure(self):
        self.conn_final_failure_for_type.update({
            TASK_CONN_TYPES['task_request']: self.__connection_for_task_request_final_failure,
            #TASK_CONN_TYPES['resource_request']: self.__connection_for_resource_request_final_failure,
            #TASK_CONN_TYPES['result_rejected']: self.__connection_for_result_rejected_final_failure,
            TASK_CONN_TYPES['task_result']: self.__connection_for_task_result_final_failure,
            TASK_CONN_TYPES['task_failure']: self.__connection_for_task_failure_final_failure,
            TASK_CONN_TYPES['start_session']: self.__connection_for_start_session_final_failure,
            TASK_CONN_TYPES['middleman']: self.noop,
            TASK_CONN_TYPES['nat_punch']: self.noop,
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
                 owner_address,owner_port, owner_key_id, owner):
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
    # unused: 'resource_request': 2,
    # unused: 'result_rejected': 3,
    # unused: 'pay_for_task': 4,
    'task_result': 5,
    'task_failure': 6,
    'start_session': 7,
    'middleman': 8,
    'nat_punch': 9,
}


class TaskListenTypes(object):
    StartSession = 1
