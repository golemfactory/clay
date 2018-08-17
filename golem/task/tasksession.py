import datetime
import functools
import logging
import os
import time

from golem_messages import message
from golem_messages import helpers as msg_helpers

from golem.core.common import HandleAttributeError
from golem.core.keysauth import KeysAuth
from golem.core.simpleserializer import CBORSerializer
from golem.core import variables
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.model import Actor
from golem.network import history
from golem.network.concent import helpers as concent_helpers
from golem.network.transport import tcpnetwork
from golem.network.transport.session import BasicSafeSession
from golem.resource.resourcehandshake import ResourceHandshakeSessionMixin
from golem.task import taskkeeper
from golem.task.server import helpers as task_server_helpers
from golem.task.taskbase import ResultType
from golem.task.taskstate import TaskState

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

    msg = history.get(
        message_class_name=message_class_name,
        task_id=task_id,
        subtask_id=subtask_id,
    )
    if msg is None:
        logger.debug(
            '%s%s message not found for task %r, subtask: %r',
            log_prefix or '',
            message_class_name,
            task_id,
            subtask_id,
        )
    return msg


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

        if not subtask_id:
            logger.error("No subtask_id value in extra_data for received data ")
            self.dropped()

        def send_verification_failure():
            self._reject_subtask_result(
                subtask_id,
                reason=message.tasks.SubtaskResultsRejected.REASON
                .VerificationNegative
            )

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

            eth_address = get_task_message(
                'ReportComputedTask',
                task_id,
                subtask_id,
            ).eth_account
            payment_processed_ts = self.task_server.accept_result(
                subtask_id,
                self.key_id,
                eth_address,
            )

            response_msg = message.tasks.SubtaskResultsAccepted(
                task_to_compute=task_to_compute,
                payment_ts=payment_processed_ts,
            )
            self.send(response_msg)
            history.add(
                response_msg,
                node_id=task_to_compute.provider_id,
                local_role=Actor.Requestor,
                remote_role=Actor.Provider,
            )
            self.dropped()

        self.task_manager.computed_task_received(
            subtask_id,
            result,
            result_type,
            verification_finished
        )

    def _reject_subtask_result(self, subtask_id, reason):
        logger.debug('_reject_subtask_result(%r, %r)', subtask_id, reason)

        self.task_server.reject_result(subtask_id, self.key_id)
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
            task_to_compute=task_to_compute,
            result_type=task_result.result_type,
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

        task_id = self._subtask_to_task(subtask_id, Actor.Provider)

        task_to_compute = get_task_message(
            'TaskToCompute',
            task_id,
            subtask_id,
        )

        if not task_to_compute:
            logger.warning("Could not retrieve TaskToCompute"
                           " for subtask_id: %s, task_id: %s",
                           subtask_id, task_id)
            return

        self.send(
            message.TaskFailure(
                task_to_compute=task_to_compute,
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

        response_msg = message.tasks.SubtaskResultsRejected(
            report_computed_task=report_computed_task,
            reason=reason,
        )
        self.send(response_msg)
        history.add(
            response_msg,
            node_id=report_computed_task.task_to_compute.provider_id,
            local_role=Actor.Requestor,
            remote_role=Actor.Provider,
        )

    def send_hello(self):
        """ Send first hello message, that should begin the communication """
        self.send(
            message.Hello(
                client_key_id=self.task_server.get_key_id(),
                rand_val=self.rand_val,
                proto_id=variables.PROTOCOL_CONST.ID,
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
        reasons = message.CannotAssignTask.REASON

        if msg.concent_enabled and not self.concent_service.enabled:
            self.send(
                message.CannotAssignTask(
                    task_id=msg.task_id,
                    reason=reasons.ConcentDisabled,
                )
            )
            self.dropped()
            return

        self.task_manager.got_wants_to_compute(msg.task_id, self.key_id,
                                               msg.node_name)
        if self.task_server.should_accept_provider(
                self.key_id, msg.task_id, msg.perf_index,
                msg.max_resource_size, msg.max_memory_size, msg.num_cores):

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

        if wrong_task:
            self.send(
                message.CannotAssignTask(
                    task_id=msg.task_id,
                    reason=reasons.NotMyTask,
                )
            )
            self.dropped()
            return

        if ctd:
            task = self.task_manager.tasks[ctd['task_id']]
            task_state: TaskState = self.task_manager.tasks_states[
                ctd['task_id']]
            price = taskkeeper.compute_subtask_value(
                task.header.max_price,
                task.header.subtask_timeout,
            )
            ttc = message.tasks.TaskToCompute(
                compute_task_def=ctd,
                requestor_id=task.header.task_owner.key,
                requestor_public_key=task.header.task_owner.key,
                requestor_ethereum_public_key=task.header.task_owner.key,
                provider_id=self.key_id,
                provider_public_key=self.key_id,
                provider_ethereum_public_key=self.key_id,
                package_hash='sha1:' + task_state.package_hash,
                concent_enabled=msg.concent_enabled,
                price=price,
                size=task_state.package_size
            )
            self.task_manager.set_subtask_value(
                subtask_id=ttc.subtask_id,
                price=price,
            )
            history.add(
                msg=ttc,
                node_id=self.key_id,
                local_role=Actor.Requestor,
                remote_role=Actor.Provider,
            )
            self.send(ttc)
            return

        if wait:
            self.send(message.WaitingForResults())
            return

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

        def _cannot_compute(reason):
            logger.debug("Cannot %r", reason)
            self.send(
                message.tasks.CannotComputeTask(
                    task_to_compute=msg,
                    reason=reason,
                ),
            )
            self.task_computer.session_closed()
            self.dropped()

        reasons = message.CannotComputeTask.REASON

        if self.concent_service.enabled and not msg.concent_enabled:
            # Provider requires concent if it's enabed locally
            _cannot_compute(reasons.ConcentRequired)
            return
        if not self.concent_service.enabled and msg.concent_enabled:
            # We can't provide what requestors wants
            _cannot_compute(reasons.ConcentDisabled)
            return

        number_of_subtasks = self.task_manager.tasks[msg.task_id]\
            .get_total_tasks()
        total_task_price = msg.price * number_of_subtasks
        transaction_system = self.task_server.client.transaction_system
        requestors_gntb_balance = transaction_system.balance(
            account_address=msg.requestor_ethereum_public_key,
        )
        if requestors_gntb_balance < total_task_price:
            _cannot_compute(reasons.InsufficientBalance)
            return
        if msg.concent_enabled:
            requestors_deposit_value = transaction_system.concent_balance(
                account_address=msg.requestor_ethereum_public_key,
            )
            if requestors_deposit_value < (total_task_price * 2):
                _cannot_compute(reasons.InsufficientDeposit)
                return
            requestors_deposit_timelock = transaction_system.concent_timelock(
                account_address=msg.requestor_ethereum_public_key,
            )
            expected_timelock = time.time() \
                + variables.CONCENT_MIN_DEPOSIT_TIMELOCK
            if requestors_deposit_timelock < expected_timelock:
                _cannot_compute(reasons.TooShortDeposit)
                return

        if self._check_ctd_params(ctd)\
                and self._set_env_params(ctd)\
                and self.task_manager.comp_task_keeper.receive_subtask(msg):
            self.task_server.add_task_session(
                ctd['subtask_id'], self
            )
            if self.task_computer.task_given(ctd):
                return
        _cannot_compute(self.err_msg)

    def _react_to_waiting_for_results(self, _):
        self.task_computer.session_closed()
        if not self.msgs_to_send:
            self.disconnect(message.Disconnect.REASON.NoMoreMessages)

    def _react_to_cannot_compute_task(self, msg):
        if self.check_provider_for_subtask(msg.subtask_id):
            logger.info(
                "Provider can't compute subtask: %r Reason: %r",
                msg.subtask_id,
                msg.reason,
            )
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
        )
        self.send(returned_msg)
        if not isinstance(returned_msg, message.tasks.AckReportComputedTask):
            self.dropped()
            return

        def after_success():
            self.disconnect(message.Disconnect.REASON.NoMoreMessages)

        def after_error():
            if msg.task_to_compute.concent_enabled:
                return
            # in case of resources failure, if we're not using the Concent
            # we're immediately sending a rejection message to the Provider
            self._reject_subtask_result(
                subtask_id,
                reason=message.tasks.SubtaskResultsRejected.REASON
                .ResourcesFailure,
            )
            self.task_manager.task_computation_failure(
                subtask_id,
                'Error downloading task result'
            )
            self.dropped()

        task_server_helpers.computed_task_reported(
            task_server=self.task_server,
            report_computed_task=msg,
            after_success=after_success,
            after_error=after_error,
        )

        logger.debug(
            "Task result hash received: %r from %r:%r",
            msg.multihash,
            self.address,
            self.port,
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
        self.concent_service.cancel_task_message(
            msg.subtask_id,
            'ForceSubtaskResults',
        )
        self.task_server.subtask_accepted(
            self.key_id,
            msg.subtask_id,
            msg.payment_ts,
        )
        self.dropped()

    @history.provider_history
    def _react_to_subtask_results_rejected(
            self, msg: message.tasks.SubtaskResultsRejected):
        subtask_id = msg.report_computed_task.subtask_id
        if not self.check_requestor_for_subtask(subtask_id):
            self.dropped()
            return
        self.concent_service.cancel_task_message(
            subtask_id,
            'ForceSubtaskResults',
        )

        if msg.task_to_compute.concent_enabled:
            # if the Concent is enabled for this subtask, as a provider,
            # knowing that we had done a proper job of computing it,
            # we are delegating the verification to the Concent so that
            # we can be paid for this subtask despite the rejection

            amount, expected = msg_helpers.provider_deposit_amount(
                subtask_price=msg.task_to_compute.price,
            )

            def ask_for_verification(_):
                srv = message.concents.SubtaskResultsVerify(
                    subtask_results_rejected=msg
                )

                self.concent_service.submit_task_message(
                    subtask_id=msg.subtask_id,
                    msg=srv,
                )

            self.task_server.client.transaction_system.concent_deposit(
                required=amount,
                expected=expected,
            ).addCallback(ask_for_verification)

        else:
            self.task_server.subtask_rejected(
                sender_node_id=self.key_id,
                subtask_id=subtask_id,
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

        if msg.proto_id != variables.PROTOCOL_CONST.ID:
            logger.info(
                "Task protocol version mismatch %r (msg) vs %r (local)",
                msg.proto_id,
                variables.PROTOCOL_CONST.ID
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
        ttc_deadline = datetime.datetime.utcfromtimestamp(
            msg.task_to_compute.compute_task_def['deadline']
        )
        svt = msg_helpers.subtask_verification_time(msg.report_computed_task)
        delay = ttc_deadline + svt - datetime.datetime.utcnow()
        self.concent_service.submit_task_message(
            subtask_id=msg.subtask_id,
            msg=delayed_forcing_msg,
            delay=delay,
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
        owner = header.task_owner

        reasons = message.CannotComputeTask.REASON
        if owner.key != self.key_id:
            self.err_msg = reasons.WrongKey
            return False

        addresses = [
            (owner.pub_addr, owner.pub_port),
            (owner.prv_addr, owner.prv_port)
        ]

        if not any(tcpnetwork.SocketAddress.is_proper_address(addr, port)
                   for addr, port in addresses):
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
            message.tasks.AckReportComputedTask.TYPE:
                self._react_to_ack_report_computed_task,
            message.tasks.RejectReportComputedTask.TYPE:
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
