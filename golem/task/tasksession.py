import functools
import logging
import os
import time

from golem_messages import message
from golem_messages import helpers as msg_helpers

from golem.core.common import HandleAttributeError
from golem.core.keysauth import KeysAuth
from golem.core.simpleserializer import CBORSerializer
from golem.core.variables import PROTOCOL_CONST
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.model import Actor
from golem.network import history
from golem.network.concent import helpers as concent_helpers
from golem.network.p2p import node as p2p_node
from golem.network.transport import tcpnetwork
from golem.network.transport.session import BasicSafeSession
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


def get_task_message(message_class_name, task_id, subtask_id, log_prefix=None):
    if log_prefix:
        log_prefix = '%s ' % log_prefix

    try:
        return history.MessageHistoryService.get_sync_as_message(
            task=task_id,
            subtask=subtask_id,
            msg_cls=message_class_name,
        )
    except history.MessageNotFound:
        logger.warning(
            '%s%s message not found for task %r, subtask: %r',
            log_prefix or '',
            message_class_name,
            task_id,
            subtask_id,
        )


class TaskSession(BasicSafeSession, ResourceHandshakeSessionMixin):
    """ Session for Golem task network """

    ConnectionStateType = tcpnetwork.SafeProtocol
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
        self.task_manager = self.task_server.task_manager  # type: TaskManager
        self.task_computer = self.task_server.task_computer
        self.concent_service = self.task_server.client.concent_service
        self.task_id = None  # current task id
        self.subtask_id = None  # current subtask id
        self.conn_id = None  # connection id
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

    def _subtask_to_task(self, sid, local_role):
        if not self.task_manager:
            return None

        if local_role == Actor.Provider:
            return self.task_manager.comp_task_keeper.subtask_to_task.get(sid)
        elif local_role == Actor.Requestor:
            return self.task_manager.subtask2task_mapping.get(sid)
        return None

    #######################
    # FileSession methods #
    #######################

    def result_received(self, extra_data):
        """ Inform server about received result
        :param dict extra_data: dictionary with information about
                                received result
        """
        result = extra_data.get('result')
        result_type = extra_data.get("result_type")
        subtask_id = extra_data.get("subtask_id")

        def send_verification_failure():
            self._reject_subtask_result(
                subtask_id,
                reason=message.tasks.SubtaskResultsRejected.REASON
                .VerificationNegative
            )

        if not subtask_id:
            logger.error("No task_id value in extra_data for received data ")
            self.dropped()

        if result_type is None:
            logger.error("No information about result_type for received data ")
            send_verification_failure()
            self.dropped()

        if result_type == ResultType.DATA:
            try:
                result = CBORSerializer.loads(result)
            except Exception as err:
                logger.exception("Can't load result data")
                send_verification_failure()
                return

        def verification_finished():
            if not self.task_manager.verify_subtask(subtask_id):
                send_verification_failure()
                self.dropped()
                return

            task_id = self._subtask_to_task(subtask_id, Actor.Requestor)

            task_to_compute = get_task_message(
                'TaskToCompute', task_id, subtask_id)

            payment = self.task_server.accept_result(
                subtask_id, self.result_owner)

            self.send(message.tasks.SubtaskResultsAccepted(
                task_to_compute=task_to_compute,
                payment_ts=payment.processed_ts
            ))
            self.dropped()

        self.task_manager.computed_task_received(
            subtask_id,
            result,
            result_type,
            verification_finished
        )

    def _reject_subtask_result(self, subtask_id, reason):
        logger.debug('_reject_subtask_result(%r, %r)', subtask_id, reason)
        self.task_server.reject_result(subtask_id, self.result_owner)
        self.send_result_rejected(subtask_id, reason)

    def request_resource(self, task_id):
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
                resource_header=None,  # unused slot
            )
        )

    # TODO address, port and eth_account should be in node_info
    # (or shouldn't be here at all). Issue #2403
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
        task_to_compute = get_task_message(
            'TaskToCompute',
            task_result.task_id,
            task_result.subtask_id,
        )

        if not task_to_compute:
            return

        client_options = self.task_server.get_share_options(task_result.task_id,
                                                            self.address)

        report_computed_task = message.ReportComputedTask(
            subtask_id=task_result.subtask_id,
            result_type=task_result.result_type,
            computation_time=task_result.computing_time,
            node_name=node_name,
            address=address,
            port=port,
            key_id=self.task_server.get_key_id(),
            node_info=node_info.to_dict(),
            eth_account=eth_account,
            extra_data=extra_data,
            size=task_result.result_size,
            package_hash='sha1:' + task_result.package_sha1,
            multihash=task_result.result_hash,
            secret=task_result.result_secret,
            options=client_options.__dict__,
        )

        report_computed_task.task_to_compute = task_to_compute

        history.add(
            msg=report_computed_task,
            node_id=self.key_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
        self.send(report_computed_task)

        # if the Concent is not available in the context of this subtask
        # we can only assume that `ReportComputedTask` above reaches
        # the Requestor safely

        if not task_to_compute.concent_enabled:
            return

        # we're preparing the `ForceReportComputedTask` here and
        # scheduling the dispatch of that message for later
        # (with an implicit delay in the concent service's `submit` method).
        #
        # though, should we receive the acknowledgement for
        # the `ReportComputedTask` sent above before the delay elapses,
        # the `ForceReportComputedTask` message to the Concent will be
        # cancelled and thus, never sent to the Concent.

        delayed_forcing_msg = message.ForceReportComputedTask(
            report_computed_task=report_computed_task,
            result_hash='sha1:' + task_result.package_sha1
        )
        logger.debug('[CONCENT] ForceReport: %s', delayed_forcing_msg)

        self.concent_service.submit_task_message(
            task_result.subtask_id,
            delayed_forcing_msg,
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

    def send_result_rejected(self, subtask_id, reason):
        """
        Inform that result doesn't pass the verification or that
        the verification was not possible

        :param str subtask_id: subtask that has wrong result
        :param SubtaskResultsRejected.Reason reason: the rejection reason
        """

        task_id = self._subtask_to_task(subtask_id, Actor.Requestor)

        report_computed_task = get_task_message(
            'ReportComputedTask',
            task_id,
            subtask_id,
        )

        self.send(message.tasks.SubtaskResultsRejected(
            report_computed_task=report_computed_task,
            reason=reason,
        ))

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
        self.task_manager.got_wants_to_compute(msg.task_id, self.key_id,
                                               msg.node_name)
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
            task = self.task_manager.tasks[ctd['task_id']]
            task_state = self.task_manager.tasks_states[ctd['task_id']]
            msg = message.tasks.TaskToCompute(
                compute_task_def=ctd,
                requestor_id=task.header.task_owner.key,
                requestor_public_key=task.header.task_owner.key,
                requestor_ethereum_public_key=task.header.task_owner.key,
                provider_id=self.key_id,
                provider_public_key=self.key_id,
                provider_ethereum_public_key=self.key_id,
                package_hash='sha1:' + task_state.package_hash,
                # for now, we're assuming the Concent
                # is always in use
                concent_enabled=self.concent_service.enabled,
            )
            history.add(
                msg=msg,
                node_id=self.key_id,
                local_role=Actor.Requestor,
                remote_role=Actor.Provider,
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
        ctd = msg.compute_task_def
        if ctd is None:
            logger.debug('TaskToCompute without ctd: %r', msg)
            self.task_computer.session_closed()
            self.dropped()
            return
        if self._check_ctd_params(ctd)\
                and self._set_env_params(ctd)\
                and self.task_manager.comp_task_keeper.receive_subtask(ctd):
            self.task_server.add_task_session(
                ctd['subtask_id'], self
            )
            if self.task_computer.task_given(ctd):
                return
        self.send(
            message.CannotComputeTask(
                subtask_id=ctd['subtask_id'],
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
        if self.check_provider_for_subtask(msg.subtask_id):
            self.task_manager.task_computation_failure(
                msg.subtask_id,
                'Task computation rejected: {}'.format(msg.reason)
            )
        self.dropped()

    @history.provider_history
    def _react_to_cannot_assign_task(self, msg):
        if not self.check_requestor_for_task(msg.task_id):
            self.dropped()
            return
        self.task_computer.task_request_rejected(msg.task_id, msg.reason)
        self.task_server.remove_task_header(msg.task_id)
        self.task_manager.comp_task_keeper.request_failure(msg.task_id)
        self.task_computer.session_closed()
        self.dropped()

    @history.requestor_history
    def _react_to_report_computed_task(self, msg):
        subtask_id = msg.subtask_id
        if not self.check_provider_for_subtask(subtask_id):
            self.dropped()
            return

        if msg.task_to_compute is None:
            logger.warning('Did not receive task_to_compute: %r', msg)
            self.dropped()
            return

        returned_msg = concent_helpers.process_report_computed_task(
            msg=msg,
            ecc=self.task_server.keys_auth.ecc,
            task_header_keeper=self.task_server.task_keeper,
        )
        self.send(returned_msg)
        if not isinstance(returned_msg, message.concents.AckReportComputedTask):
            self.dropped()
            return

        self.task_server.receive_subtask_computation_time(
            subtask_id,
            msg.computation_time
        )

        self.result_owner = EthAccountInfo(
            msg.key_id,
            msg.node_name,
            p2p_node.Node.from_dict(msg.node_info),
            msg.eth_account
        )

        task_id = self.task_manager.subtask2task_mapping.get(subtask_id, None)
        task = self.task_manager.tasks.get(task_id, None)
        output_dir = task.tmp_dir if hasattr(task, 'tmp_dir') else None

        client_options = self.task_server.get_download_options(msg.options,
                                                               task_id)
        logger.debug(
            "Task result hash received: %r from %r:%r (options: %r)",
            msg.multihash,
            self.address,
            self.port,
            client_options
        )

        fgtr = message.concents.ForceGetTaskResult(
            report_computed_task=msg
        )

        def on_success(extracted_pkg, *args, **kwargs):
            extra_data = extracted_pkg.to_extra_data()
            logger.debug("Task result extracted %r",
                         extracted_pkg.__dict__)
            self.result_received(extra_data)
            self.concent_service.cancel_task_message(
                msg.subtask_id, 'ForceGetTaskResult')

        def on_error(exc, *args, **kwargs):
            logger.warning("Task result error: %s (%s)", subtask_id,
                           exc or "unspecified")

            if not msg.task_to_compute.concent_enabled:
                # in case of resources failure, if we're not using the Concent
                # we're immediately sending a rejection message to the Provider
                self._reject_subtask_result(
                    subtask_id,
                    reason=message.tasks.SubtaskResultsRejected.REASON
                    .ResourcesFailure
                )

                self.task_manager.task_computation_failure(
                    subtask_id,
                    'Error downloading task result'
                )
            else:
                # otherwise, we're resorting to mediation through the Concent
                # to obtain the task results
                logger.debug('[CONCENT] sending ForceGetTaskResult: %s', fgtr)
                self.concent_service.submit_task_message(subtask_id, fgtr)

            self.dropped()

        # submit a delayed `ForceGetTaskResult` to the Concent
        # in case the download exceeds the maximum allowable download time.
        # however, if it succeeds, the message will get cancelled
        # in the success handler

        self.concent_service.submit_task_message(
            subtask_id, fgtr, msg_helpers.maximum_download_time(msg.size))

        self.task_manager.task_result_incoming(subtask_id)
        self.task_manager.task_result_manager.pull_package(
            msg.multihash,
            task_id,
            subtask_id,
            msg.secret,
            success=on_success,
            error=on_error,
            client_options=client_options,
            output_dir=output_dir
        )

    def _react_to_get_resource(self, msg):
        # self.last_resource_msg = msg
        resources = self.task_server.get_resources(msg.task_id)
        options = self.task_server.get_share_options(
            task_id=msg.task_id,
            address=self.address
        )

        self.send(message.ResourceList(
            resources=resources,
            options=options.__dict__,  # This slot will be used in #1768
        ))

    @history.provider_history
    def _react_to_subtask_result_accepted(self, msg):
        if msg.task_to_compute is None:
            logger.info(
                'Empty task_to_compute in %s. Disconnecting: %r',
                msg,
                self.key_id,
            )
            self.disconnect(message.Disconnect.REASON.BadProtocol)
            return
        if not self.check_requestor_for_subtask(msg.subtask_id):
            self.dropped()
            return
        self.task_server.subtask_accepted(
            self.key_id,
            msg.subtask_id,
            msg.payment_ts,
        )
        self.concent_service.cancel_task_message(
            msg.subtask_id,
            'ForceSubtaskResults',
        )
        self.dropped()

    @history.provider_history
    def _react_to_subtask_results_rejected(self, msg):
        subtask_id = msg.report_computed_task.subtask_id
        if not self.check_requestor_for_subtask(subtask_id):
            self.dropped()
            return
        self.task_server.subtask_rejected(
            subtask_id=subtask_id,
        )
        self.concent_service.cancel_task_message(
            subtask_id,
            'ForceSubtaskResults',
        )
        self.dropped()

    def _react_to_task_failure(self, msg):
        if self.check_provider_for_subtask(msg.subtask_id):
            self.task_server.subtask_failure(msg.subtask_id, msg.err)
        self.dropped()

    def _react_to_resource_list(self, msg):
        resource_manager = self.task_server.client.resource_server.resource_manager  # noqa
        resources = resource_manager.from_wire(msg.resources)

        client_options = self.task_server.get_download_options(msg.options,
                                                               self.task_id)

        self.task_computer.wait_for_resources(self.task_id, resources)
        self.task_server.pull_resources(self.task_id, resources,
                                        client_options=client_options)

    def _react_to_hello(self, msg):
        if not self.conn.opened:
            return
        send_hello = False

        if self.key_id is None:
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

        if not KeysAuth.is_pubkey_difficult(
                self.key_id,
                self.task_server.config_desc.key_difficulty):
            logger.info(
                "Key from %r (%s:%d) is not difficult enough (%d < %d).",
                msg.node_info.node_name, self.address, self.port,
                KeysAuth.get_difficulty(self.key_id),
                self.task_server.config_desc.key_difficulty)
            self.disconnect(message.Disconnect.REASON.KeyNotDifficult)
            return

        if send_hello:
            self.send_hello()
        self.send(
            message.RandVal(rand_val=msg.rand_val),
            send_unverified=True
        )

    def _react_to_rand_val(self, msg):
        # If we disconnect in react_to_hello, we still might get the RandVal
        # message
        if self.key_id is None:
            return

        if self.rand_val == msg.rand_val:
            self.verified = True
            self.task_server.verified_conn(self.conn_id, )
            for msg_ in self.msgs_to_send:
                self.send(msg_)
            self.msgs_to_send = []
        else:
            self.disconnect(message.Disconnect.REASON.Unverified)

    def _react_to_start_session_response(self, msg):
        self.task_server.respond_to(self.key_id, self, msg.conn_id)

    @history.provider_history
    def _react_to_ack_report_computed_task(self, msg):
        keeper = self.task_manager.comp_task_keeper
        sender_is_owner = keeper.check_task_owner_by_subtask(
            self.key_id,
            msg.subtask_id,
        )
        if not sender_is_owner:
            logger.warning("Requestor '%r' acknowledged a computed task report "
                           "of an unknown task (subtask_id='%s')",
                           self.key_id, msg.subtask_id)
            return

        logger.debug("Requestor '%r' accepted the computed subtask '%r' "
                     "report", self.key_id, msg.subtask_id)

        self.concent_service.cancel_task_message(
            msg.subtask_id, 'ForceReportComputedTask')

        delayed_forcing_msg = message.concents.ForceSubtaskResults(
            ack_report_computed_task=msg,
        )
        logger.debug('[CONCENT] ForceResults: %s', delayed_forcing_msg)
        report_computed_task = get_task_message(
            'ReportComputedTask',
            msg.task_id,
            msg.subtask_id,
        )
        if report_computed_task is None:
            logger.warning(
                '[CONCENT] Can`t delay send %r.'
                ' ForceReportComputedTask not found; delay unknown',
                delayed_forcing_msg,
            )
            return
        self.concent_service.submit_task_message(
            subtask_id=msg.subtask_id,
            msg=delayed_forcing_msg,
            delay=msg_helpers.maximum_results_patience(report_computed_task),
        )

    @history.provider_history
    def _react_to_reject_report_computed_task(self, msg):
        keeper = self.task_manager.comp_task_keeper
        if keeper.check_task_owner_by_subtask(self.key_id, msg.subtask_id):
            logger.info("Requestor '%r' rejected the computed subtask '%r' "
                        "report", self.key_id, msg.subtask_id)

            self.concent_service.cancel_task_message(
                msg.subtask_id, 'ForceReportComputedTask')
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

    def check_provider_for_subtask(self, subtask_id) -> bool:
        node_id = self.task_manager.get_node_id_for_subtask(subtask_id)
        if node_id != self.key_id:
            logger.warning('Received message about subtask %r from diferrent '
                           'node %r than expected %r', subtask_id,
                           self.key_id, node_id)
            return False
        return True

    def check_requestor_for_task(self, task_id, additional_msg="") -> bool:
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(
            task_id)
        if node_id != self.key_id:
            logger.warning('Received message about task %r from diferrent '
                           'node %r than expected %r. %s', task_id,
                           self.key_id, node_id, additional_msg)
            return False
        return True

    def check_requestor_for_subtask(self, subtask_id) -> bool:
        task_id = self.task_manager.comp_task_keeper.get_task_id_for_subtask(
            subtask_id)
        return self.check_requestor_for_task(task_id, "Subtask %r" % subtask_id)

    def _check_ctd_params(self, ctd):
        header = self.task_manager.comp_task_keeper.get_task_header(
            ctd['task_id'])
        reasons = message.CannotComputeTask.REASON
        if header.task_owner_key_id != self.key_id\
                or header.task_owner.key != self.key_id:
            self.err_msg = reasons.WrongKey
            return False
        if not tcpnetwork.SocketAddress.is_proper_address(
                header.task_owner_address,
                header.task_owner_port):
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
        for image_dict in ctd['docker_images']:
            image = DockerImage(**image_dict)
            for env_image in env.docker_images:
                if env_image.cmp_name_and_tag(image):
                    ctd['docker_images'] = [image_dict]
                    return True

        reasons = message.CannotComputeTask.REASON
        self.err_msg = reasons.WrongDockerImages
        return False

    def __set_msg_interpretations(self):
        self._interpretation.update({
            message.WantToComputeTask.TYPE: self._react_to_want_to_compute_task,
            message.TaskToCompute.TYPE: self._react_to_task_to_compute,
            message.CannotAssignTask.TYPE: self._react_to_cannot_assign_task,
            message.CannotComputeTask.TYPE: self._react_to_cannot_compute_task,
            message.ReportComputedTask.TYPE:
                self._react_to_report_computed_task,
            message.GetResource.TYPE: self._react_to_get_resource,
            message.ResourceList.TYPE: self._react_to_resource_list,
            message.tasks.SubtaskResultsAccepted.TYPE:
                self._react_to_subtask_result_accepted,
            message.tasks.SubtaskResultsRejected.TYPE:
                self._react_to_subtask_results_rejected,
            message.TaskFailure.TYPE: self._react_to_task_failure,
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
