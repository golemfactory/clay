import cPickle as pickle
import logging
import os
import struct
import time

from golem.core.common import HandleAttributeError
from golem.network.transport.message import MessageHello, MessageRandVal, MessageWantToComputeTask, \
    MessageTaskToCompute, MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, \
    MessageGetTaskResult, MessageSubtaskResultAccepted, MessageSubtaskResultRejected, \
    MessageDeltaParts, MessageResourceFormat, MessageAcceptResourceFormat, MessageTaskFailure, \
    MessageStartSessionResponse, MessageMiddleman, MessageMiddlemanReady, MessageBeingMiddlemanAccepted, \
    MessageMiddlemanAccepted, MessageJoinMiddlemanConn, MessageNatPunch, MessageWaitForNatTraverse, \
    MessageResourceList, MessageTaskResultHash, MessageWaitingForResults, MessageCannotComputeTask, \
    MessageContestWinnerAccept, MessageContestWinner, MessageContestWinnerReject
from golem.network.transport.session import MiddlemanSafeSession
from golem.network.transport.tcpnetwork import MidAndFilesProtocol, EncryptFileProducer, DecryptFileConsumer, \
    EncryptDataProducer, DecryptDataConsumer, SocketAddress
from golem.resource.client import AsyncRequest, AsyncRequestExecutor
from golem.resource.resource import decompress_dir
from golem.task.taskbase import ComputeTaskDef, result_types, resource_types
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo

logger = logging.getLogger(__name__)


TASK_PROTOCOL_ID = 'brass.0.2.1'


def drop_after_attr_error(*args, **kwargs):
    logger.warning("Attribute error occur")
    args[0].dropped()


def call_task_computer_and_drop_after_attr_error(*args, **kwargs):
    logger.warning("Attribute error occur")
    args[0].task_computer.session_closed()
    args[0].dropped()


class TaskSession(MiddlemanSafeSession):
    """ Session for Golem task network """

    ConnectionStateType = MidAndFilesProtocol
    handle_attr_error = HandleAttributeError(drop_after_attr_error)
    handle_attr_error_with_task_computer = HandleAttributeError(call_task_computer_and_drop_after_attr_error)

    def __init__(self, conn):
        """
        Create new Session
        :param Protocol conn: connection protocol implementation that this session should enhance
        :return:
        """
        MiddlemanSafeSession.__init__(self, conn)
        self.task_server = self.conn.server
        self.task_manager = self.task_server.task_manager
        self.task_computer = self.task_server.task_computer
        self.task_id = None  # current task id
        self.subtask_id = None  # current subtask id
        self.conn_id = None  # connection id
        self.asking_node_key_id = None  # key of a peer that communicates with us through middleman session

        self.msgs_to_send = []  # messages waiting to be send (because connection hasn't been verified yet)

        # self.last_resource_msg = None  # last message about resource

        self.result_owner = None  # information about user that should be rewarded (or punished) for the result

        self.__set_msg_interpretations()

    ########################
    # BasicSession methods #
    ########################

    def interpret(self, msg):
        """ React to specific message. Disconnect, if message type is unknown for that session.
        In middleman mode doesn't react to message, just sends it to other open session.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        # print "Receiving from {}:{}: {}".format(self.address, self.port, msg)
        self.task_server.set_last_message("<-", time.localtime(), msg, self.address, self.port)
        MiddlemanSafeSession.interpret(self, msg)

    def dropped(self):
        """ Close connection """
        MiddlemanSafeSession.dropped(self)
        if self.task_server:
            self.task_server.remove_task_session(self)
        if self.task_manager:
            self.task_manager.contest_manager.remove_contender(self.task_id, self.key_id)

    #######################
    # SafeSession methods #
    #######################

    def encrypt(self, data):
        """ Encrypt given data using key_id from this connection
        :param str data: data to be encrypted
        :return str: encrypted data or unchanged message (if server doesn't exist)
        """
        if self.task_server:
            return self.task_server.encrypt(data, self.key_id)
        logger.warning("Can't encrypt message - no task server")
        return data

    def decrypt(self, data):
        """ Decrypt given data using private key. If during decryption AssertionError occurred this may mean that
        data is not encrypted simple serialized message. In that case unaltered data are returned.
        :param str data: data to be decrypted
        :return str|None: decrypted data
        """
        if self.task_server is None:
            logger.warning("Can't decrypt data - no task server")
            return data
        try:
            data = self.task_server.decrypt(data)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
        except Exception as err:
            logger.warning("Fail to decrypt message {}".format(err))
            self.dropped()
            return None

        return data

    def sign(self, msg):
        """ Sign given message
        :param Message msg: message to be signed
        :return Message: signed message
        """
        if self.task_server is None:
            logger.error("Task Server is None, can't sign a message.")
            return None

        msg.sig = self.task_server.sign(msg.get_short_hash())
        return msg

    def verify(self, msg):
        """ Verify signature on given message. Check if message was signed with key_id from this connection.
        :param Message msg: message to be verified
        :return boolean: True if message was signed with key_id from this connection
        """
        return self.task_server.verify_sig(msg.sig, msg.get_short_hash(), self.key_id)

    #######################
    # FileSession methods #
    #######################

    def data_sent(self, extra_data):
        """ All data that should be send in a stream mode has been send.
        :param dict extra_data: additional information that may be needed
        """
        if extra_data and "subtask_id" in extra_data:
            self.task_server.task_result_sent(extra_data["subtask_id"])
        MiddlemanSafeSession.data_sent(self, extra_data)
        self.dropped()

    def full_data_received(self, extra_data):
        """ Received all data in a stream mode (it may be task result or resources for the task).
        :param dict extra_data: additional information that may be needed
        """
        data_type = extra_data.get('data_type')
        if data_type is None:
            logger.error("Wrong full data received type")
            self.dropped()
            return
        if data_type == "resource":
            self.resource_received(extra_data)
        elif data_type == "result":
            self.result_received(extra_data)
        else:
            logger.error("Unknown data type {}".format(data_type))
            self.conn.producer = None
            self.dropped()

    def resource_received(self, extra_data):
        """ Inform server about received resource
        :param dict extra_data: dictionary with information about received resource
        """
        file_sizes = extra_data.get('file_sizes')
        if file_sizes is None:
            logger.error("No file sizes given")
            self.dropped()
        file_size = file_sizes[0]
        tmp_file = extra_data.get('file_received')[0]
        if file_size > 0:
            decompress_dir(extra_data.get('output_dir'), tmp_file)
        task_id = extra_data.get('task_id')
        if task_id:
            self.task_computer.resource_given(task_id)
        else:
            logger.error("No task_id in extra_data for received File")
        self.conn.producer = None
        self.dropped()

    def result_received(self, extra_data, decrypt=True):
        """ Inform server about received result
        :param dict extra_data: dictionary with information about received result
        :param bool decrypt: tells whether result decryption should be performed
        """
        result = extra_data.get('result')
        result_type = extra_data.get("result_type")
        subtask_id = extra_data.get("subtask_id")

        if result_type is None:
            logger.error("No information about result_type for received data ")
            self._reject_subtask_result(subtask_id)
            self.dropped()
            return

        if result_type == result_types['data']:
            try:
                if decrypt:
                    result = self.decrypt(result)
                result = pickle.loads(result)
            except Exception as err:
                logger.error("Can't unpickle result data {}".format(err))
                self._reject_subtask_result(subtask_id)
                self.dropped()
                return

        if subtask_id:
            self.task_manager.computed_task_received(subtask_id, result, result_type)
            if self.task_manager.verify_subtask(subtask_id):
                self.task_server.accept_result(subtask_id, self.result_owner)
                self.send(MessageSubtaskResultAccepted(subtask_id))
            else:
                self._reject_subtask_result(subtask_id)
        else:
            logger.error("No task_id value in extra_data for received data ")
        self.dropped()

    def _reject_subtask_result(self, subtask_id):
        self.task_server.reject_result(subtask_id, self.result_owner)
        self.send(MessageSubtaskResultRejected(subtask_id))

    def request_task(self, node_name, task_id, performance_index, price, max_resource_size, max_memory_size, num_cores):
        """ Inform that node wants to compute given task
        :param str node_name: name of that node
        :param uuid task_id: if of a task that node wants to compute
        :param float performance_index: benchmark result for this task type
        :param float price: price for an hour
        :param int max_resource_size: how much disk space can this node offer
        :param int max_memory_size: how much ram can this node offer
        :param int num_cores: how many cpu cores this node can offer
        :return:
        """
        self.task_id = task_id
        self.send(MessageWantToComputeTask(node_name, task_id, performance_index, price,
                                           max_resource_size, max_memory_size, num_cores))

    def request_resource(self, task_id, resource_header):
        """ Ask for a resources for a given task. Task owner should compare given resource header with
         resources for that task and send only lacking / changed resources
        :param uuid task_id:
        :param ResourceHeader resource_header: description of resources that current node has
        :return:
        """
        self.send(MessageGetResource(task_id, pickle.dumps(resource_header)))

    # TODO address, port and eth_account should be in node_info (or shouldn't be here at all)
    def send_report_computed_task(self, task_result, address, port, eth_account, node_info):
        """ Send task results after finished computations
        :param WaitingTaskResult task_result: finished computations result with additional information
        :param str address: task result owner address
        :param int port: task result owner port
        :param str eth_account: ethereum address (bytes20) of task result owner
        :param Node node_info: information about this node
        :return:
        """
        if task_result.result_type == result_types['data']:
            extra_data = []
        elif task_result.result_type == result_types['files']:
            extra_data = [os.path.basename(x) for x in task_result.result]
        else:
            logger.error("Unknown result type {}".format(task_result.result_type))
            return
        node_name = self.task_server.get_node_name()

        self.send(MessageReportComputedTask(task_result.subtask_id, task_result.result_type, task_result.computing_time,
                                            node_name, address, port, self.task_server.get_key_id(), node_info,
                                            eth_account, extra_data))

    def send_task_failure(self, subtask_id, err_msg):
        """ Inform task owner that an error occurred during task computation
        :param str subtask_id:
        :param err_msg: error message that occurred during computation
        """
        self.send(MessageTaskFailure(subtask_id, err_msg))

    def send_result_rejected(self, subtask_id):
        """ Inform that result don't pass verification
        :param str subtask_id: subtask that has wrong result
        """
        self.send(MessageSubtaskResultRejected(subtask_id))

    def send_message_subtask_accepted(self, subtask_id, reward):
        """ Inform that results pass verification and confirm reward
        :param str subtask_id:
        :param int reward: how high is the payment
        """
        self.send(MessageSubtaskResultAccepted(subtask_id, reward))

    def send_hello(self):
        """ Send first hello message, that should begin the communication """
        self.send(
            MessageHello(
                client_key_id=self.task_server.get_key_id(),
                rand_val=self.rand_val,
                proto_id=TASK_PROTOCOL_ID
            ),
            send_unverified=True
        )

    def send_contest_winner(self, task_id):
        self.send(MessageContestWinner(task_id))

    def send_task_to_compute(self, msg):
        ctd = self.task_manager.get_next_subtask(self.key_id, msg.node_name, msg.task_id, msg.perf_index,
                                                 msg.price, msg.max_resource_size, msg.max_memory_size,
                                                 msg.num_cores, self.address)
        self.send(MessageTaskToCompute(ctd))

    def send_cannot_assign_task(self, task_id, reason=None):
        self.send(MessageCannotAssignTask(task_id, reason or "Unspecified"))
        self.disconnect(self.DCRNoMoreMessages)

    def send_start_session_response(self, conn_id):
        """ Inform that this session was started as an answer for a request to start task session
        :param uuid conn_id: connection id for reference
        """
        self.send(MessageStartSessionResponse(conn_id))

    # TODO Maybe dest_node is not necessary?
    def send_middleman(self, asking_node, dest_node, ask_conn_id):
        """ Ask node to become middleman in the communication with other node
        :param Node asking_node: other node information. Middleman should connect with that node.
        :param Node dest_node: information about this node
        :param ask_conn_id: connection id that asking node gave for reference
        """
        self.asking_node_key_id = asking_node.key
        self.send(MessageMiddleman(asking_node, dest_node, ask_conn_id))

    def send_join_middleman_conn(self, key_id, conn_id, dest_node_key_id):
        """ Ask node communicate with other through middleman connection (this node is the middleman and connection
            with other node is already opened
        :param key_id:  this node public key
        :param conn_id: connection id for reference
        :param dest_node_key_id: public key of the other node of the middleman connection
        """
        self.send(MessageJoinMiddlemanConn(key_id, conn_id, dest_node_key_id))

    def send_nat_punch(self, asking_node, dest_node, ask_conn_id):
        """ Ask node to inform other node about nat hole that this node will prepare with this connection
        :param Node asking_node: node that should be informed about potential hole based on this connection
        :param Node dest_node: node that will try to end this connection and open hole in it's NAT
        :param uuid ask_conn_id: connection id that asking node gave for reference
        :return:
        """
        self.asking_node_key_id = asking_node.key
        self.send(MessageNatPunch(asking_node, dest_node, ask_conn_id))

    #########################
    # Reactions to messages #
    #########################

    def _react_to_want_to_compute_task(self, msg):

        trust = self.task_server.get_computing_trust(self.key_id)
        self.task_id = msg.task_id

        logger.debug("Computing trust level: {}".format(trust))

        if not self.task_manager.has_task(msg.task_id):
            logger.debug("Unknown task {} (received from node {})".format(msg.task_id, self.key_id))
            self.send(MessageCannotAssignTask(msg.task_id, "Not my task {}".format(msg.task_id)))
            self.dropped()

        elif not self.task_manager.has_subtasks(msg.task_id, msg.max_resource_size, msg.max_memory_size, msg.price):
            logger.debug("No subtasks in task {}".format(msg.task_id))
            self.send(MessageCannotAssignTask(msg.task_id, "No more subtasks in {}".format(msg.task_id)))
            self.dropped()

        elif trust < self.task_server.config_desc.computing_trust:
            message = "Reputation too low (min {}, got {})".format(self.task_server.config_desc.computing_trust, trust)
            logger.debug(message + " for task {}".format(msg.task_id))
            self.send(MessageCannotAssignTask(msg.task_id, message))
            self.dropped()

        elif self.task_manager.is_finishing(self.key_id, msg.task_id):
            logger.debug("Waiting for task {} results from node {}".format(msg.task_id, self.key_id))
            self.send(MessageWaitingForResults())

        else:
            logger.debug("New contender {} for task {}".format(self.key_id, msg.task_id))
            computing_trust = self.task_server.get_computing_trust(self.key_id) or 0.
            self.task_manager.contest_manager.add_contender(msg.task_id, self.key_id, self,
                                                            request_message=msg,
                                                            computing_trust=computing_trust)

    def _react_to_contest_winner(self, msg):
        if self.task_id == msg.task_id and not self.task_computer.is_busy(msg.task_id):
            self.send(MessageContestWinnerAccept(msg.task_id))
        else:
            self.send(MessageContestWinnerReject(msg.task_id))
            self.dropped()

    def _react_to_contest_winner_accept(self, msg):
        if self.task_id == msg.task_id:
            self.task_manager.contest_manager.winner_accepts(msg.task_id, self.key_id)
        else:
            self.disconnect(self.DCRBadProtocol)

    def _react_to_contest_winner_reject(self, msg):
        if self.task_id == msg.task_id:
            self.task_manager.contest_manager.winner_rejects(msg.task_id, self.key_id)
            self.dropped()
        else:
            self.disconnect(self.DCRBadProtocol)

    @handle_attr_error_with_task_computer
    def _react_to_task_to_compute(self, msg):
        if self._check_ctd_params(msg.ctd) and self.task_manager.comp_task_keeper.receive_subtask(msg.ctd):
            self.task_server.add_task_session(msg.ctd.subtask_id, self)
            self.task_computer.task_given(msg.ctd)
        else:
            self.send(MessageCannotComputeTask(msg.ctd.subtask_id))
            self.task_computer.session_closed()
            self.dropped()

    def _react_to_waiting_for_results(self, _):
        self.task_computer.session_closed()
        if not self.msgs_to_send:
            self.disconnect(self.DCRNoMoreMessages)

    def _react_to_cannot_compute_task(self, msg):
        if self.task_manager.get_node_id_for_subtask(msg.subtask_id) == self.key_id:
            self.task_manager.contest_manager.winner_rejects(msg.task_id, self.key_id)
            self.task_manager.task_computation_failure(msg.subtask_id,
                                                       'Task computation rejected: {}'.format(msg.reason))
        self.dropped()

    def _react_to_cannot_assign_task(self, msg):
        self.task_computer.task_request_rejected(msg.task_id, msg.reason)
        self.task_server.remove_task_header(msg.task_id)
        self.task_computer.session_closed()
        self.dropped()

    def _react_to_report_computed_task(self, msg):
        if msg.subtask_id in self.task_manager.subtask2task_mapping:
            self.task_server.receive_subtask_computation_time(msg.subtask_id, msg.computation_time)
            delay = self.task_manager.accept_results_delay(self.task_manager.subtask2task_mapping[msg.subtask_id])
            self.result_owner = EthAccountInfo(msg.key_id, msg.port, msg.address, msg.node_name, msg.node_info,
                                               msg.eth_account)
            self.send(MessageGetTaskResult(msg.subtask_id, delay))
        else:
            self.dropped()

    def _react_to_get_task_result(self, msg):
        res = self.task_server.get_waiting_task_result(msg.subtask_id)
        if res is None:
            return

        if msg.delay <= 0.0:
            res.already_sending = True
            return self.__send_result_hash(res)
        else:
            res.last_sending_trial = time.time()
            res.delay_time = msg.delay
            res.already_sending = False
            self.dropped()

    def _react_to_task_result_hash(self, msg):
        secret = msg.secret
        multihash = msg.multihash
        subtask_id = msg.subtask_id
        client_options = msg.options

        task_id = self.task_manager.subtask2task_mapping.get(subtask_id, None)
        task = self.task_manager.tasks.get(task_id, None)
        output_dir = task.tmp_dir if hasattr(task, 'tmp_dir') else None

        if not task:
            logger.error("Task result received with unknown subtask_id: {}".format(subtask_id))
            return

        logger.debug("Task result hash received: {} from {}:{} (options: {})"
                     .format(multihash, self.address, self.port, client_options))

        def on_success(extracted_pkg, *args, **kwargs):
            extra_data = extracted_pkg.to_extra_data()
            logger.debug("Task result extracted {}"
                         .format(extracted_pkg.__dict__))
            self.result_received(extra_data, decrypt=False)

        def on_error(exc, *args, **kwargs):
            logger.error("Task result error: {} ({})"
                         .format(subtask_id, exc or "unspecified"))
            self.send(MessageSubtaskResultRejected(subtask_id))
            self.task_server.reject_result(subtask_id, self.result_owner)
            self.task_manager.task_computation_failure(subtask_id,
                                                       'Error downloading task result')
            self.dropped()

        self.task_manager.task_result_incoming(subtask_id)
        self.task_manager.task_result_manager.pull_package(multihash, task_id, subtask_id,
                                                           secret,
                                                           success=on_success,
                                                           error=on_error,
                                                           client_options=client_options,
                                                           output_dir=output_dir)

    def _react_to_get_resource(self, msg):
        # self.last_resource_msg = msg
        # self.__send_resource_format(self.task_server.config_desc.use_distributed_resource_management)
        self.__send_resource_list(msg)

    def _react_to_accept_resource_format(self, msg):
        if self.last_resource_msg is not None:
            if self.task_server.config_desc.use_distributed_resource_management:
                self.__send_resource_list(self.last_resource_msg)
            else:
                self.__send_delta_resource(self.last_resource_msg)
            self.last_resource_msg = None
        else:
            logger.error("Unexpected MessageAcceptResource message")
            self.dropped()

    def _react_to_resource(self, msg):
        self.task_computer.resource_given(msg.subtask_id)

    def _react_to_subtask_result_accepted(self, msg):
        self.task_server.subtask_accepted(msg.subtask_id, msg.reward)
        self.dropped()

    def _react_to_subtask_result_rejected(self, msg):
        self.task_server.subtask_rejected(msg.subtask_id)
        self.dropped()

    def _react_to_task_failure(self, msg):
        self.task_server.subtask_failure(msg.subtask_id, msg.err)
        self.dropped()

    def _react_to_delta_parts(self, msg):
        self.task_computer.wait_for_resources(self.task_id, msg.delta_header)
        self.task_server.pull_resources(self.task_id, msg.parts)
        self.task_server.add_resource_peer(msg.node_name, msg.addr, msg.port, self.key_id, msg.node_info)

    def _react_to_resource_list(self, msg):
        resource_manager = self.task_server.client.resource_server.resource_manager
        resources = resource_manager.join_split_resources(msg.resources)
        client_options = msg.options

        self.task_computer.wait_for_resources(self.task_id, resources)
        self.task_server.pull_resources(self.task_id, resources,
                                        client_options=client_options)

    def _react_to_resource_format(self, msg):
        if not msg.use_distributed_resource:
            tmp_file = os.path.join(self.task_computer.resource_manager.get_temporary_dir(self.task_id),
                                    "res" + self.task_id)
            output_dir = self.task_computer.resource_manager.get_resource_dir(self.task_id)
            extra_data = {"task_id": self.task_id, "data_type": 'resource', 'output_dir': output_dir}
            self.conn.consumer = DecryptFileConsumer([tmp_file], output_dir, self, extra_data)
            self.conn.stream_mode = True
        self.__send_accept_resource_format()

    def _react_to_hello(self, msg):
        send_hello = False

        if self.key_id == 0:
            self.key_id = msg.client_key_id
            send_hello = True

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(TaskSession.DCRUnverified)
            return

        if msg.proto_id != TASK_PROTOCOL_ID:
            logger.error("Protocol version mismatch {} vs {} (local)"
                         .format(msg.proto_id, TASK_PROTOCOL_ID))
            self.disconnect(TaskSession.DCRProtocolVersion)
            return

        if send_hello:
            self.send_hello()
        self.send(MessageRandVal(msg.rand_val), send_unverified=True)

    def _react_to_rand_val(self, msg):
        if self.rand_val == msg.rand_val:
            self.verified = True
            self.task_server.verified_conn(self.conn_id, )
            for msg in self.msgs_to_send:
                self.send(msg)
            self.msgs_to_send = []
        else:
            self.disconnect(TaskSession.DCRUnverified)

    def _react_to_start_session_response(self, msg):
        self.task_server.respond_to(self.key_id, self, msg.conn_id)

    def _react_to_middleman(self, msg):
        self.send(MessageBeingMiddlemanAccepted())
        self.task_server.be_a_middleman(self.key_id, self, self.conn_id, msg.asking_node, msg.dest_node,
                                        msg.ask_conn_id)

    def _react_to_join_middleman_conn(self, msg):
        self.middleman_conn_data = {'key_id': msg.key_id, 'conn_id': msg.conn_id,
                                    'dest_node_key_id': msg.dest_node_key_id}
        self.send(MessageMiddlemanAccepted())

    def _react_to_middleman_ready(self, msg):
        key_id = self.middleman_conn_data.get('key_id')
        conn_id = self.middleman_conn_data.get('conn_id')
        dest_node_key_id = self.middleman_conn_data.get('dest_node_key_id')
        self.task_server.respond_to_middleman(key_id, self, conn_id, dest_node_key_id)

    def _react_to_being_middleman_accepted(self, msg):
        self.key_id = self.asking_node_key_id

    def _react_to_middleman_accepted(self, msg):
        self.send(MessageMiddlemanReady())
        self.is_middleman = True
        self.open_session.is_middleman = True

    def _react_to_nat_punch(self, msg):
        self.task_server.organize_nat_punch(self.address, self.port, self.key_id, msg.asking_node, msg.dest_node,
                                            msg.ask_conn_id)
        self.send(MessageWaitForNatTraverse(self.port))
        self.dropped()

    def _react_to_wait_for_nat_traverse(self, msg):
        self.task_server.wait_for_nat_traverse(msg.port, self)

    def _react_to_nat_punch_failure(self, msg):
        pass

    def send(self, msg, send_unverified=False):
        if not self.is_middleman and not self.verified and not send_unverified:
            self.msgs_to_send.append(msg)
            return
        MiddlemanSafeSession.send(self, msg, send_unverified=send_unverified)
        # print "Task Session Sending to {}:{}: {}".format(self.address, self.port, msg)
        self.task_server.set_last_message("->", time.localtime(), msg, self.address, self.port)

    def _check_ctd_params(self, ctd):
        if not isinstance(ctd, ComputeTaskDef) or ctd.key_id != self.key_id or ctd.task_owner.key != self.key_id:
            return False
        if not SocketAddress.is_proper_address(ctd.return_address, ctd.return_port):
            return False
        return True

    def __send_delta_resource(self, msg):
        res_file_path = self.task_manager.get_resources(msg.task_id, pickle.loads(msg.resource_header),
                                                        resource_types["zip"])

        if not res_file_path:
            logger.error("Task {} has no resource".format(msg.task_id))
            self.conn.transport.write(struct.pack("!L", 0))
            self.dropped()
            return

        self.conn.producer = EncryptFileProducer([res_file_path], self)

    def __send_resource_parts_list(self, msg):
        res = self.task_manager.get_resources(msg.task_id, pickle.loads(msg.resource_header),
                                              resource_types["parts"])
        if res is None:
            return
        delta_header, parts_list = res

        self.send(MessageDeltaParts(self.task_id, delta_header, parts_list, self.task_server.get_node_name(),
                                    self.task_server.node, self.task_server.get_resource_addr(),
                                    self.task_server.get_resource_port())
                  )

    def __send_resource_list(self, msg):
        resource_manager = self.task_server.client.resource_server.resource_manager
        client_options = resource_manager.build_client_options(self.task_server.get_key_id())
        res = resource_manager.list_split_resources(msg.task_id)
        self.send(MessageResourceList(res, options=client_options))

    def __send_resource_format(self, use_distributed_resource):
        self.send(MessageResourceFormat(use_distributed_resource))

    def __send_accept_resource_format(self):
        self.send(MessageAcceptResourceFormat())

    def __send_data_results(self, res):
        result = pickle.dumps(res.result)
        extra_data = {"subtask_id": res.subtask_id, "data_type": "result"}
        self.conn.producer = EncryptDataProducer(self.encrypt(result), self, extra_data=extra_data)

    def __send_files_results(self, res):
        extra_data = {"subtask_id": res.subtask_id}
        self.conn.producer = EncryptFileProducer(res.result, self, extra_data=extra_data)

    def __send_result_hash(self, res):
        task_result_manager = self.task_manager.task_result_manager
        resource_manager = task_result_manager.resource_manager
        client_options = resource_manager.build_client_options(self.task_server.get_key_id())

        subtask_id = res.subtask_id
        secret = task_result_manager.gen_secret()

        def success(output):
            logger.debug("Task session: sending task result hash: {}".format(output))

            file_name, multihash = output
            self.send(MessageTaskResultHash(subtask_id, multihash, secret, options=client_options))

        def error(exc):
            logger.error("Couldn't create a task result package for subtask {}: {}"
                         .format(res.subtask_id, exc))

            if isinstance(exc, EnvironmentError):
                self.task_server.retry_sending_task_result(subtask_id)
            else:
                self.send(MessageTaskFailure(subtask_id, '{}'.format(exc)))
                self.task_server.task_result_sent(subtask_id)

            self.dropped()

        request = AsyncRequest(task_result_manager.create,
                               self.task_server.node, res,
                               client_options=client_options,
                               key_or_secret=secret)

        return AsyncRequestExecutor.run(request, success=success, error=error)

    def __receive_data_result(self, msg):
        extra_data = {"subtask_id": msg.subtask_id, "result_type": msg.result_type, "data_type": "result"}
        self.conn.consumer = DecryptDataConsumer(self, extra_data)
        self.conn.stream_mode = True
        self.subtask_id = msg.subtask_id

    def __receive_files_result(self, msg):
        extra_data = {"subtask_id": msg.subtask_id, "result_type": msg.result_type, "data_type": "result"}
        output_dir = self.task_manager.dir_manager.get_task_temporary_dir(
            self.task_manager.get_task_id(msg.subtask_id), create=False
        )
        self.conn.consumer = DecryptFileConsumer(msg.extra_data, output_dir, self, extra_data)
        self.conn.stream_mode = True
        self.subtask_id = msg.subtask_id

    def __set_msg_interpretations(self):
        self._interpretation.update({
            MessageWantToComputeTask.Type: self._react_to_want_to_compute_task,
            MessageTaskToCompute.Type: self._react_to_task_to_compute,
            MessageCannotAssignTask.Type: self._react_to_cannot_assign_task,
            MessageCannotComputeTask.Type: self._react_to_cannot_compute_task,
            MessageReportComputedTask.Type: self._react_to_report_computed_task,
            MessageContestWinner.Type: self._react_to_contest_winner,
            MessageContestWinnerAccept.Type: self._react_to_contest_winner_accept,
            MessageContestWinnerReject.Type: self._react_to_contest_winner_reject,
            MessageGetTaskResult.Type: self._react_to_get_task_result,
            MessageTaskResultHash.Type: self._react_to_task_result_hash,
            MessageGetResource.Type: self._react_to_get_resource,
            MessageAcceptResourceFormat.Type: self._react_to_accept_resource_format,
            MessageResource.Type: self._react_to_resource,
            MessageResourceList.Type: self._react_to_resource_list,
            MessageSubtaskResultAccepted.Type: self._react_to_subtask_result_accepted,
            MessageSubtaskResultRejected.Type: self._react_to_subtask_result_rejected,
            MessageTaskFailure.Type: self._react_to_task_failure,
            MessageDeltaParts.Type: self._react_to_delta_parts,
            MessageResourceFormat.Type: self._react_to_resource_format,
            MessageHello.Type: self._react_to_hello,
            MessageRandVal.Type: self._react_to_rand_val,
            MessageStartSessionResponse.Type: self._react_to_start_session_response,
            MessageMiddleman.Type: self._react_to_middleman,
            MessageMiddlemanReady.Type: self._react_to_middleman_ready,
            MessageBeingMiddlemanAccepted.Type: self._react_to_being_middleman_accepted,
            MessageMiddlemanAccepted.Type: self._react_to_middleman_accepted,
            MessageJoinMiddlemanConn.Type: self._react_to_join_middleman_conn,
            MessageNatPunch.Type: self._react_to_nat_punch,
            MessageWaitForNatTraverse.Type: self._react_to_wait_for_nat_traverse,
            MessageWaitingForResults.Type: self._react_to_waiting_for_results,
        })

        # self.can_be_not_encrypted.append(MessageHello.Type)
        self.can_be_unsigned.append(MessageHello.Type)
        self.can_be_unverified.extend([MessageHello.Type, MessageRandVal.Type])
