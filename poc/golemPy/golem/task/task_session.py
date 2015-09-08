import time
import cPickle as pickle
import struct
import logging
import os

from golem.network.transport.message import MessageHello, MessageRandVal, MessageWantToComputeTask, MessageTaskToCompute, \
    MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, MessageTaskResult, \
    MessageGetTaskResult, MessageRemoveTask, MessageSubtaskResultAccepted, MessageSubtaskResultRejected, \
    MessageDeltaParts, MessageResourceFormat, MessageAcceptResourceFormat, MessageTaskFailure, \
    MessageStartSessionResponse, MessageMiddleman, MessageMiddlemanReady, MessageBeingMiddlemanAccepted, \
    MessageMiddlemanAccepted, MessageJoinMiddlemanConn, MessageNatPunch, MessageWaitForNatTraverse
from golem.network.transport.tcp_network import MidAndFilesProtocol, EncryptFileProducer, DecryptFileConsumer, \
    EncryptDataProducer, DecryptDataConsumer
from golem.network.transport.session import MiddlemanSafeSession
from golem.task.TaskBase import result_types
from golem.resource.Resource import decompressDir
from golem.transactions.Ethereum.EthereumPaymentsKeeper import EthAccountInfo

logger = logging.getLogger(__name__)


class TaskSession(MiddlemanSafeSession):
    """ Session for Golem task network """

    ConnectionStateType = MidAndFilesProtocol

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

        self.last_resource_msg = None  # last message about resource

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
            return data
        try:
            data = self.task_server.decrypt(data)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
        except Exception, err:
            logger.warning("Fail to decrypt message {}".format(str(err)))
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
        verify = self.task_server.verify_sig(msg.sig, msg.get_short_hash(), self.key_id)
        return verify

    #######################
    # FileSession methods #
    #######################

    def data_sent(self, extra_data):
        """ All data that should be send in a stream mode has been send.
        :param dict extra_data: additional information that may be needed
        """
        if extra_data and "subtask_id" in extra_data:
            self.task_server.task_result_sent(extra_data["subtask_id"])
        if self.conn.producer:
            self.conn.producer.close()
            self.conn.producer = None
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

    def production_failed(self, extra_data=None):
        """ Producer encounter error and stopped sending data in stream mode
        :param dict|None extra_data: additional information that may be needed
        """
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
            decompressDir(extra_data.get('output_dir'), tmp_file)
        task_id = extra_data.get('task_id')
        if task_id:
            self.task_computer.resource_given(task_id)
        else:
            logger.error("No task_id in extra_data for received File")
        self.conn.producer = None
        self.dropped()

    def result_received(self, extra_data):
        """ Inform server about received result
        :param dict extra_data: dictionary with information about received result
        """
        result = extra_data.get('result')
        result_type = extra_data.get("result_type")
        if result_type is None:
            logger.error("No information about result_type for received data ")
            self.dropped()
            return

        if result_type == result_types['data']:
            try:
                result = self.decrypt(result)
                result = pickle.loads(result)
            except Exception, err:
                logger.error("Can't unpickle result data {}".format(str(err)))

        subtask_id = extra_data.get("subtask_id")
        if subtask_id:
            self.task_manager.computedTaskReceived(subtask_id, result, result_type)
            if self.task_manager.verifySubtask(subtask_id):
                self.task_server.accept_result(subtask_id, self.result_owner)
            else:
                self.task_server.reject_result(subtask_id, self.result_owner)
        else:
            logger.error("No task_id value in extra_data for received data ")
        self.dropped()

    # TODO Wszystkie parametry klienta powinny zostac zapisane w jednej spojnej klasie
    def request_task(self, node_id, task_id, performance_index, max_resource_size, max_memory_size, num_cores):
        """ Inform that node wants to compute given task
        :param str node_id: id of that node
        :param uuid task_id: if of a task that node wants to compute
        :param float performance_index: benchmark result for this task type
        :param int max_resource_size: how much disk space can this node offer
        :param int max_memory_size: how much ram can this node offer
        :param int num_cores: how many cpu cores this node can offer
        :return:
        """
        self.send(MessageWantToComputeTask(node_id, task_id, performance_index, max_resource_size, max_memory_size,
                                           num_cores))

    def request_resource(self, task_id, resource_header):
        """ Ask for a resources for a given task. Task owner should compare given resource header with
         resources for that task and send only lacking / changed resources
        :param uuid task_id:
        :param ResourceHeader resource_header: description of resources that current node has
        :return:
        """
        self.send(MessageGetResource(task_id, pickle.dumps(resource_header)))

    # TODO address, port oraz eth_account powinny byc w node_info (albo w ogole niepotrzebne)
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
        node_id = self.task_server.get_client_id()

        self.send(MessageReportComputedTask(task_result.subtask_id, task_result.result_type, node_id, address, port,
                                            self.task_server.get_key_id(), node_info, eth_account, extra_data))

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

    # TODO Trzeba zmienic nazwe tej metody
    def send_reward_for_task(self, subtask_id, reward):
        """ Inform that results pass verification and confirm reward
        :param str subtask_id:
        :param int reward: how high is the payment
        """
        self.send(MessageSubtaskResultAccepted(subtask_id, reward))

    def send_hello(self):
        """ Send first hello message, that should begin the communication """
        self.send(MessageHello(client_key_id=self.task_server.get_key_id(), rand_val=self.rand_val), send_unverified=True)

    def send_start_session_response(self, conn_id):
        """ Inform that this session was started as an answer for a request to start task session
        :param uuid conn_id: connection id for reference
        """
        self.send(MessageStartSessionResponse(conn_id))

    # TODO Moze dest_node nie jest potrzebne i mozna je pobierac z polaczenia?
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
        trust = self.task_server.get_computing_trust(msg.client_id)
        logger.debug("Computing trust level: {}".format(trust))
        if trust >= self.task_server.config_desc.computing_trust:
            ctd, wrong_task = self.task_manager.getNextSubTask(msg.client_id, msg.task_id, msg.perf_index,
                                                               msg.max_resource_size, msg.max_memory_size,
                                                               msg.num_cores)
        else:
            ctd, wrong_task = None, False

        if wrong_task:
            self.send(MessageCannotAssignTask(msg.task_id, "Not my task  {}".format(msg.task_id)))
            self.send(MessageRemoveTask(msg.task_id))
        elif ctd:
            self.send(MessageTaskToCompute(ctd))
        else:
            self.send(MessageCannotAssignTask(msg.task_id, "No more subtasks in {}".format(msg.task_id)))

    def _react_to_task_to_compute(self, msg):
        self.task_computer.task_given(msg.ctd, self.task_server.get_subtask_ttl(msg.ctd.taskId))
        self.dropped()

    def _react_to_cannot_assign_task(self, msg):
        self.task_computer.taskRequestRejected(msg.task_id, msg.reason)
        self.task_server.remove_task_header(msg.task_id)
        self.dropped()

    def _react_to_report_computed_task(self, msg):
        if msg.subtask_id in self.task_manager.subTask2TaskMapping:
            delay = self.task_manager.accept_results_delay(self.task_manager.subTask2TaskMapping[msg.subtask_id])

            if delay == -1.0:
                self.dropped()
            elif delay == 0.0:
                self.send(MessageGetTaskResult(msg.subtask_id, delay))
                self.result_owner = EthAccountInfo(msg.key_id, msg.port, msg.address, msg.node_id, msg.node_info,
                                                   msg.eth_account)

                if msg.result_type == result_types['data']:
                    self.__receive_data_result(msg)
                elif msg.result_type == result_types['files']:
                    self.__receive_files_result(msg)
                else:
                    logger.error("Unknown result type {}".format(msg.result_type))
                    self.dropped()
            else:
                self.send(MessageGetTaskResult(msg.subtask_id, delay))
                self.dropped()
        else:
            self.dropped()

    def _react_to_get_task_result(self, msg):
        res = self.task_server.get_waiting_task_result(msg.subtask_id)
        if res is None:
            return
        if msg.delay == 0.0:
            res.already_sending = True
            if res.result_type == result_types['data']:
                self.__send_data_results(res)
            elif res.result_type == result_types['files']:
                self.__send_files_results(res)
            else:
                logger.error("Unknown result type {}".format(res.result_type))
                self.dropped()
        else:
            res.last_sending_trial = time.time()
            res.delay_time = msg.delay
            res.already_sending = False
            self.dropped()

    def _react_to_task_result(self, msg):
        self.__receiveTaskResult(msg.subtask_id, msg.result)

    def _react_to_get_resource(self, msg):
        self.last_resource_msg = msg
        self.__send_resource_format(self.task_server.config_desc.use_distributed_resource_management)

    def _react_to_accept_resource_format(self, msg):
        if self.last_resource_msg is not None:
            if self.task_server.config_desc.use_distributed_resource_management:
                self.__send_resource_parts_list(self.last_resource_msg)
            else:
                self.__send_delta_resource(self.last_resource_msg)
            self.last_resource_msg = None
        else:
            logger.error("Unexpected MessageAcceptResource message")
            self.dropped()

    def _react_to_resource(self, msg):
        self.task_computer.resource_given(msg.subtask_id)
        self.dropped()

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
        self.task_computer.waitForResources(self.task_id, msg.delta_header)
        self.task_server.pull_resources(self.task_id, msg.parts)
        self.task_server.add_resource_peer(msg.client_id, msg.addr, msg.port, self.key_id, msg.node_info)
        self.dropped()

    def _react_to_resource_format(self, msg):
        if not msg.use_distributed_resource:
            tmp_file = os.path.join(self.task_computer.resource_manager.getTemporaryDir(self.task_id),
                                    "res" + self.task_id)
            output_dir = self.task_computer.resource_manager.getResourceDir(self.task_id)
            extra_data = {"task_id": self.task_id, "data_type": 'resource', 'output_dir': output_dir}
            self.conn.consumer = DecryptFileConsumer([tmp_file], output_dir, self, extra_data)
            self.conn.stream_mode = True
        self.__send_accept_resource_format()

    def _react_to_hello(self, msg):
        if self.key_id == 0:
            self.key_id = msg.client_key_id
            self.send_hello()

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(TaskSession.DCRUnverified)
            return

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
        self.task_server.be_a_middleman(self.key_id, self, self.conn_id, msg.asking_node, msg.dest_node, msg.ask_conn_id)

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
        pass  # TODO Powiadomienie drugiego wierzcholka o nieudanym rendezvous

    def send(self, msg, send_unverified=False):
        if not self.is_middleman and not self.verified and not send_unverified:
            self.msgs_to_send.append(msg)
            return
        MiddlemanSafeSession.send(self, msg, send_unverified=send_unverified)
        # print "Task Session Sending to {}:{}: {}".format(self.address, self.port, msg)
        self.task_server.set_last_message("->", time.localtime(), msg, self.address, self.port)

    def __send_delta_resource(self, msg):
        res_file_path = self.task_manager.prepare_resource(msg.task_id, pickle.loads(msg.resource_header))

        if not res_file_path:
            logger.error("Task {} has no resource".format(msg.task_id))
            self.conn.transport.write(struct.pack("!L", 0))
            self.dropped()
            return

        self.conn.producer = EncryptFileProducer([res_file_path], self)

    def __send_resource_parts_list(self, msg):
        delta_header, parts_list = self.task_manager.getResourcePartsList(msg.task_id, pickle.loads(msg.resource_header))
        self.send(MessageDeltaParts(self.task_id, delta_header, parts_list, self.task_server.get_client_id(),
                                    self.task_server.node, self.task_server.get_resource_addr(),
                                    self.task_server.get_resource_port())
                  )

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

    def __receive_data_result(self, msg):
        extra_data = {"subtask_id": msg.subtask_id, "result_type": msg.result_type, "data_type": "result"}
        self.conn.consumer = DecryptDataConsumer(self, extra_data)
        self.conn.stream_mode = True
        self.subtask_id = msg.subtask_id

    def __receive_files_result(self, msg):
        extra_data = {"subtask_id": msg.subtask_id, "result_type": msg.result_type, "data_type": "result"}
        output_dir = self.task_manager.dir_manager.getTaskTemporaryDir(
            self.task_manager.getTaskId(msg.subtask_id), create=False
        )
        self.conn.consumer = DecryptFileConsumer(msg.extra_data, output_dir, self, extra_data)
        self.conn.stream_mode = True
        self.subtask_id = msg.subtask_id

    def __set_msg_interpretations(self):
        self._interpretation.update({
            MessageWantToComputeTask.Type: self._react_to_want_to_compute_task,
            MessageTaskToCompute.Type: self._react_to_task_to_compute,
            MessageCannotAssignTask.Type: self._react_to_cannot_assign_task,
            MessageReportComputedTask.Type: self._react_to_report_computed_task,
            MessageGetTaskResult.Type: self._react_to_get_task_result,
            MessageTaskResult.Type: self._react_to_task_result,
            MessageGetResource.Type: self._react_to_get_resource,
            MessageAcceptResourceFormat.Type: self._react_to_accept_resource_format,
            MessageResource: self._react_to_resource,
            MessageSubtaskResultAccepted: self._react_to_subtask_result_accepted,
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
            MessageWaitForNatTraverse.Type: self._react_to_wait_for_nat_traverse
        })

        # self.can_be_not_encrypted.append(MessageHello.Type)
        self.can_be_unsigned.append(MessageHello.Type)
        self.can_be_unverified.extend([MessageHello.Type, MessageRandVal.Type])
