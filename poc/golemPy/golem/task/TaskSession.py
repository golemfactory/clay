import time
import cPickle as pickle
import struct
import logging
import os

from golem.Message import MessageHello, MessageRandVal, MessageWantToComputeTask, MessageTaskToCompute, \
    MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, MessageTaskResult, \
    MessageGetTaskResult, MessageRemoveTask, MessageSubtaskResultAccepted, MessageSubtaskResultRejected, \
    MessageDeltaParts, MessageResourceFormat, MessageAcceptResourceFormat, MessageTaskFailure, \
    MessageStartSessionResponse, MessageMiddleman, MessageMiddlemanReady, MessageBeingMiddlemanAccepted, \
    MessageMiddlemanAccepted, MessageJoinMiddlemanConn, MessageNatPunch, MessageWaitForNatTraverse
from golem.network.transport.tcp_network import MidAndFilesProtocol, EncryptFileProducer, DecryptFileConsumer, \
    EncryptDataProducer, DecryptDataConsumer
from golem.network.transport.session import MiddlemanSafeSession
from golem.task.TaskBase import resultTypes
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
        self.task_manager = self.task_server.taskManager
        self.task_computer = self.task_server.taskComputer
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
        self.task_server.setLastMessage("<-", time.localtime(), msg, self.address, self.port)
        MiddlemanSafeSession.interpret(self, msg)

    def dropped(self):
        """ Close connection """
        MiddlemanSafeSession.dropped(self)
        if self.task_server:
            self.task_server.removeTaskSession(self)

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

        msg.sign(self.task_server)
        return msg

    def verify(self, msg):
        """ Verify signature on given message. Check if message was signed with key_id from this connection.
        :param Message msg: message to be verified
        :return boolean: True if message was signed with key_id from this connection
        """
        verify = self.task_server.verifySig(msg.sig, msg.getShortHash(), self.key_id)
        return verify

    #######################
    # FileSession methods #
    #######################

    def data_sent(self, extra_data):
        """ All data that should be send in a stream mode has been send.
        :param dict extra_data: additional information that may be needed
        """
        if extra_data and "subtask_id" in extra_data:
            self.task_server.taskResultSent(extra_data["subtask_id"])
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
            self.task_computer.resourceGiven(task_id)
        else:
            logger.error("No taskId in extra_data for received File")
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

        if result_type == resultTypes['data']:
            try:
                result = self.decrypt(result)
                result = pickle.loads(result)
            except Exception, err:
                logger.error("Can't unpickle result data {}".format(str(err)))

        subtask_id = extra_data.get("subtask_id")
        if subtask_id:
            self.task_manager.computedTaskReceived(subtask_id, result, result_type)
            if self.task_manager.verifySubtask(subtask_id):
                self.task_server.acceptResult(subtask_id, self.result_owner)
            else:
                self.task_server.rejectResult(subtask_id, self.result_owner)
        else:
            logger.error("No taskId value in extra_data for received data ")
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
        if task_result.resultType == resultTypes['data']:
            extra_data = []
        elif task_result.resultType == resultTypes['files']:
            extra_data = [os.path.basename(x) for x in task_result.result]
        else:
            logger.error("Unknown result type {}".format(task_result.resultType))
            return
        node_id = self.task_server.getClientId()

        self.send(MessageReportComputedTask(task_result.subtaskId, task_result.resultType, node_id, address, port,
                                            self.task_server.getKeyId(), node_info, eth_account, extra_data))

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
        self.send(MessageHello(clientKeyId=self.task_server.getKeyId(), randVal=self.rand_val), send_unverified=True)

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
        trust = self.task_server.getComputingTrust(msg.clientId)
        logger.debug("Computing trust level: {}".format(trust))
        if trust >= self.task_server.configDesc.computingTrust:
            ctd, wrong_task = self.task_manager.getNextSubTask(msg.clientId, msg.taskId, msg.perfIndex,
                                                               msg.maxResourceSize, msg.maxMemorySize, msg.numCores)
        else:
            ctd, wrong_task = None, False

        if wrong_task:
            self.send(MessageCannotAssignTask(msg.taskId, "Not my task  {}".format(msg.taskId)))
            self.send(MessageRemoveTask(msg.taskId))
        elif ctd:
            self.send(MessageTaskToCompute(ctd))
        else:
            self.send(MessageCannotAssignTask(msg.taskId, "No more subtasks in {}".format(msg.taskId)))

    def _react_to_task_to_compute(self, msg):
        self.task_computer.taskGiven(msg.ctd, self.task_server.getSubtaskTtl(msg.ctd.taskId))
        self.dropped()

    def _react_to_cannot_assign_task(self, msg):
        self.task_computer.taskRequestRejected(msg.taskId, msg.reason)
        self.task_server.removeTaskHeader(msg.taskId)
        self.dropped()

    def _react_to_report_computed_task(self, msg):
        if msg.subtaskId in self.task_manager.subTask2TaskMapping:
            delay = self.task_manager.acceptResultsDelay(self.task_manager.subTask2TaskMapping[msg.subtaskId])

            if delay == -1.0:
                self.dropped()
            elif delay == 0.0:
                self.send(MessageGetTaskResult(msg.subtaskId, delay))
                self.result_owner = EthAccountInfo(msg.keyId, msg.port, msg.address, msg.nodeId, msg.nodeInfo,
                                                   msg.ethAccount)

                if msg.resultType == resultTypes['data']:
                    self.__receive_data_result(msg)
                elif msg.resultType == resultTypes['files']:
                    self.__receive_files_result(msg)
                else:
                    logger.error("Unknown result type {}".format(msg.resultType))
                    self.dropped()
            else:
                self.send(MessageGetTaskResult(msg.subtaskId, delay))
                self.dropped()
        else:
            self.dropped()

    def _react_to_get_task_result(self, msg):
        res = self.task_server.getWaitingTaskResult(msg.subtaskId)
        if res:
            if msg.delay == 0.0:
                res.alreadySending = True
                if res.resultType == resultTypes['data']:
                    self.__send_data_results(res)
                elif res.resultType == resultTypes['files']:
                    self.__send_files_results(res)
                else:
                    logger.error("Unknown result type {}".format(res.resultType))
                    self.dropped()
            else:
                res.lastSendingTrial = time.time()
                res.delayTime = msg.delay
                res.alreadySending = False
                self.dropped()

    def _react_to_task_result(self, msg):
        self.__receiveTaskResult(msg.subtaskId, msg.result)

    def _react_to_get_resource(self, msg):
        self.last_resource_msg = msg
        self.__send_resource_format(self.task_server.configDesc.useDistributedResourceManagement)

    def _react_to_accept_resource_format(self, msg):
        if self.last_resource_msg is not None:
            if self.task_server.configDesc.useDistributedResourceManagement:
                self.__send_resource_parts_list(self.last_resource_msg)
            else:
                self.__send_delta_resource(self.last_resource_msg)
            self.last_resource_msg = None
        else:
            logger.error("Unexpected MessageAcceptResource message")
            self.dropped()

    def _react_to_resource(self, msg):
        self.task_computer.resourceGiven(msg.subtaskId)
        self.dropped()

    def _react_to_subtask_result_accepted(self, msg):
        self.task_server.subtaskAccepted(msg.subtaskId, msg.reward)
        self.dropped()

    def _react_to_subtask_result_rejected(self, msg):
        self.task_server.subtaskRejected(msg.subtaskId)
        self.dropped()

    def _react_to_task_failure(self, msg):
        self.task_server.subtaskFailure(msg.subtaskId, msg.err)
        self.dropped()

    def _react_to_delta_parts(self, msg):
        self.task_computer.waitForResources(self.task_id, msg.deltaHeader)
        self.task_server.pullResources(self.task_id, msg.parts)
        self.task_server.addResourcePeer(msg.clientId, msg.addr, msg.port, self.key_id, msg.nodeInfo)
        self.dropped()

    def _react_to_resource_format(self, msg):
        if not msg.useDistributedResource:
            tmp_file = os.path.join(self.task_computer.resourceManager.getTemporaryDir(self.task_id),
                                    "res" + self.task_id)
            output_dir = self.task_computer.resourceManager.getResourceDir(self.task_id)
            extra_data = {"task_id": self.task_id, "data_type": 'resource', 'output_dir': output_dir}
            self.conn.consumer = DecryptFileConsumer([tmp_file], output_dir, self, extra_data)
            self.conn.stream_mode = True
        self.__send_accept_resource_format()

    def _react_to_hello(self, msg):
        if self.key_id == 0:
            self.key_id = msg.clientKeyId
            self.send_hello()

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(TaskSession.DCRUnverified)
            return

        self.send(MessageRandVal(msg.randVal), send_unverified=True)

    def _react_to_rand_val(self, msg):
        if self.rand_val == msg.randVal:
            self.verified = True
            self.task_server.verifiedConn(self.conn_id, )
            for msg in self.msgs_to_send:
                self.send(msg)
            self.msgs_to_send = []
        else:
            self.disconnect(TaskSession.DCRUnverified)

    def _react_to_start_session_response(self, msg):
        self.task_server.respondTo(self.key_id, self, msg.connId)

    def _react_to_middleman(self, msg):
        self.send(MessageBeingMiddlemanAccepted())
        self.task_server.beAMiddleman(self.key_id, self, self.conn_id, msg.askingNode, msg.destNode, msg.askConnId)

    def _react_to_join_middleman_conn(self, msg):
        self.middlemanConnData = {'keyId': msg.keyId, 'connId': msg.connId, 'destNodeKeyId': msg.destNodeKeyId}
        self.send(MessageMiddlemanAccepted())

    def _react_to_middleman_ready(self, msg):
        key_id = self.middlemanConnData['keyId']
        conn_id = self.middlemanConnData['connId']
        dest_node_key_id = self.middlemanConnData['destNodeKeyId']
        self.task_server.respondToMiddleman(key_id, self, conn_id, dest_node_key_id)

    def _react_to_being_middleman_accepted(self, msg):
        self.key_id = self.asking_node_key_id

    def _react_to_middleman_accepted(self, msg):
        self.send(MessageMiddlemanReady())
        self.is_middleman = True
        self.openSession.is_middleman = True

    def _react_to_nat_punch(self, msg):
        self.task_server.organizeNatPunch(self.address, self.port, self.key_id, msg.askingNode, msg.destNode,
                                          msg.askConnId)
        self.send(MessageWaitForNatTraverse(self.port))
        self.dropped()

    def _react_to_wait_for_nat_traverse(self, msg):
        self.task_server.waitForNatTraverse(msg.port, self)

    def _react_to_nat_punch_failure(self, msg):
        pass  # TODO Powiadomienie drugiego wierzcholka o nieudanym rendezvous

    def send(self, msg, send_unverified=False):
        if not self.is_middleman and not self.verified and not send_unverified:
            self.msgs_to_send.append(msg)
            return
        MiddlemanSafeSession.send(self, msg, send_unverified=send_unverified)
        # print "Task Session Sending to {}:{}: {}".format(self.address, self.port, msg)
        self.task_server.setLastMessage("->", time.localtime(), msg, self.address, self.port)

    def __send_delta_resource(self, msg):
        res_file_path = self.task_manager.prepareResource(msg.taskId, pickle.loads(msg.resourceHeader))

        if not res_file_path:
            logger.error("Task {} has no resource".format(msg.taskId))
            self.conn.transport.write(struct.pack("!L", 0))
            self.dropped()
            return

        self.conn.producer = EncryptFileProducer([res_file_path], self)

    def __send_resource_parts_list(self, msg):
        delta_header, parts_list = self.task_manager.getResourcePartsList(msg.taskId, pickle.loads(msg.resourceHeader))
        self.send(MessageDeltaParts(self.task_id, delta_header, parts_list, self.task_server.getClientId(),
                                    self.task_server.node, self.task_server.getResourceAddr(),
                                    self.task_server.getResourcePort())
                  )

    def __send_resource_format(self, use_distributed_resource):
        self.send(MessageResourceFormat(use_distributed_resource))

    def __send_accept_resource_format(self):
        self.send(MessageAcceptResourceFormat())

    def __send_data_results(self, res):
        result = pickle.dumps(res.result)
        extra_data = {"subtask_id": res.subtaskId, "data_type": "result"}
        self.conn.producer = EncryptDataProducer(self.encrypt(result), self, extra_data=extra_data)

    def __send_files_results(self, res):
        extra_data = {"subtask_id": res.subtaskId}
        self.conn.producer = EncryptFileProducer(res.result, self, extra_data=extra_data)

    def __receive_data_result(self, msg):
        extra_data = {"subtask_id": msg.subtaskId, "result_type": msg.resultType, "data_type": "result"}
        self.conn.consumer = DecryptDataConsumer(self, extra_data)
        self.conn.stream_mode = True
        self.subtask_id = msg.subtaskId

    def __receive_files_result(self, msg):
        extra_data = {"subtask_id": msg.subtaskId, "result_type": msg.resultType, "data_type": "result"}
        output_dir = self.task_manager.dirManager.getTaskTemporaryDir(
            self.task_manager.getTaskId(msg.subtaskId), create=False
        )
        self.conn.consumer = DecryptFileConsumer(msg.extraData, output_dir, self, extra_data)
        self.conn.stream_mode = True
        self.subtask_id = msg.subtaskId

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
