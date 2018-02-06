import functools
import logging
import os
import pickle
import time

from golem_messages import message
from twisted.internet import defer

from golem.core.async import AsyncRequest, async_run
from golem.core.common import HandleAttributeError
from golem.core.simpleserializer import CBORSerializer
from golem.core.variables import PROTOCOL_CONST
from golem.docker.environment import DockerEnvironment
from golem.model import Actor
from golem.network import history
from golem.network.concent import exceptions as concent_exceptions
from golem.network.concent import helpers as concent_helpers
from golem.network.concent.client import ConcentRequest
from golem.network.transport import tcpnetwork
from golem.network.transport.session import BasicSafeSession
from golem.resource.resource import decompress_dir
from golem.resource.resourcehandshake import ResourceHandshakeSessionMixin
from golem.task.taskbase import ResultType
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo

logger = logging.getLogger(__name__)


def drop_after_attr_error(*args, **_):
    logger.warning("Attribute error occured(1)", exc_info=True)
    args[0].dropped()


def call_task_computer_and_drop_after_attr_error(*args, **_):
    logger.warning("Attribute error occured(2)", exc_info=True)
    args[0].task_computer.session_closed()
    args[0].dropped()


def dropped_after():
    def inner(f):
        @functools.wraps(f)
        def curry(self, *args, **kwargs):
            result = f(self, *args, **kwargs)
            self.dropped()
            return result
        return curry
    return inner


class TaskSession(BasicSafeSession, ResourceHandshakeSessionMixin,
                  history.IMessageHistoryProvider):
    """ Session for Golem task network """

    ConnectionStateType = tcpnetwork.FilesProtocol
    handle_attr_error = HandleAttributeError(drop_after_attr_error)
    handle_attr_error_with_task_computer = HandleAttributeError(
        call_task_computer_and_drop_after_attr_error
    )

    def __init__(self, conn):
        """
        Create new Session
        :param Protocol conn: connection protocol implementation that this
                              session should enhance
        :return:
        """
        BasicSafeSession.__init__(self, conn)
        ResourceHandshakeSessionMixin.__init__(self)
        self.task_server = self.conn.server
        self.task_manager = self.task_server.task_manager
        self.task_computer = self.task_server.task_computer
        self.concent_service = self.task_server.client.concent_service
        self.task_id = None  # current task id
        self.subtask_id = None  # current subtask id
        self.conn_id = None  # connection id
        # key of a peer that communicates with us through middleman session
        self.asking_node_key_id = None
        # messages waiting to be send (because connection hasn't been
        # verified yet)
        self.msgs_to_send = []
        # information about user that should be rewarded (or punished)
        # for the result
        self.result_owner = None
        self.err_msg = None  # Keep track of errors
        self.__set_msg_interpretations()

        # self.threads = []
    ########################
    # BasicSession methods #
    ########################

    def interpret(self, msg):
        """React to specific message. Disconnect, if message type is unknown
           for that session. In middleman mode doesn't react to message, just
           sends it to other open session.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        self.task_server.set_last_message(
            "<-",
            time.localtime(),
            msg,
            self.address,
            self.port
        )
        BasicSafeSession.interpret(self, msg)

    def dropped(self):
        """ Close connection """
        BasicSafeSession.dropped(self)
        if self.task_server:
            self.task_server.remove_task_session(self)
            if self.key_id:
                self.task_server.remove_resource_peer(self.task_id, self.key_id)

    #######################
    # SafeSession methods #
    #######################

    @property
    def my_private_key(self):
        if self.task_server is None:
            logger.error("Task Server is None, can't sign a message.")
            return None
        return self.task_server.keys_auth.ecc.raw_privkey

    ###################################
    # IMessageHistoryProvider methods #
    ###################################

    def message_to_model(self, msg, local_role, remote_role):
        task, subtask = self._task_subtask_from_message(msg, local_role)

        return dict(
            task=task,
            subtask=subtask,
            node=self.key_id,
            msg_date=time.time(),
            msg_cls=msg.__class__.__name__,
            msg_data=pickle.dumps(msg),
            local_role=local_role,
            remote_role=remote_role,
        )

    def _task_subtask_from_message(self, msg, local_role):
        task, subtask = None, None

        if isinstance(msg, message.TaskToCompute):
            definition = msg.compute_task_def
            if definition:
                task = definition.get('task_id')
                subtask = definition.get('subtask_id')
        else:
            task = getattr(msg, 'task_id', None)
            subtask = getattr(msg, 'subtask_id', None)
            task = task or self._subtask_to_task(subtask, local_role)

        return task, subtask

    def _subtask_to_task(self, sid, local_role):
        if not self.task_manager:
            return None

        if local_role == Actor.Provider:
            return self.task_manager.comp_task_keeper.subtask_to_task.get(sid)
        elif local_role == Actor.Requestor:
            return self.task_manager.subtask2task_mapping.get(sid)

    #######################
    # FileSession methods #
    #######################

    def data_sent(self, extra_data):
        """ All data that should be send in a stream mode has been send.
        :param dict extra_data: additional information that may be needed
        """
        if extra_data and "subtask_id" in extra_data:
            self.task_server.task_result_sent(extra_data["subtask_id"])
        BasicSafeSession.data_sent(self, extra_data)
        self.dropped()

    def full_data_received(self, extra_data):
        """Received all data in a stream mode (it may be task result or
           resources for the task).
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
        :param dict extra_data: dictionary with information about received
                                resource
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
        :param dict extra_data: dictionary with information about
                                received result
        :param bool decrypt: tells whether result decryption should
                             be performed
        """
        result = extra_data.get('result')
        result_type = extra_data.get("result_type")
        subtask_id = extra_data.get("subtask_id")

        if not subtask_id:
            logger.error("No task_id value in extra_data for received data ")
            self.dropped()

        if result_type is None:
            logger.error("No information about result_type for received data ")
            self._reject_subtask_result(subtask_id)
            self.dropped()

        if result_type == ResultType.DATA:
            try:
                if decrypt:
                    result = self.decrypt(result)
                result = CBORSerializer.loads(result)
            except Exception as err:
                logger.error("Can't load result data {}".format(err))
                self._reject_subtask_result(subtask_id)
                return

        def verification_finished():
            if not self.task_manager.verify_subtask(subtask_id):
                self._reject_subtask_result(subtask_id)
                self.dropped()
                return

            payment = self.task_server.accept_result(subtask_id,
                                                     self.result_owner)
            self.send(message.tasks.SubtaskResultsAccepted(
                subtask_id=subtask_id,
                payment_ts=payment.processed_ts))
            self.dropped()

        self.task_manager.computed_task_received(
            subtask_id,
            result,
            result_type,
            verification_finished
        )

    def _reject_subtask_result(self, subtask_id):
        self.task_server.reject_result(subtask_id, self.result_owner)
        self.send_result_rejected(subtask_id)

    def request_resource(self, task_id, resource_header):
        """Ask for a resources for a given task. Task owner should compare
           given resource header with resources for that task and send only
           lacking / changed resources
        :param uuid task_id:
        :param ResourceHeader resource_header: description of resources
                                               that current node has
        :return:
        """
        self.send(
            message.GetResource(
                task_id=task_id,
                resource_header=resource_header
            )
        )

    # TODO address, port and eth_account should be in node_info
    # (or shouldn't be here at all)
    @defer.inlineCallbacks
    def send_report_computed_task(
            self,
            task_result,
            address,
            port,
            eth_account,
            node_info):
        """ Send task results after finished computations
        :param WaitingTaskResult task_result: finished computations result
                                              with additional information
        :param str address: task result owner address
        :param int port: task result owner port
        :param str eth_account: ethereum address (bytes20) of task result owner
        :param Node node_info: information about this node
        :return:
        """
        if task_result.result_type == ResultType.DATA:
            extra_data = []
        elif task_result.result_type == ResultType.FILES:
            extra_data = [os.path.basename(x) for x in task_result.result]
        else:
            logger.error(
                "Unknown result type %r",
                task_result.result_type
            )
            return
        node_name = self.task_server.get_node_name()

        try:
            task_to_compute = history.MessageHistoryService.get_sync_as_message(
                task=task_result.task_id,
                subtask=task_result.subtask_id,
                msg_cls='TaskToCompute',
            )
        except history.MessageNotFound:
            task_to_compute = None
            logger.warning(
                '[CONCENT] TaskToCompute not found for subtask: %r',
                task_result.subtask_id,
            )
            return

        report_computed_task = message.ReportComputedTask(
            subtask_id=task_result.subtask_id,
            result_type=task_result.result_type,
            computation_time=task_result.computing_time,
            node_name=node_name,
            address=address,
            port=port,
            key_id=self.task_server.get_key_id(),
            node_info=node_info,
            eth_account=eth_account,
            extra_data=extra_data)
        report_computed_task.task_to_compute = task_to_compute
        self.send(report_computed_task)

        msg = message.ForceReportComputedTask()
        msg.task_to_compute = task_to_compute
        result_hash = yield concent_helpers.deferred_compute_result_hash(
            task_result,
        )
        msg.result_hash = 'sha1:' + result_hash.hexdigest()
        logger.debug('[CONCENT] ForceReport: %s', msg)

        self.concent_service.submit(
            ConcentRequest.build_key(
                task_result.subtask_id,
                msg.__class__.__name__,
            ),
            msg,
        )

    def send_task_failure(self, subtask_id, err_msg):
        """ Inform task owner that an error occurred during task computation
        :param str subtask_id:
        :param err_msg: error message that occurred during computation
        """
        self.send(
            message.TaskFailure(
                subtask_id=subtask_id,
                err=err_msg
            )
        )

    def send_result_rejected(self, subtask_id):
        """ Inform that result don't pass verification
        :param str subtask_id: subtask that has wrong result
        """
        self.send(message.tasks.SubtaskResultsRejected(subtask_id=subtask_id))

    def send_hello(self):
        """ Send first hello message, that should begin the communication """
        self.send(
            message.Hello(
                client_key_id=self.task_server.get_key_id(),
                rand_val=self.rand_val,
                proto_id=PROTOCOL_CONST.ID
            ),
            send_unverified=True
        )

    def send_start_session_response(self, conn_id):
        """Inform that this session was started as an answer for a request
           to start task session
        :param uuid conn_id: connection id for reference
        """
        self.send(message.StartSessionResponse(conn_id=conn_id))

    #########################
    # Reactions to messages #
    #########################

    def _react_to_want_to_compute_task(self, msg):
        if self.task_server.should_accept_provider(self.key_id):

            if self._handshake_required(self.key_id):
                logger.warning('Cannot yet assign task for %r: resource '
                               'handshake is required', self.key_id)
                self._start_handshake(self.key_id)
                return

            elif self._handshake_in_progress(self.key_id):
                logger.warning('Cannot yet assign task for %r: resource '
                               'handshake is in progress', self.key_id)
                return

            ctd, wrong_task, wait = self.task_manager.get_next_subtask(
                self.key_id, msg.node_name, msg.task_id, msg.perf_index,
                msg.price, msg.max_resource_size, msg.max_memory_size,
                msg.num_cores, self.address)
        else:
            ctd, wrong_task, wait = None, False, False

        reasons = message.CannotAssignTask.REASON
        if wrong_task:
            self.send(
                message.CannotAssignTask(
                    task_id=msg.task_id,
                    reason=reasons.NotMyTask,
                )
            )
            self.dropped()
        elif ctd:
            msg = message.tasks.TaskToCompute(
                compute_task_def=ctd,
                requestor_id=ctd['task_owner']['key'],
                requestor_public_key=ctd['task_owner']['key'],
                provider_id=self.key_id,
                provider_public_key=self.key_id,
            )
            self.send(msg)
        elif wait:
            self.send(message.WaitingForResults())
        else:
            self.send(
                message.CannotAssignTask(
                    task_id=msg.task_id,
                    reason=reasons.NoMoreSubtasks,
                )
            )
            self.dropped()

    @handle_attr_error_with_task_computer
    @history.provider_history
    def _react_to_task_to_compute(self, msg):
        if msg.compute_task_def is None:
            logger.debug('TaskToCompute without ctd: %r', msg)
            self.task_computer.session_closed()
            self.dropped()
            return
        if self._check_ctd_params(msg.compute_task_def)\
                and self._set_env_params(msg.compute_task_def)\
                and self.task_manager.comp_task_keeper.receive_subtask(msg.compute_task_def):  # noqa
            self.task_server.add_task_session(
                msg.compute_task_def['subtask_id'], self
            )
            self.task_computer.task_given(msg.compute_task_def)
        else:
            self.send(
                message.CannotComputeTask(
                    subtask_id=msg.compute_task_def['subtask_id'],
                    reason=self.err_msg
                )
            )
            self.task_computer.session_closed()
            self.dropped()

    def _react_to_waiting_for_results(self, _):
        self.task_computer.session_closed()
        if not self.msgs_to_send:
            self.disconnect(message.Disconnect.REASON.NoMoreMessages)

    def _react_to_cannot_compute_task(self, msg):
        if self.task_manager.get_node_id_for_subtask(msg.subtask_id) == self.key_id:  # noqa
            self.task_manager.task_computation_failure(
                msg.subtask_id,
                'Task computation rejected: {}'.format(msg.reason)
            )
        self.dropped()

    @history.provider_history
    def _react_to_cannot_assign_task(self, msg):
        self.task_computer.task_request_rejected(msg.task_id, msg.reason)
        self.task_server.remove_task_header(msg.task_id)
        self.task_computer.session_closed()
        self.dropped()

    def _react_to_report_computed_task(self, msg):
        if msg.subtask_id not in self.task_manager.subtask2task_mapping:
            logger.warning('Received unknown subtask_id: %r', msg)
            self.dropped()
            return

        if msg.task_to_compute is None:
            logger.warning('Did not receive task_to_compute: %r', msg)
            self.dropped()
            return

        try:
            concent_helpers.process_report_computed_task(
                msg,
                task_session=self,
            )
        except concent_exceptions.ConcentVerificationFailed:
            return

        self.task_server.receive_subtask_computation_time(
            msg.subtask_id,
            msg.computation_time
        )

        self.result_owner = EthAccountInfo(
            msg.key_id,
            msg.port,
            msg.address,
            msg.node_name,
            msg.node_info,
            msg.eth_account
        )
        self.send(message.GetTaskResult(subtask_id=msg.subtask_id))

    @history.provider_history
    def _react_to_get_task_result(self, msg):
        res = self.task_server.get_waiting_task_result(msg.subtask_id)
        if res is None:
            return

        res.already_sending = True
        return self.__send_result_hash(res)

    def _react_to_task_result_hash(self, msg):
        secret = msg.secret
        content_hash = msg.multihash
        subtask_id = msg.subtask_id
        client_options = self.task_server.get_download_options(self.key_id,
                                                               self.address)

        task_id = self.task_manager.subtask2task_mapping.get(subtask_id, None)
        task = self.task_manager.tasks.get(task_id, None)
        output_dir = task.tmp_dir if hasattr(task, 'tmp_dir') else None

        if not task:
            logger.error(
                "Task result received with unknown subtask_id: %r",
                subtask_id
            )
            return

        logger.debug(
            "Task result hash received: %r from %r:%r (options: %r)",
            content_hash,
            self.address,
            self.port,
            client_options
        )

        def on_success(extracted_pkg, *args, **kwargs):
            extra_data = extracted_pkg.to_extra_data()
            logger.debug("Task result extracted {}"
                         .format(extracted_pkg.__dict__))
            self.result_received(extra_data, decrypt=False)

        def on_error(exc, *args, **kwargs):
            logger.error("Task result error: {} ({})"
                         .format(subtask_id, exc or "unspecified"))
            self.send_result_rejected(subtask_id)
            self.task_server.reject_result(subtask_id, self.result_owner)
            self.task_manager.task_computation_failure(
                subtask_id,
                'Error downloading task result'
            )
            self.dropped()

        self.task_manager.task_result_incoming(subtask_id)
        self.task_manager.task_result_manager.pull_package(
            content_hash,
            task_id,
            subtask_id,
            secret,
            success=on_success,
            error=on_error,
            client_options=client_options,
            output_dir=output_dir
        )

    def _react_to_get_resource(self, msg):
        # self.last_resource_msg = msg
        key_id = self.task_server.get_key_id()
        task_id = msg.task_id

        resources = self.task_server.get_resources(task_id)
        options = self.task_server.get_share_options(task_id, key_id)

        self.send(message.ResourceList(
            resources=resources,
            options=options
        ))

    @history.provider_history
    def _react_to_subtask_result_accepted(self, msg):
        self.task_server.subtask_accepted(msg.subtask_id, msg.payment_ts)
        self.dropped()

    @history.provider_history
    def _react_to_subtask_result_rejected(self, msg):
        self.task_server.subtask_rejected(msg.subtask_id)
        self.dropped()

    def _react_to_task_failure(self, msg):
        self.task_server.subtask_failure(msg.subtask_id, msg.err)
        self.dropped()

    def _react_to_delta_parts(self, msg):
        self.task_computer.wait_for_resources(self.task_id, msg.delta_header)
        self.task_server.pull_resources(self.task_id, msg.parts)
        self.task_server.add_resource_peer(
            msg.node_name,
            msg.address,
            msg.port,
            self.key_id,
            msg.node_info
        )

    def _react_to_resource_list(self, msg):
        resource_manager = self.task_server.client.resource_server.resource_manager  # noqa
        resources = resource_manager.from_wire(msg.resources)

        client_options = self.task_server.get_download_options(self.key_id,
                                                               self.address)

        self.task_computer.wait_for_resources(self.task_id, resources)
        self.task_server.pull_resources(self.task_id, resources,
                                        client_options=client_options)

    def _react_to_hello(self, msg):
        super()._react_to_hello(msg)
        if not self.conn.opened:
            return
        send_hello = False

        if self.key_id == 0:
            self.key_id = msg.client_key_id
            send_hello = True

        if msg.proto_id != PROTOCOL_CONST.ID:
            logger.info(
                "Task protocol version mismatch %r (msg) vs %r (local)",
                msg.proto_id,
                PROTOCOL_CONST.ID
            )
            self.disconnect(message.Disconnect.REASON.ProtocolVersion)
            return

        if send_hello:
            self.send_hello()
        self.send(
            message.RandVal(rand_val=msg.rand_val),
            send_unverified=True
        )

    def _react_to_rand_val(self, msg):
        if self.rand_val == msg.rand_val:
            self.verified = True
            self.task_server.verified_conn(self.conn_id, )
            for msg in self.msgs_to_send:
                self.send(msg)
            self.msgs_to_send = []
        else:
            self.disconnect(message.Disconnect.REASON.Unverified)

    def _react_to_start_session_response(self, msg):
        self.task_server.respond_to(self.key_id, self, msg.conn_id)

    @history.provider_history
    def _react_to_ack_report_computed_task(self, msg):
        keeper = self.task_manager.comp_task_keeper
        if keeper.check_task_owner_by_subtask(self.key_id, msg.subtask_id):
            logger.debug("Requestor '%r' accepted the computed subtask '%r' "
                         "report", self.key_id, msg.subtask_id)

            self.concent_service.cancel(
                ConcentRequest.build_key(msg.subtask_id,
                                         'ForceReportComputedTask')
            )
        else:
            logger.warning("Requestor '%r' acknowledged a computed task report "
                           "of an unknown task (subtask_id='%s')",
                           self.key_id, msg.subtask_id)

    @history.provider_history
    def _react_to_reject_report_computed_task(self, msg):
        keeper = self.task_manager.comp_task_keeper
        if keeper.check_task_owner_by_subtask(self.key_id, msg.subtask_id):
            logger.info("Requestor '%r' rejected the computed subtask '%r' "
                        "report", self.key_id, msg.subtask_id)

            self.concent_service.cancel(
                ConcentRequest.build_key(msg.subtask_id,
                                         'ForceReportComputedTask')
            )
        else:
            logger.warning("Requestor '%r' rejected a computed task report of"
                           "an unknown task (subtask_id='%s')",
                           self.key_id, msg.subtask_id)

    def send(self, msg, send_unverified=False):
        if not self.verified and not send_unverified:
            self.msgs_to_send.append(msg)
            return
        BasicSafeSession.send(self, msg, send_unverified=send_unverified)
        self.task_server.set_last_message(
            "->",
            time.localtime(),
            msg,
            self.address,
            self.port
        )

    def _check_ctd_params(self, ctd):
        reasons = message.CannotComputeTask.REASON
        if ctd['key_id'] != self.key_id\
                or ctd['task_owner']['key'] != self.key_id:
            self.err_msg = reasons.WrongKey
            return False
        if not tcpnetwork.SocketAddress.is_proper_address(
                ctd['return_address'],
                ctd['return_port']):
            self.err_msg = reasons.WrongAddress
            return False
        return True

    def _set_env_params(self, ctd):
        environment = self.task_manager.comp_task_keeper.get_task_env(ctd['task_id'])  # noqa
        env = self.task_server.get_environment_by_id(environment)
        reasons = message.CannotComputeTask.REASON
        if not env:
            self.err_msg = reasons.WrongEnvironment
            return False

        if isinstance(env, DockerEnvironment):
            if not self.__check_docker_images(ctd, env):
                return False

        if not env.allow_custom_main_program_file:
            ctd['src_code'] = env.get_source_code()

        if not ctd['src_code']:
            self.err_msg = reasons.NoSourceCode
            return False

        return True

    def __check_docker_images(self, ctd, env):
        for image in ctd['docker_images']:
            for env_image in env.docker_images:
                if env_image.cmp_name_and_tag(image):
                    ctd['docker_images'] = [image]
                    return True

        reasons = message.CannotComputeTask.REASON
        self.err_msg = reasons.WrongDockerImages
        return False

    def __send_result_hash(self, res):
        task_result_manager = self.task_manager.task_result_manager
        client_options = self.task_server.get_share_options(res.task_id,
                                                            self.key_id)

        subtask_id = res.subtask_id
        secret = task_result_manager.gen_secret()

        def success(result):
            result_hash, result_path = result
            logger.debug(
                "Task session: sending task result hash: %r (%r)",
                result_hash, result_path
            )

            self.send(
                message.TaskResultHash(
                    subtask_id=subtask_id,
                    multihash=result_hash,
                    secret=secret,
                    options=client_options
                )
            )

        def error(exc):
            logger.error(
                "Couldn't create a task result package for subtask %r: %r",
                res.subtask_id,
                exc
            )

            if isinstance(exc, EnvironmentError):
                self.task_server.retry_sending_task_result(subtask_id)
            else:
                self.send_task_failure(subtask_id, '{}'.format(exc))
                self.task_server.task_result_sent(subtask_id)

            self.dropped()

        request = AsyncRequest(task_result_manager.create,
                               self.task_server.node, res,
                               key_or_secret=secret)

        return async_run(request, success=success, error=error)

    def __receive_data_result(self, msg):
        extra_data = {
            "subtask_id": msg.subtask_id,
            "result_type": msg.result_type,
            "data_type": "result"
        }
        self.conn.consumer = tcpnetwork.DecryptDataConsumer(self, extra_data)
        self.conn.stream_mode = True
        self.subtask_id = msg.subtask_id

    def __receive_files_result(self, msg):
        extra_data = {
            "subtask_id": msg.subtask_id,
            "result_type": msg.result_type,
            "data_type": "result"
        }
        output_dir = self.task_manager.dir_manager.get_task_temporary_dir(
            self.task_manager.get_task_id(msg.subtask_id), create=False
        )
        self.conn.consumer = tcpnetwork.DecryptFileConsumer(
            msg.extra_data,
            output_dir,
            self,
            extra_data
        )
        self.conn.stream_mode = True
        self.subtask_id = msg.subtask_id

    def __set_msg_interpretations(self):
        self._interpretation.update({
            message.WantToComputeTask.TYPE: self._react_to_want_to_compute_task,
            message.TaskToCompute.TYPE: self._react_to_task_to_compute,
            message.CannotAssignTask.TYPE: self._react_to_cannot_assign_task,
            message.CannotComputeTask.TYPE: self._react_to_cannot_compute_task,
            message.ReportComputedTask.TYPE: self._react_to_report_computed_task,  # noqa
            message.GetTaskResult.TYPE: self._react_to_get_task_result,
            message.TaskResultHash.TYPE: self._react_to_task_result_hash,
            message.GetResource.TYPE: self._react_to_get_resource,
            message.ResourceList.TYPE: self._react_to_resource_list,
            message.tasks.SubtaskResultsAccepted.TYPE:
                self._react_to_subtask_result_accepted,
            message.tasks.SubtaskResultsRejected.TYPE:
                self._react_to_subtask_result_rejected,
            message.TaskFailure.TYPE: self._react_to_task_failure,
            message.DeltaParts.TYPE: self._react_to_delta_parts,
            message.Hello.TYPE: self._react_to_hello,
            message.RandVal.TYPE: self._react_to_rand_val,
            message.StartSessionResponse.TYPE: self._react_to_start_session_response,  # noqa
            message.WaitingForResults.TYPE: self._react_to_waiting_for_results,  # noqa

            # Concent messages
            message.AckReportComputedTask.TYPE:
                self._react_to_ack_report_computed_task,
            message.RejectReportComputedTask.TYPE:
                self._react_to_reject_report_computed_task,
        })

        # self.can_be_not_encrypted.append(message.Hello.TYPE)
        self.can_be_unverified.extend(
            [
                message.Hello.TYPE,
                message.RandVal.TYPE,
                message.ChallengeSolution.TYPE
            ]
        )
        self.can_be_not_encrypted.extend([message.Hello.TYPE])
