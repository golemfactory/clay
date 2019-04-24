# pylint: disable=too-many-lines

import copy
import datetime
import enum
import logging
import time
from typing import TYPE_CHECKING, List, Optional

from ethereum.utils import denoms
from golem_messages import exceptions as msg_exceptions
from golem_messages import helpers as msg_helpers
from golem_messages import message
from golem_messages import utils as msg_utils
from pydispatch import dispatcher

import golem
from golem.core import common
from golem.core.keysauth import KeysAuth
from golem.core import variables
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.marketplace import scale_price, Offer, OfferPool
from golem.model import Actor
from golem.network import history
from golem.network import nodeskeeper
from golem.network.concent import helpers as concent_helpers
from golem.network.transport import tcpnetwork
from golem.network.transport.session import BasicSafeSession
from golem.ranking.manager.database_manager import (
    get_provider_efficacy,
    get_provider_efficiency,
)
from golem.resource.resourcehandshake import ResourceHandshakeSessionMixin
from golem.task import exceptions
from golem.task import taskkeeper
from golem.task.server import helpers as task_server_helpers

if TYPE_CHECKING:
    from .taskcomputer import TaskComputer  # noqa pylint:disable=unused-import
    from .taskmanager import TaskManager  # noqa pylint:disable=unused-import
    from .taskserver import TaskServer  # noqa pylint:disable=unused-import

logger = logging.getLogger(__name__)


def drop_after_attr_error(*args, **_):
    logger.warning("Attribute error occured(1)", exc_info=True)
    args[0].dropped()


def call_task_computer_and_drop_after_attr_error(*args, **_):
    logger.warning("Attribute error occured(2)", exc_info=True)
    args[0].task_computer.session_closed()
    args[0].dropped()


def get_task_message(
        message_class_name,
        node_id,
        task_id,
        subtask_id,
        log_prefix=None):
    if log_prefix:
        log_prefix = '%s ' % log_prefix

    msg = history.get(
        message_class_name=message_class_name,
        node_id=node_id,
        subtask_id=subtask_id,
        task_id=task_id
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


def copy_and_sign(msg: message.base.Message, private_key) \
        -> message.base.Message:
    """Returns signed shallow copy of message

    Copy is made only if original is unsigned.
    """
    if msg.sig is None:
        # If message is delayed in msgs_to_send then will
        # overcome this by making a signed copy
        msg = copy.copy(msg)
        msg.sign_message(private_key)
    return msg


def check_docker_images(
        ctd: message.ComputeTaskDef,
        env: DockerEnvironment,
):
    for image_dict in ctd['docker_images']:
        image = DockerImage(**image_dict)
        for env_image in env.docker_images:
            if env_image.cmp_name_and_tag(image):
                ctd['docker_images'] = [image_dict]
                return

    reasons = message.tasks.CannotComputeTask.REASON
    raise exceptions.CannotComputeTask(reason=reasons.WrongDockerImages)


class RequestorCheckResult(enum.Enum):
    OK = enum.auto()
    MISMATCH = enum.auto()
    NOT_FOUND = enum.auto()


class TaskSession(BasicSafeSession, ResourceHandshakeSessionMixin):
    """ Session for Golem task network """

    handle_attr_error = common.HandleAttributeError(drop_after_attr_error)
    handle_attr_error_with_task_computer = common.HandleAttributeError(
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
        self.conn_id = None  # connection id
        # set in TaskServer.new_session_prepare()
        self.key_id: Optional[str] = None
        # messages waiting to be send (because connection hasn't been
        # verified yet)
        self.msgs_to_send = []
        self.__set_msg_interpretations()

    @property
    def task_server(self) -> 'TaskServer':
        return self.conn.server

    @property
    def task_manager(self) -> 'TaskManager':
        return self.task_server.task_manager

    @property
    def task_computer(self) -> 'TaskComputer':
        return self.task_server.task_computer

    @property
    def concent_service(self):
        return self.task_server.client.concent_service

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
        self.task_server.remove_task_session(self)

    #######################
    # SafeSession methods #
    #######################

    @property
    def my_private_key(self) -> bytes:
        return self.task_server.keys_auth._private_key  # noqa pylint: disable=protected-access

    @property
    def my_public_key(self) -> bytes:
        return self.task_server.keys_auth.public_key

    ###################################
    # IMessageHistoryProvider methods #
    ###################################

    def _subtask_to_task(self, sid, local_role):
        if local_role == Actor.Provider:
            return self.task_manager.comp_task_keeper.subtask_to_task.get(sid)
        elif local_role == Actor.Requestor:
            return self.task_manager.subtask2task_mapping.get(sid)
        return None

    #######################
    # FileSession methods #
    #######################

    def result_received(self, subtask_id: str, result_files: List[str]):
        """ Inform server about received result
        """
        def send_verification_failure():
            self._reject_subtask_result(
                subtask_id,
                reason=message.tasks.SubtaskResultsRejected.REASON
                .VerificationNegative
            )

        def verification_finished():
            logger.debug("Verification finished handler.")
            if not self.task_manager.verify_subtask(subtask_id):
                logger.debug("Verification failure. subtask_id=%r", subtask_id)
                send_verification_failure()
                self.dropped()
                return

            task_id = self._subtask_to_task(subtask_id, Actor.Requestor)

            report_computed_task = get_task_message(
                message_class_name='ReportComputedTask',
                node_id=self.key_id,
                task_id=task_id,
                subtask_id=subtask_id
            )
            task_to_compute = report_computed_task.task_to_compute

            # FIXME Remove in 0.20
            if not task_to_compute.sig:
                task_to_compute.sign_message(self.my_private_key)

            config_desc = self.task_server.config_desc
            if config_desc.disallow_node_timeout_seconds is not None:
                # Experimental feature. Try to spread subtasks fairly amongst
                # providers.
                self.task_server.disallow_node(
                    node_id=task_to_compute.provider_id,
                    timeout_seconds=config_desc.disallow_node_timeout_seconds,
                    persist=False,
                )
            if config_desc.disallow_ip_timeout_seconds is not None:
                # Experimental feature. Try to spread subtasks fairly amongst
                # providers.
                self.task_server.disallow_ip(
                    ip=self.address,
                    timeout_seconds=config_desc.disallow_ip_timeout_seconds,
                )

            payment_processed_ts = self.task_server.accept_result(
                subtask_id,
                self.key_id,
                task_to_compute.provider_ethereum_address,
                task_to_compute.price,
            )

            response_msg = message.tasks.SubtaskResultsAccepted(
                report_computed_task=report_computed_task,
                payment_ts=payment_processed_ts,
            )
            self.send(response_msg)
            history.add(
                copy_and_sign(
                    msg=response_msg,
                    private_key=self.my_private_key,
                ),
                node_id=task_to_compute.provider_id,
                local_role=Actor.Requestor,
                remote_role=Actor.Provider,
            )
            self.dropped()

        self.task_manager.computed_task_received(
            subtask_id,
            result_files,
            verification_finished
        )

    def _reject_subtask_result(self, subtask_id, reason):
        logger.debug('_reject_subtask_result(%r, %r)', subtask_id, reason)

        self.task_server.reject_result(subtask_id, self.key_id)
        self.send_result_rejected(subtask_id, reason)

    # TODO address, port and eth_account should be in node_info
    # (or shouldn't be here at all). Issue #2403
    def send_report_computed_task(
            self,
            task_result,
            address,
            port,
            node_info):
        """ Send task results after finished computations
        :param WaitingTaskResult task_result: finished computations result
                                              with additional information
        :param str address: task result owner address
        :param int port: task result owner port
        :param Node node_info: information about this node
        :return:
        """
        extra_data = []

        node_name = self.task_server.get_node_name()

        task_to_compute = get_task_message(
            message_class_name='TaskToCompute',
            node_id=self.key_id,
            task_id=task_result.task_id,
            subtask_id=task_result.subtask_id
        )

        if not task_to_compute:
            return

        client_options = self.task_server.get_share_options(task_result.task_id,
                                                            self.address)

        report_computed_task = message.tasks.ReportComputedTask(
            task_to_compute=task_to_compute,
            node_name=node_name,
            address=address,
            port=port,
            key_id=self.task_server.get_key_id(),
            node_info=node_info.to_dict(),
            extra_data=extra_data,
            size=task_result.result_size,
            package_hash='sha1:' + task_result.package_sha1,
            multihash=task_result.result_hash,
            secret=task_result.result_secret,
            options=client_options.__dict__,
        )

        self.send(report_computed_task)
        report_computed_task = copy_and_sign(
            msg=report_computed_task,
            private_key=self.my_private_key,
        )
        history.add(
            msg=report_computed_task,
            node_id=self.key_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

        # if the Concent is not available in the context of this subtask
        # we can only assume that `ReportComputedTask` above reaches
        # the Requestor safely

        if not task_to_compute.concent_enabled:
            logger.debug(
                "Concent not enabled for this task, "
                "skipping `ForceReportComputedTask`. "
                "task_id=%r, "
                "subtask_id=%r, ",
                task_to_compute.task_id,
                task_to_compute.subtask_id,
            )
            return

        # we're preparing the `ForceReportComputedTask` here and
        # scheduling the dispatch of that message for later
        # (with an implicit delay in the concent service's `submit` method).
        #
        # though, should we receive the acknowledgement for
        # the `ReportComputedTask` sent above before the delay elapses,
        # the `ForceReportComputedTask` message to the Concent will be
        # cancelled and thus, never sent to the Concent.

        delayed_forcing_msg = message.concents.ForceReportComputedTask(
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
            message_class_name='TaskToCompute',
            node_id=self.key_id,
            task_id=task_id,
            subtask_id=subtask_id
        )

        if not task_to_compute:
            logger.warning("Could not retrieve TaskToCompute"
                           " for subtask_id: %s, task_id: %s",
                           subtask_id, task_id)
            return

        self.send(
            message.tasks.TaskFailure(
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
            message_class_name='ReportComputedTask',
            node_id=self.key_id,
            task_id=task_id,
            subtask_id=subtask_id
        )

        response_msg = message.tasks.SubtaskResultsRejected(
            report_computed_task=report_computed_task,
            reason=reason,
        )
        self.send(response_msg)
        response_msg = copy_and_sign(
            msg=response_msg,
            private_key=self.my_private_key,
        )
        history.add(
            response_msg,
            node_id=report_computed_task.task_to_compute.provider_id,
            local_role=Actor.Requestor,
            remote_role=Actor.Provider,
        )

    def send_hello(self):
        """ Send first hello message, that should begin the communication """
        self.send(
            message.base.Hello(
                client_key_id=self.task_server.get_key_id(),
                client_ver=golem.__version__,
                rand_val=self.rand_val,
                proto_id=variables.PROTOCOL_CONST.ID,
                node_info=self.task_server.client.node,
            ),
            send_unverified=True
        )

    def send_start_session_response(self, conn_id):
        """Inform that this session was started as an answer for a request
           to start task session
        :param uuid conn_id: connection id for reference
        """
        self.send(message.tasks.StartSessionResponse(conn_id=conn_id))

    #########################
    # Reactions to messages #
    #########################

    # pylint: disable=too-many-return-statements
    def _react_to_want_to_compute_task(self, msg):
        def _cannot_assign(reason):
            logger.debug("Cannot assign task: %r", reason)
            self.send(
                message.tasks.CannotAssignTask(
                    task_id=msg.task_id,
                    reason=reason,
                ),
            )
            self.dropped()

        reasons = message.tasks.CannotAssignTask.REASON

        if msg.concent_enabled and not self.concent_service.enabled:
            _cannot_assign(reasons.ConcentDisabled)
            return

        if not self.task_manager.is_my_task(msg.task_id):
            _cannot_assign(reasons.NotMyTask)
            return

        try:
            msg.task_header.verify(self.my_public_key)
        except msg_exceptions.InvalidSignature:
            _cannot_assign(reasons.NotMyTask)
            return

        node_name_id = common.node_info_str(msg.node_name, self.key_id)
        logger.info("Received offer to compute. task_id=%r, node=%r",
                    msg.task_id, node_name_id)

        logger.debug(
            "Calling `task_manager.got_wants_to_compute`,"
            "task_id=%s, node=%s",
            msg.task_id,
            node_name_id,
        )
        self.task_manager.got_wants_to_compute(msg.task_id, self.key_id,
                                               msg.node_name)

        logger.debug(
            "WTCT processing... task_id=%s, node=%s",
            msg.task_id,
            node_name_id,
        )

        task_server_ok = self.task_server.should_accept_provider(
            self.key_id,
            self.address,
            msg.node_name,
            msg.task_id,
            msg.perf_index,
            msg.max_resource_size,
            msg.max_memory_size)

        logger.debug(
            "Task server ok? should_accept_provider=%s task_id=%s node=%s",
            task_server_ok,
            msg.task_id,
            node_name_id,
        )

        if not task_server_ok:
            _cannot_assign(reasons.NoMoreSubtasks)
            return

        if not self.task_manager.check_next_subtask(
                msg.task_id, msg.price):
            logger.debug(
                "check_next_subtask False. task_id=%s, node=%s",
                msg.task_id,
                node_name_id,
            )
            _cannot_assign(reasons.NoMoreSubtasks)
            return

        if self.task_manager.task_finished(msg.task_id):
            logger.debug(
                "TaskFinished. task_id=%s, provider=%s",
                msg.task_id,
                node_name_id,
            )
            _cannot_assign(reasons.TaskFinished)
            return

        if self.task_manager.should_wait_for_node(msg.task_id, self.key_id):
            logger.warning("Can not accept offer: Still waiting on results."
                           "task_id=%r, node=%r", msg.task_id, node_name_id)
            task = self.task_manager.tasks[msg.task_id]
            subtasks = task.get_finishing_subtasks(
                node_id=self.key_id,
            )
            previous_ttc = get_task_message(
                message_class_name='TaskToCompute',
                node_id=self.key_id,
                task_id=msg.task_id,
                subtask_id=subtasks[0]['subtask_id'],
            )
            self.send(
                message.tasks.WaitingForResults(
                    task_to_compute=previous_ttc,
                ),
            )
            return

        if self._handshake_required(self.key_id):
            logger.warning('Can not accept offer: Resource handshake is'
                           ' required. task_id=%r, node=%r',
                           msg.task_id, node_name_id)
            self.task_server.start_handshake(self.key_id)
            return

        elif self._handshake_in_progress(self.key_id):
            logger.warning('Can not accept offer: Resource handshake is in'
                           ' progress. task_id=%r, node=%r',
                           msg.task_id, node_name_id)
            return

        def _offer_chosen(is_chosen: bool) -> None:
            if not self.conn.opened:
                logger.info(
                    "Provider disconnected. task_id=%r, node=%r",
                    msg.task_id,
                    node_name_id,
                )
                return

            if not is_chosen:
                logger.info(
                    "Provider not chosen by marketplace. task_id=%r, node=%r",
                    msg.task_id,
                    node_name_id,
                )
                _cannot_assign(reasons.NoMoreSubtasks)
                return

            logger.info("Offer confirmed, assigning subtask")
            ctd = self.task_manager.get_next_subtask(
                self.key_id, msg.node_name, msg.task_id, msg.perf_index,
                msg.price, msg.max_resource_size, msg.max_memory_size,
                self.address)

            ctd["resources"] = self.task_server.get_resources(msg.task_id)
            logger.debug(
                "CTD generated. task_id=%s, node=%s ctd=%s",
                msg.task_id,
                node_name_id,
                ctd,
            )

            if ctd is None:
                _cannot_assign(reasons.NoMoreSubtasks)
                return

            logger.info(
                "Subtask assigned. task_id=%r, node=%s, subtask_id=%r",
                msg.task_id,
                node_name_id,
                ctd["subtask_id"],
            )
            task = self.task_manager.tasks[ctd['task_id']]
            task_state = self.task_manager.tasks_states[ctd['task_id']]
            price = taskkeeper.compute_subtask_value(
                msg.price,
                task.header.subtask_timeout,
            )
            ttc = message.tasks.TaskToCompute(
                compute_task_def=ctd,
                want_to_compute_task=msg,
                requestor_id=task.header.task_owner.key,
                requestor_public_key=task.header.task_owner.key,
                requestor_ethereum_public_key=task.header.task_owner.key,
                provider_id=self.key_id,
                package_hash='sha1:' + task_state.package_hash,
                concent_enabled=msg.concent_enabled,
                price=price,
                size=task_state.package_size,
                resources_options=self.task_server.get_share_options(
                    ctd['task_id'], self.address).__dict__
            )
            ttc.generate_ethsig(self.my_private_key)
            self.send(ttc)
            history.add(
                msg=copy_and_sign(
                    msg=ttc,
                    private_key=self.my_private_key,
                ),
                node_id=self.key_id,
                local_role=Actor.Requestor,
                remote_role=Actor.Provider,
            )

        task = self.task_manager.tasks[msg.task_id]
        offer = Offer(
            scaled_price=scale_price(task.header.max_price, msg.price),
            reputation=get_provider_efficiency(self.key_id),
            quality=get_provider_efficacy(self.key_id).vector,
        )

        OfferPool.add(msg.task_id, offer).addCallback(_offer_chosen)

    # pylint: disable=too-many-return-statements
    @handle_attr_error_with_task_computer
    @history.provider_history
    def _react_to_task_to_compute(self, msg):
        ctd: Optional[message.tasks.ComputeTaskDef] = msg.compute_task_def
        want_to_compute_task = msg.want_to_compute_task
        if ctd is None or want_to_compute_task is None:
            logger.debug(
                'TaskToCompute without ctd or want_to_compute_task: %r', msg)
            self.task_computer.session_closed()
            self.dropped()
            return

        try:
            want_to_compute_task.verify_signature(
                self.task_server.keys_auth.ecc.raw_pubkey)
        except msg_exceptions.InvalidSignature:
            logger.debug(
                'WantToComputeTask attached to TaskToCompute is not signed '
                'with key: %r.', want_to_compute_task.provider_public_key)
            self.task_computer.session_closed()
            self.dropped()
            return

        dispatcher.send(
            signal='golem.message',
            event='received',
            message=msg
        )

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

        reasons = message.tasks.CannotComputeTask.REASON

        if self.task_computer.has_assigned_task():
            _cannot_compute(reasons.OfferCancelled)
            return

        if self.concent_service.enabled and not msg.concent_enabled:
            # Provider requires concent if it's enabed locally
            _cannot_compute(reasons.ConcentRequired)
            return
        if not self.concent_service.enabled and msg.concent_enabled:
            # We can't provide what requestor wants
            _cannot_compute(reasons.ConcentDisabled)
            return

        if not self._check_resource_size(msg.size):
            # We don't have enough disk space available
            _cannot_compute(reasons.ResourcesTooBig)
            return

        number_of_subtasks = self.task_server.task_keeper\
            .task_headers[msg.task_id]\
            .subtasks_count
        total_task_price = msg.price * number_of_subtasks
        transaction_system = self.task_server.client.transaction_system
        requestors_gntb_balance = transaction_system.get_available_gnt(
            account_address=msg.requestor_ethereum_address,
        )
        if requestors_gntb_balance < total_task_price:
            _cannot_compute(reasons.InsufficientBalance)
            return
        if msg.concent_enabled:
            requestors_deposit_value = transaction_system.concent_balance(
                account_address=msg.requestor_ethereum_address,
            )
            requestors_expected_deposit_value = msg_helpers \
                .requestor_deposit_amount(
                    total_task_price=total_task_price,
                )[0]
            if requestors_deposit_value < requestors_expected_deposit_value:
                logger.info(
                    "Requestors deposit is too small (%.8f < %.8f)",
                    requestors_deposit_value / denoms.ether,
                    requestors_expected_deposit_value / denoms.ether,
                )
                _cannot_compute(reasons.InsufficientDeposit)
                return
            requestors_deposit_timelock = transaction_system.concent_timelock(
                account_address=msg.requestor_ethereum_address,
            )
            # 0 - safe to use
            # <anything else> - withdrawal procedure has started
            if requestors_deposit_timelock != 0:
                _cannot_compute(reasons.TooShortDeposit)
                return

        try:
            self._check_ctd_params(ctd)
            self._set_env_params(
                env_id=msg.want_to_compute_task.task_header.environment,
                ctd=ctd,
            )
        except exceptions.CannotComputeTask as e:
            _cannot_compute(e.reason)
            return

        self.task_manager.comp_task_keeper.receive_subtask(msg)
        self.task_server.add_task_session(
            ctd['subtask_id'], self
        )
        if not self.task_server.task_given(self.key_id, ctd, msg.price):
            _cannot_compute(None)
            return

    def _check_resource_size(self, resource_size):
        max_resource_size_kib = self.task_server.config_desc.max_resource_size
        max_resource_size = int(max_resource_size_kib) * 1024
        if resource_size > max_resource_size:
            logger.info('Subtask with too big resources received: '
                        f'{resource_size}, only {max_resource_size} available')
            return False
        return True

    def _react_to_waiting_for_results(
            self,
            msg: message.tasks.WaitingForResults,
    ):
        if self.concent_service.available:
            concent_key = self.concent_service.variant['pubkey']
        else:
            concent_key = None
        try:
            msg.verify_owners(
                requestor_public_key=msg_utils.decode_hex(self.key_id),
                provider_public_key=self.task_server.keys_auth.ecc.raw_pubkey,
                concent_public_key=concent_key,
            )
        except msg_exceptions.MessageError:
            node_id = common.short_node_id(self.key_id)
            logger.info(
                'Dropping invalid WaitingForResults.'
                ' sender_node_id: %(node_id)s, task_id: %(task_id)s,'
                ' subtask_id: %(subtask_id)s',
                {
                    'node_id': node_id,
                    'task_id': msg.task_id,
                    'subtask_id': msg.subtask_id,
                },
            )
            logger.debug('Invalid WaitingForResults received', exc_info=True)
            return
        self.task_server.subtask_waiting(
            task_id=msg.task_id,
            subtask_id=msg.subtask_id,
        )
        self.task_computer.session_closed()
        if not self.msgs_to_send:
            self.disconnect(message.base.Disconnect.REASON.NoMoreMessages)

    def _react_to_cannot_compute_task(self, msg):
        if self.check_provider_for_subtask(msg.subtask_id):
            logger.info(
                "Provider can't compute subtask: %r Reason: %r",
                msg.subtask_id,
                msg.reason,
            )

            config = self.task_server.config_desc
            timeout = config.computation_cancellation_timeout

            self.task_manager.task_computation_cancelled(
                msg.subtask_id,
                'Task computation rejected: {}'.format(msg.reason),
                timeout,
            )

        self.dropped()

    @history.provider_history
    def _react_to_cannot_assign_task(self, msg):
        if self.check_requestor_for_task(msg.task_id) != \
                RequestorCheckResult.OK:
            self.dropped()
            return
        logger.info(
            "Task request rejected. task_id: %r, reason: %r",
            msg.task_id,
            msg.reason,
        )
        reasons = message.tasks.CannotAssignTask.REASON
        if msg.reason is reasons.TaskFinished:
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

        self.task_server.add_task_session(
            msg.subtask_id, self
        )

        returned_msg = concent_helpers.process_report_computed_task(
            msg=msg,
            ecc=self.task_server.keys_auth.ecc,
        )
        self.send(returned_msg)
        if not isinstance(returned_msg, message.tasks.AckReportComputedTask):
            self.dropped()
            return

        def after_success():
            self.disconnect(message.base.Disconnect.REASON.NoMoreMessages)

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

    @history.provider_history
    def _react_to_subtask_results_accepted(
            self, msg: message.tasks.SubtaskResultsAccepted):
        # The message must be verified, and verification requires self.key_id.
        # This assert is for mypy, which only knows that it's Optional[str].
        assert self.key_id is not None

        if msg.task_to_compute is None or \
                msg.task_to_compute.requestor_public_key != self.key_id:
            logger.info(
                'Empty task_to_compute in %s. Disconnecting: %r',
                msg,
                self.key_id,
            )
            self.disconnect(message.base.Disconnect.REASON.BadProtocol)
            return

        dispatcher.send(
            signal='golem.message',
            event='received',
            message=msg
        )

        self.concent_service.cancel_task_message(
            msg.subtask_id,
            'ForceSubtaskResults',
        )

        self.task_server.subtask_accepted(
            self.key_id,
            msg.subtask_id,
            msg.task_to_compute.requestor_ethereum_address,
            msg.task_to_compute.price,
            msg.payment_ts,
        )
        self.dropped()

    @history.provider_history
    def _react_to_subtask_results_rejected(
            self, msg: message.tasks.SubtaskResultsRejected):
        subtask_id = msg.report_computed_task.subtask_id
        if self.check_requestor_for_subtask(subtask_id) != \
                RequestorCheckResult.OK:
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

            self.task_server.client.transaction_system.\
                validate_concent_deposit_possibility(
                    required=amount,
                    tasks_num=1,
                )
            self.task_server.client.transaction_system.concent_deposit(
                required=amount,
                expected=expected,
            ).addCallback(ask_for_verification).addErrback(
                lambda failure: logger.warning(
                    "Additional verification deposit failed %s", failure.value,
                ),
            )

        else:
            dispatcher.send(
                signal='golem.message',
                event='received',
                message=msg
            )

            self.task_server.subtask_rejected(
                sender_node_id=self.key_id,
                subtask_id=subtask_id,
            )

        self.dropped()

    def _react_to_task_failure(self, msg):
        if self.check_provider_for_subtask(msg.subtask_id):
            self.task_server.subtask_failure(msg.subtask_id, msg.err)
        self.dropped()

    def _react_to_hello(self, msg):
        if not self.conn.opened:
            return
        send_hello = False

        if self.key_id is None:
            self.key_id = msg.client_key_id
            send_hello = True

        if (msg.proto_id != variables.PROTOCOL_CONST.ID)\
                or (msg.node_info is None):
            logger.info(
                "Task protocol version mismatch %r (msg) vs %r (local)",
                msg.proto_id,
                variables.PROTOCOL_CONST.ID
            )
            self.disconnect(message.base.Disconnect.REASON.ProtocolVersion)
            return

        if not KeysAuth.is_pubkey_difficult(
                self.key_id,
                self.task_server.config_desc.key_difficulty):
            logger.info(
                "Key from %s (%s:%d) is not difficult enough (%d < %d).",
                common.node_info_str(
                    msg.node_info.node_name,
                    msg.client_key_id,
                ),
                self.address, self.port,
                KeysAuth.get_difficulty(self.key_id),
                self.task_server.config_desc.key_difficulty)
            self.disconnect(message.base.Disconnect.REASON.KeyNotDifficult)
            return

        nodeskeeper.store(msg.node_info)

        if send_hello:
            self.send_hello()
        self.send(
            message.base.RandVal(rand_val=msg.rand_val),
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
            self.disconnect(message.base.Disconnect.REASON.Unverified)

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
            logger.warning("Requestor '%r' acknowledged a computed task report"
                           " of an unknown task (subtask_id='%s')",
                           self.key_id, msg.subtask_id)
            return

        logger.debug("Requestor '%r' accepted the computed subtask '%r' "
                     "report", self.key_id, msg.subtask_id)

        self.concent_service.cancel_task_message(
            msg.subtask_id, 'ForceReportComputedTask')

        if msg.task_to_compute.concent_enabled:
            delayed_forcing_msg = message.concents.ForceSubtaskResults(
                ack_report_computed_task=msg,
            )
            ttc_deadline = datetime.datetime.utcfromtimestamp(
                msg.task_to_compute.compute_task_def['deadline']
            )
            svt = msg_helpers.subtask_verification_time(
                msg.report_computed_task,
            )
            delay = ttc_deadline + svt - datetime.datetime.utcnow()
            delay += datetime.timedelta(seconds=1)  # added for safety
            logger.debug(
                '[CONCENT] Delayed ForceResults. msg=%r, delay=%r',
                delayed_forcing_msg,
                delay
            )
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

    def check_requestor_for_task(self, task_id: str, additional_msg: str = "") \
            -> RequestorCheckResult:
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(
            task_id)
        if node_id is None:
            return RequestorCheckResult.NOT_FOUND
        if node_id != self.key_id:
            logger.warning('Received message about task %r from diferrent '
                           'node %r than expected %r. %s', task_id,
                           self.key_id, node_id, additional_msg)
            return RequestorCheckResult.MISMATCH
        return RequestorCheckResult.OK

    def check_requestor_for_subtask(self, subtask_id: str) \
            -> RequestorCheckResult:
        task_id = self.task_manager.comp_task_keeper.get_task_id_for_subtask(
            subtask_id)
        if task_id is None:
            return RequestorCheckResult.NOT_FOUND
        return self.check_requestor_for_task(task_id, "Subtask %r" % subtask_id)

    def _check_ctd_params(self, ctd: message.ComputeTaskDef) -> None:
        header = self.task_manager.comp_task_keeper.get_task_header(
            ctd['task_id'])
        owner = header.task_owner

        reasons = message.tasks.CannotComputeTask.REASON
        if owner.key != self.key_id:
            raise exceptions.CannotComputeTask(reason=reasons.WrongKey)

        addresses = [
            (owner.pub_addr, owner.pub_port),
            (owner.prv_addr, owner.prv_port)
        ]

        if not any(tcpnetwork.SocketAddress.is_proper_address(addr, port)
                   for addr, port in addresses):
            raise exceptions.CannotComputeTask(reason=reasons.WrongAddress)

    def _set_env_params(
            self,
            env_id: str,
            ctd: message.tasks.ComputeTaskDef,
    ) -> None:
        env = self.task_server.get_environment_by_id(env_id)
        reasons = message.tasks.CannotComputeTask.REASON
        if not env:
            raise exceptions.CannotComputeTask(reason=reasons.WrongEnvironment)

        reasons = message.tasks.CannotComputeTask.REASON

        if isinstance(env, DockerEnvironment):
            check_docker_images(ctd, env)

    def __set_msg_interpretations(self):
        self._interpretation.update({
            message.tasks.WantToComputeTask:
                self._react_to_want_to_compute_task,
            message.tasks.TaskToCompute:
                self._react_to_task_to_compute,
            message.tasks.CannotAssignTask:
                self._react_to_cannot_assign_task,
            message.tasks.CannotComputeTask:
                self._react_to_cannot_compute_task,
            message.tasks.ReportComputedTask:
                self._react_to_report_computed_task,
            message.tasks.SubtaskResultsAccepted:
                self._react_to_subtask_results_accepted,
            message.tasks.SubtaskResultsRejected:
                self._react_to_subtask_results_rejected,
            message.tasks.TaskFailure:
                self._react_to_task_failure,
            message.base.Hello:
                self._react_to_hello,
            message.base.RandVal:
                self._react_to_rand_val,
            message.tasks.StartSessionResponse:
                self._react_to_start_session_response,
            message.tasks.WaitingForResults:
                self._react_to_waiting_for_results,

            # Concent messages
            message.tasks.AckReportComputedTask:
                self._react_to_ack_report_computed_task,
            message.tasks.RejectReportComputedTask:
                self._react_to_reject_report_computed_task,
        })

        self.can_be_unverified.extend(
            [
                message.base.Hello,
                message.base.RandVal,
                message.base.ChallengeSolution
            ]
        )

        self.can_be_not_encrypted.extend([message.base.Hello])
