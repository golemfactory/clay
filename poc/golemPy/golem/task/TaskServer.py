import time
import os
import logging

from collections import deque

from TaskManager import TaskManager
from TaskComputer import TaskComputer
from task_session import TaskSession
from TaskKeeper import TaskKeeper

from golem.ranking.Ranking import RankingStats
from golem.network.transport.tcp_network import TCPNetwork, TCPConnectInfo, TCPAddress, MidAndFilesProtocol
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcp_server import PendingConnectionsServer, PendingConnection, PenConnStatus

logger = logging.getLogger(__name__)


class TaskServer(PendingConnectionsServer):
    def __init__(self, node, config_desc, keys_auth, client, use_ipv6=False):
        self.client = client
        self.keys_auth = keys_auth
        self.config_desc = config_desc

        self.node = node
        self.task_keeper = TaskKeeper()
        self.task_manager = TaskManager(config_desc.clientUid, self.node, key_id=self.keys_auth.get_key_id(),
                                       rootPath=TaskServer.__get_task_manager_root(config_desc),
                                       useDistributedResources=config_desc.useDistributedResourceManagement)
        self.task_computer = TaskComputer(config_desc.clientUid, self)
        self.task_sessions = {}
        self.task_sessions_incoming = []

        self.max_trust = 1.0
        self.min_trust = 0.0

        self.last_messages = []
        self.last_message_time_threshold = config_desc.taskSessionTimeout

        self.results_to_send = {}
        self.failures_to_send = {}

        self.use_ipv6 = use_ipv6

        self.response_list = {}

        network = TCPNetwork(ProtocolFactory(MidAndFilesProtocol, self, SessionFactory(TaskSession)), use_ipv6)
        PendingConnectionsServer.__init__(self, config_desc, network)

    def start_accepting(self):
        PendingConnectionsServer.start_accepting(self)

    def sync_network(self):
        self.task_computer.run()
        self._sync_pending()
        self.__remove_old_tasks()
        self.__send_waiting_results()
        self.__remove_old_sessions()
        self._remove_old_listenings()
        self.__send_payments()
        self.__check_payments()

    # This method chooses random task from the network to compute on our machine
    def request_task(self):

        theader = self.task_keeper.getTask()
        if theader is not None:
            trust = self.client.getRequestingTrust(theader.client_id)
            logger.debug("Requesting trust level: {}".format(trust))
            if trust >= self.config_desc.requestingTrust:
                args = {
                    'client_id': self.config_desc.clientUid,
                    'key_id': theader.taskOwnerKeyId,
                    'task_id': theader.taskId,
                    'estimated_performance': self.config_desc.estimatedPerformance,
                    'max_resource_size': self.config_desc.maxResourceSize,
                    'max_memory_size': self.config_desc.maxMemorySize,
                    'num_cores': self.config_desc.numCores
                }
                self._add_pending_request(TaskConnTypes.TaskRequest, theader.taskOwner, theader.taskOwnerPort,
                                          theader.taskOwnerKeyId, args)

                return theader.taskId

        return 0

    def request_resource(self, subtask_id, resource_header, address, port, key_id, task_owner):
        args = {
            'key_id': key_id,
            'subtask_id': subtask_id,
            'resource_header': resource_header
        }
        self._add_pending_request(TaskConnTypes.ResourceRequest, task_owner, port, key_id, args)
        return subtask_id

    def pull_resources(self, task_id, list_files):
        self.client.pull_resources(task_id, list_files)

    def send_results(self, subtask_id, task_id, result, owner_address, owner_port, owner_key_id, owner, node_id):

        if 'data' not in result or 'resultType' not in result:
            logger.error("Wrong result format")
            assert False

        self.client.increaseTrust(node_id, RankingStats.requested)

        if subtask_id not in self.results_to_send:
            self.task_keeper.addToVerification(subtask_id, task_id)
            self.results_to_send[subtask_id] = WaitingTaskResult(subtask_id, result['data'], result['resultType'],
                                                               0.0, 0.0, owner_address, owner_port, owner_key_id, owner)
        else:
            assert False

        return True

    def send_task_failed(self, subtask_id, task_id, err_msg, owner_address, owner_port, owner_key_id, owner, node_id):
        self.client.decreaseTrust(node_id, RankingStats.requested)
        if subtask_id not in self.failures_to_send:
            self.failures_to_send[subtask_id] = WaitingTaskFailure(subtask_id, err_msg, owner_address, owner_port,
                                                                 owner_key_id, owner)

    def new_connection(self, session):
        self.task_sessions_incoming.append(session)

    def get_tasks_headers(self):
        ths = self.task_keeper.getAllTasks() + self.task_manager.get_tasks_headers()

        ret = []

        for th in ths:
            ret.append({"id": th.taskId,
                        "address": th.taskOwnerAddress,
                        "port": th.taskOwnerPort,
                        "keyId": th.taskOwnerKeyId,
                        "taskOwner": th.taskOwner,
                        "ttl": th.ttl,
                        "subtaskTimeout": th.subtaskTimeout,
                        "client_id": th.client_id,
                        "environment": th.environment,
                        "minVersion": th.minVersion})

        return ret

    def add_task_header(self, th_dict_repr):
        try:
            id_ = th_dict_repr["id"]
            if id_ not in self.task_manager.tasks.keys():  # It is not my task id
                self.task_keeper.add_task_header(th_dict_repr, self.client.supportedTask(th_dict_repr))
            return True
        except Exception, err:
            logger.error("Wrong task header received {}".format(str(err)))
            return False

    def remove_task_header(self, task_id):
        self.task_keeper.remove_task_header(task_id)

    def remove_task_session(self, task_session):
        pc = self.pending_connections.get(task_session.conn_id)
        if pc:
            pc.status = PenConnStatus.Failure

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
        return self.results_to_send.get(subtask_id)

    def get_client_id(self):
        return self.config_desc.clientUid

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
        return self.client.node.prvAddr

    def get_resource_port(self):
        return self.client.resourcePort

    def get_subtask_ttl(self, task_id):
        return self.task_keeper.get_subtask_ttl(task_id)

    def add_resource_peer(self, client_id, addr, port, key_id, node_info):
        self.client.add_resource_peer(client_id, addr, port, key_id, node_info)

    def task_result_sent(self, subtask_id):
        if subtask_id in self.results_to_send:
            del self.results_to_send[subtask_id]
        else:
            assert False

    def change_config(self, config_desc):
        PendingConnectionsServer.change_config(self, config_desc)
        self.config_desc = config_desc
        self.last_message_time_threshold = config_desc.taskSessionTimeout
        self.task_manager.change_config(self.__get_task_manager_root(config_desc),
                                       config_desc.useDistributedResourceManagement)
        self.task_computer.change_config()

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout, min_subtask_time):
        self.task_manager.change_timeouts(task_id, full_task_timeout, subtask_timeout, min_subtask_time)

    def get_task_computer_root(self):
        return os.path.join(self.config_desc.rootPath, "ComputerRes")

    def subtask_rejected(self, subtask_id):
        logger.debug("Subtask {} result rejected".format(subtask_id))
        task_id = self.task_keeper.getWaitingForVerificationTaskId(subtask_id)
        if task_id is not None:
            self.decrease_trust_payment(task_id)
            self.remove_task_header(task_id)
            self.task_keeper.removeWaitingForVerificationTaskId(subtask_id)

    def subtask_accepted(self, task_id, reward):
        logger.debug("Task {} result accepted".format(task_id))

        #  task_id = self.task_keeper.getWaitingForVerificationTaskId(task_id)
        if not self.task_keeper.isWaitingForTask(task_id):
            logger.error("Wasn't waiting for reward for task {}".format(task_id))
            return
        try:
            logger.info("Getting {} for task {}".format(reward, task_id))
            self.client.getReward(int(reward))
            self.increase_trust_payment(task_id)
        except ValueError:
            logger.error("Wrong reward amount {} for task {}".format(reward, task_id))
            self.decrease_trust_payment(task_id)
        self.task_keeper.removeWaitingForVerification(task_id)

    def subtask_failure(self, subtask_id, err):
        logger.info("Computation for task {} failed: {}.".format(subtask_id, err))
        node_id = self.task_manager.getNodeIdForSubtask(subtask_id)
        self.client.decreaseTrust(node_id, RankingStats.computed)
        self.task_manager.taskComputation_failure(subtask_id, err)

    def accept_result(self, subtask_id, account_info):
        price_mod = self.task_manager.getPriceMod(subtask_id)
        task_id = self.task_manager.getTaskId(subtask_id)
        self.client.accept_result(task_id, subtask_id, price_mod, account_info)

        mod = min(max(self.task_manager.getTrustMod(subtask_id), self.min_trust), self.max_trust)
        self.client.increaseTrust(account_info.nodeId, RankingStats.computed, mod)

    def receive_task_verification(self, task_id):
        self.task_keeper.receive_task_verification(task_id)

    def increase_trust_payment(self, task_id):
        node_id = self.task_keeper.getReceiverForTaskVerificationResult(task_id)
        self.receive_task_verification(task_id)
        self.client.increaseTrust(node_id, RankingStats.payment, self.max_trust)

    def decrease_trust_payment(self, task_id):
        node_id = self.task_keeper.getReceiverForTaskVerificationResult(task_id)
        self.receive_task_verification(task_id)
        self.client.decreaseTrust(node_id, RankingStats.payment, self.max_trust)

    def local_pay_for_task(self, task_id, address, port, key_id, node_info, price):
        logger.info("Paying {} for task {}".format(price, task_id))
        args = {'key_id': key_id, 'task_id': task_id, 'price': price}
        self._add_pending_request(TaskConnTypes.PayForTask, node_info, port, key_id, args)

    def global_pay_for_task(self, task_id, payments):
        global_payments = {ethAccount: desc.value for ethAccount, desc in payments.items()}
        self.client.global_pay_for_task(task_id, global_payments)
        for ethAccount, v in global_payments.iteritems():
            print "Global paying {} to {}".format(v, ethAccount)

    def reject_result(self, subtask_id, account_info):
        mod = min(max(self.task_manager.getTrustMod(subtask_id), self.min_trust), self.max_trust)
        self.client.decreaseTrust(account_info.node_id, RankingStats.wrongComputed, mod)
        args = {'key_id': account_info.key_id, 'subtask_id': subtask_id}
        self._add_pending_request(TaskConnTypes.ResultRejected, account_info.node_info, account_info.port,
                                  account_info.key_id, args)

    def unpack_delta(self, dest_dir, delta, task_id):
        self.client.resource_server.unpack_delta(dest_dir, delta, task_id)

    def get_computing_trust(self, node_id):
        return self.client.get_computing_trust(node_id)

    def start_task_session(self, node_info, super_node_info, conn_id):
        # FIXME Jaki port i adres startowy?
        args = {'key_id': node_info.key, 'node_info': node_info, 'super_node_info': super_node_info,
                'ans_conn_id': conn_id}
        self._add_pending_request(TaskConnTypes.StartSession, node_info, node_info.prvPort, node_info.key, args)

    def respond_to(self, key_id, session, conn_id):
        if conn_id in self.pending_connections:
            del self.pending_connections[conn_id]

        responses = self.response_list.get(key_id)
        if responses is None or len(responses) == 0:
            session.dropped()
            return

        res = responses.popleft()
        res(session)

    def respond_to_middleman(self, key_id, session, conn_id, dest_key_id):
        if dest_key_id in self.response_list:
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
            self.response_list[key_id].append(response)
        else:
            self.response_list[key_id] = deque([response])

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
        connect_info = TCPConnectInfo([TCPAddress(addr, port)], self.__connection_for_traverse_nat_established,
                                      self.__connection_for_traverse_nat_failure)
        self.network.connect(connect_info, client_key_id=key_id, conn_id=conn_id, super_key_id=super_key_id)

    def traverse_nat_failure(self, conn_id):
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.failure(conn_id, *pc.args)

    def get_tcp_addresses(self, node_info, port, key_id):
        tcp_addresses = PendingConnectionsServer.get_tcp_addresses(self, node_info, port, key_id)
        addr = self.client.getSuggestedAddr(key_id)
        if addr:
            tcp_addresses = [TCPAddress(addr, port)] + tcp_addresses
        return tcp_addresses

    def _get_factory(self):
        return self.factory(self)

    def _listening_established(self, port, **kwargs):
        self.cur_port = port
        logger.info(" Port {} opened - listening".format(self.cur_port))
        self.node.prvPort = self.cur_port
        self.task_manager.listenAddress = self.node.prvAddr
        self.task_manager.listenPort = self.cur_port
        self.task_manager.node = self.node

    def _listening_failure(self, **kwargs):
        logger.error("Listening on ports {} to {} failure".format(self.config_desc.startPort, self.config_desc.endPort))
        # FIXME: some graceful terminations should take place here
        # sys.exit(0)

    def _listening_for_start_session_established(self, port, listen_id, super_node, asking_node, dest_node,
                                                 ask_conn_id):
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
    def __connection_for_task_request_established(self, session, conn_id, client_id, key_id, task_id,
                                                  estimated_performance, max_resource_size, max_memory_size, num_cores):
        session.task_id = task_id
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[task_id] = session
        session.send_hello()
        session.request_task(client_id, task_id, estimated_performance, max_resource_size, max_memory_size, num_cores)

    def __connection_for_task_request_failure(self, conn_id, client_id, key_id, task_id, estimated_performance,
                                              max_resource_size, max_memory_size, num_cores, *args):

        response = lambda session: self.__connection_for_task_request_established(session, conn_id, client_id, key_id,
                                                                                  task_id, estimated_performance,
                                                                                  max_resource_size, max_memory_size,
                                                                                  num_cores)
        if key_id in self.response_list:
            self.response_list[key_id].append(response)
        else:
            self.response_list[key_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_task_result_established(self, session, conn_id, key_id, waiting_task_result):
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.task_sessions[waiting_task_result.subtask_id] = session

        session.send_hello()
        session.send_report_computed_task(waiting_task_result, self.node.prvAddr, self.cur_port,
                                          self.client.getEthAccount(),
                                          self.node)

    def __connection_for_task_result_failure(self, conn_id, key_id, waiting_task_result):

        response = lambda session: self.__connection_for_task_result_established(session, conn_id, key_id,
                                                                                 waiting_task_result)

        if key_id in self.response_list:
            self.response_list[key_id].append(response)
        else:
            self.response_list[key_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_task_failure_established(self, session, conn_id, key_id, subtask_id, err_msg):
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
            self.response_list[key_id].append(response)
        else:
            self.response_list[key_id] = deque([response])

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
            self.response_list[key_id].append(response)
        else:
            self.response_list[key_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_result_rejected_established(self, session, conn_id, key_id, subtask_id):
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_result_rejected(subtask_id)

    def __connection_for_result_rejected_failure(self, conn_id, key_id, subtask_id):

        response = lambda session: self.__connection_for_result_rejected_established(session, conn_id, key_id,
                                                                                     subtask_id)

        if key_id in self.response_list:
            self.response_list[key_id].append(response)
        else:
            self.response_list[key_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_pay_for_task_established(self, session, conn_id, key_id, task_id, price):
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_reward_for_task(task_id, price)
        self.client.taskRewardPaid(task_id, price)

    def __connection_for_pay_for_task_failure(self, conn_id, key_id, task_id, price):

        response = lambda session: self.__connection_for_pay_for_task_established(session, conn_id, key_id, task_id,
                                                                                  price)

        if key_id in self.response_list:
            self.response_list[key_id].append(response)
        else:
            self.response_list[key_id] = deque([response])

        self.client.want_to_start_task_session(key_id, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def __connection_for_start_session_established(self, session, conn_id, key_id, node_info, super_node_info,
                                                   ans_conn_id):
        session.key_id = key_id
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_start_session_response(ans_conn_id)

    def __connection_for_start_session_failure(self, conn_id, key_id, node_info, super_node_info, ans_conn_id):
        logger.info("Failed to start requested task session for node {}".format(key_id))
        self.final_conn_failure(conn_id)
        # TODO CO w takiej sytuacji?
        if super_node_info is None:
            logger.info("Permanently can't connect to node {}".format(key_id))
            return

        # FIXME To powinno zostac przeniesione do jakiejs wyzszej polaczeniowej instalncji
        if self.node.natType in TaskServer.supported_nat_types:
            args = {
                'super_node': super_node_info,
                'asking_node': node_info,
                'dest_node': self.node,
                'ans_conn_id': ans_conn_id
            }
            self._add_pending_request(TaskConnTypes.NatPunch, super_node_info, super_node_info.prvPort,
                                      super_node_info.key,
                                      args)
        else:
            args = {
                'key_id': super_node_info.key,
                'asking_node_info': node_info,
                'self_node_info': self.node,
                'ans_conn_id': ans_conn_id
            }
            self._add_pending_request(TaskConnTypes.Middleman, super_node_info, super_node_info.prvPort,
                                      super_node_info.key,
                                      args)
            # TODO Dodatkowe usuniecie tego zadania (bo zastapione innym)

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
        self._add_pending_request(TaskConnTypes.Middleman, super_node, super_node.prvPort,
                                  super_node.key, args)

    def __connection_for_traverse_nat_established(self, session, client_key_id, conn_id, super_key_id):
        self.respond_to(client_key_id, session, conn_id)  # FIXME

    def __connection_for_traverse_nat_failure(self, client_key_id, conn_id, super_key_id):
        logger.error("Connection for traverse nat failure")
        self.client.inform_about_nat_traverse_failure(super_key_id, client_key_id, conn_id)
        pass  # TODO Powinnismy powiadomic serwer o nieudanej probie polaczenia

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

    def __connection_for_task_request_final_failure(self, conn_id, client_id, key_id, task_id, estimated_performance,
                                                    max_resource_size, max_memory_size, num_cores, *args):
        logger.warning("Cannot connect to task {} owner".format(task_id))
        logger.warning("Removing task {} from task list".format(task_id))

        self.task_computer.taskRequestRejected(task_id, "Connection failed")
        self.task_keeper.request_failure(task_id)

    def __connection_for_pay_for_task_final_failure(self, conn_id, key_id, task_id, price):
        logger.warning("Cannot connect to pay for task {} ".format(task_id))
        self.client.taskRewardPayment_failure(task_id, price)

    def __connection_for_resource_request_final_failure(self, conn_id, key_id, subtask_id, resource_header):
        logger.warning("Cannot connect to task {} owner".format(subtask_id))
        logger.warning("Removing task {} from task list".format(subtask_id))

        self.task_computer.resourceRequestRejected(subtask_id, "Connection failed")
        self.remove_task_header(subtask_id)

    def __connection_for_result_rejected_final_failure(self, conn_id, key_id, subtask_id):
        logger.warning("Cannot connect to deliver information about rejected result for task {}".format(subtask_id))

    def __connection_for_task_result_final_failure(self, conn_id, key_id, waiting_task_result):
        logger.warning("Cannot connect to task {} owner".format(waiting_task_result.subtask_id))

        waiting_task_result.lastSendingTrial = time.time()
        waiting_task_result.delayTime = self.config_desc.maxResultsSendingDelay
        waiting_task_result.alreadySending = False

    def __connection_for_task_failure_final_failure(self, conn_id, key_id, subtask_id, err_msg):
        logger.warning("Cannot connect to task {} owner".format(subtask_id))

    def __connection_for_start_session_final_failure(self, conn_id, key_id, node_info, super_node_info, ans_conn_id):
        logger.warning("Starting session for {} impossible".format(key_id))

    def __connection_for_middleman_final_failure(self, *args):
        pass

    def __connection_for_nat_punch_final_failure(self, *args):
        pass

    # SYNC METHODS
    #############################
    def __remove_old_tasks(self):
        self.task_keeper.removeOldTasks()
        nodes_with_timeouts = self.task_manager.removeOldTasks()
        for node_id in nodes_with_timeouts:
            self.client.decreaseTrust(node_id, RankingStats.computed)

    def __remove_old_sessions(self):
        cur_time = time.time()
        sessions_to_remove = []
        for subtask_id, session in self.task_sessions.iteritems():
            if cur_time - session.last_message_time > self.last_message_time_threshold:
                sessions_to_remove.append(subtask_id)
        for subtask_id in sessions_to_remove:
            if self.task_sessions[subtask_id].task_computer is not None:
                self.task_sessions[subtask_id].task_computer.sessionTimeout()
            self.task_sessions[subtask_id].dropped()

    def __send_waiting_results(self):
        for wtr in self.results_to_send.itervalues():

            if not wtr.already_sending:
                if time.time() - wtr.last_sending_trial > wtr.delay_time:
                    wtr.already_sending = True
                    args = {'key_id': wtr.owner_key_id, 'waiting_task_result': wtr}
                    self._add_pending_request(TaskConnTypes.TaskResult, wtr.owner, wtr.owner_port, wtr.owner_key_id,
                                              args)

        for wtf in self.failures_to_send.itervalues():
            args = {'key_id': wtf.owner_key_id, 'subtask_id': wtf.subtask_id, 'err_msg': wtf.err_msg}
            self._add_pending_request(TaskConnTypes.TaskFailure, wtf.owner, wtf.owner_port, wtf.owner_key_id, args)

        self.failures_to_send.clear()

    def __send_payments(self):
        task_id, payments = self.client.getNewPaymentsTasks()
        if payments:
            self.global_pay_for_task(task_id, payments)
            for payment in payments.itervalues():
                for idx, account in enumerate(payment.accounts):
                    self.local_pay_for_task(task_id, account.addr, account.port, account.keyId, account.node_info,
                                            payment.accountsPayments[idx])

    def __check_payments(self):
        after_deadline = self.task_keeper.checkPayments()
        for task_id in after_deadline:
            self.decrease_trust_payment(task_id)

    # CONFIGURATION METHODS
    #############################
    @staticmethod
    def __get_task_manager_root(config_desc):
        return os.path.join(config_desc.rootPath, "res")

    def _set_conn_established(self):
        self.conn_established_for_type.update({
            TaskConnTypes.TaskRequest: self.__connection_for_task_request_established,
            TaskConnTypes.PayForTask: self.__connection_for_pay_for_task_established,
            TaskConnTypes.ResourceRequest: self.__connection_for_resource_request_established,
            TaskConnTypes.ResultRejected: self.__connection_for_result_rejected_established,
            TaskConnTypes.TaskResult: self.__connection_for_task_result_established,
            TaskConnTypes.TaskFailure: self.__connection_for_task_failure_established,
            TaskConnTypes.StartSession: self.__connection_for_start_session_established,
            TaskConnTypes.Middleman: self.__connection_for_middleman_established,
            TaskConnTypes.NatPunch: self.__connection_for_nat_punch_established
        })

    def _set_conn_failure(self):
        self.conn_failure_for_type.update({
            TaskConnTypes.TaskRequest: self.__connection_for_task_request_failure,
            TaskConnTypes.PayForTask: self.__connection_for_pay_for_task_failure,
            TaskConnTypes.ResourceRequest: self.__connection_for_resource_request_failure,
            TaskConnTypes.ResultRejected: self.__connection_for_result_rejected_failure,
            TaskConnTypes.TaskResult: self.__connection_for_task_result_failure,
            TaskConnTypes.TaskFailure: self.__connection_for_task_failure_failure,
            TaskConnTypes.StartSession: self.__connection_for_start_session_failure,
            TaskConnTypes.Middleman: self.__connection_for_middleman_failure,
            TaskConnTypes.NatPunch: self.__connection_for_nat_punch_failure
        })

    def _set_conn_final_failure(self):
        self.conn_final_failure_for_type.update({
            TaskConnTypes.TaskRequest: self.__connection_for_task_request_final_failure,
            TaskConnTypes.PayForTask: self.__connection_for_pay_for_task_final_failure,
            TaskConnTypes.ResourceRequest: self.__connection_for_resource_request_final_failure,
            TaskConnTypes.ResultRejected: self.__connection_for_result_rejected_final_failure,
            TaskConnTypes.TaskResult: self.__connection_for_task_result_final_failure,
            TaskConnTypes.TaskFailure: self.__connection_for_task_failure_final_failure,
            TaskConnTypes.StartSession: self.__connection_for_start_session_final_failure,
            TaskConnTypes.Middleman: self.__connection_for_middleman_final_failure,
            TaskConnTypes.NatPunch: self.__connection_for_nat_punch_final_failure
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
    def __init__(self, subtask_id, result, result_type, last_sending_trial, delay_time, owner_address, owner_port,
                 owner_key_id, owner):
        self.subtask_id = subtask_id
        self.result = result
        self.result_type = result_type
        self.last_sending_trial = last_sending_trial
        self.delay_time = delay_time
        self.owner_address = owner_address
        self.owner_port = owner_port
        self.owner_key_id = owner_key_id
        self.owner = owner
        self.already_sending = False


class WaitingTaskFailure(object):
    def __init__(self, subtask_id, err_msg, owner_address, owner_port, owner_key_id, owner):
        self.subtask_id = subtask_id
        self.owner_address = owner_address
        self.owner_port = owner_port
        self.owner_key_id = owner_key_id
        self.owner = owner
        self.err_msg = err_msg


class TaskConnTypes(object):
    TaskRequest = 1
    ResourceRequest = 2
    ResultRejected = 3
    PayForTask = 4
    TaskResult = 5
    TaskFailure = 6
    StartSession = 7
    Middleman = 8
    NatPunch = 9


class TaskListenTypes(object):
    StartSession = 1
