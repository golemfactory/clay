# pylint: disable=too-many-lines
import binascii
import datetime
import enum
import functools
import logging
import time
from typing import (
    Any, Callable, TYPE_CHECKING,
    Optional, Generator
)

from ethereum.utils import denoms
from golem_messages import exceptions as msg_exceptions
from golem_messages import helpers as msg_helpers
from golem_messages import message
from golem_messages import utils as msg_utils
from pydispatch import dispatcher
from twisted.internet import defer

import golem
from golem.core import common
from golem.core import deferred
from golem.core import variables
from golem.core.common import deadline_to_timeout
from golem.core.deferred import deferred_from_future
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.marketplace import Offer, ProviderPerformance
from golem.model import Actor
from golem.network import history
from golem.network import nodeskeeper
from golem.network.concent import helpers as concent_helpers
from golem.network.transport import msg_queue
from golem.network.transport import tcpnetwork
from golem.network.transport.session import BasicSafeSession
from golem.ranking.manager.database_manager import (
    update_requestor_assigned_sum
)
from golem.resource.resourcehandshake import ResourceHandshakeSessionMixin
from golem.task import exceptions
from golem.task.helpers import calculate_subtask_payment
from golem.task.requestedtaskmanager import ComputingNodeDefinition
from golem.task.rpc import add_resources
from golem.task.server import helpers as task_server_helpers

if TYPE_CHECKING:
    # pylint: disable=unused-import,ungrouped-imports
    from twisted.internet.protocol import Protocol

    from .requestedtaskmanager import RequestedTaskManager
    from .taskcomputer import TaskComputerAdapter
    from .taskmanager import TaskManager
    from .taskserver import TaskServer
    from golem.network.concent.client import ConcentClientService

logger = logging.getLogger(__name__)


def drop_after_attr_error(*args, **_):
    logger.warning("Attribute error occured(1)", exc_info=True)
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

    def __init__(self, conn: 'Protocol') -> None:
        """
        Create new Session
        :param conn: connection protocol implementation that this
                     session should enhance
        """
        BasicSafeSession.__init__(self, conn)
        ResourceHandshakeSessionMixin.__init__(self)
        # set in server.queue.msg_queue_connection_established()
        self.conn_id = None  # connection id
        self.key_id: Optional[str] = None

        self.__set_msg_interpretations()

    @property
    def task_server(self) -> 'TaskServer':
        return self.conn.server

    @property
    def task_manager(self) -> 'TaskManager':
        return self.task_server.task_manager

    @property
    def requested_task_manager(self) -> 'RequestedTaskManager':
        return self.task_server.requested_task_manager

    @property
    def task_computer(self) -> 'TaskComputerAdapter':
        return self.task_server.task_computer

    @property
    def concent_service(self) -> 'ConcentClientService':
        return self.task_server.client.concent_service

    @property
    def deposit_contract_address(self):
        return self.task_server.client\
            .transaction_system.deposit_contract_address

    @property
    def is_active(self) -> bool:
        if not self.conn.opened:
            return False
        inactivity: float = time.time() - self.last_message_time
        if inactivity > self.task_server.config_desc.task_session_timeout:
            return False
        return True

    def _get_task_class(
            self, task_header: message.tasks.TaskHeader):
        return self.task_server.client.apps_manager.get_task_class_for_env(
            task_header.environment
        )

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
        self.task_server.remove_session_by_node_id(self.key_id)

    #######################
    # SafeSession methods #
    #######################

    @property
    def my_private_key(self) -> bytes:
        return self.task_server.keys_auth._private_key  # noqa pylint: disable=protected-access

    @property
    def my_public_key(self) -> bytes:
        return self.task_server.keys_auth.public_key

    def verify_owners(self, msg, my_role) -> bool:
        if self.concent_service.available:
            concent_key = self.concent_service.variant['pubkey']
        else:
            concent_key = None
        if my_role is Actor.Provider:
            requestor_key = msg_utils.decode_hex(self.key_id)
            provider_key = self.task_server.keys_auth.ecc.raw_pubkey
        else:
            requestor_key = self.task_server.keys_auth.ecc.raw_pubkey
            provider_key = msg_utils.decode_hex(self.key_id)
        try:
            msg.verify_owners(
                requestor_public_key=requestor_key,
                provider_public_key=provider_key,
                concent_public_key=concent_key,
            )
        except msg_exceptions.MessageError:
            node_id = common.short_node_id(self.key_id)
            logger.info(
                'Dropping invalid %(msg_class)s.'
                ' sender_node_id: %(node_id)s, task_id: %(task_id)s,'
                ' subtask_id: %(subtask_id)s',
                {
                    'msg_class': msg.__class__.__name__,
                    'node_id': node_id,
                    'task_id': msg.task_id,
                    'subtask_id': msg.subtask_id,
                },
            )
            logger.debug('Invalid message received', exc_info=True)
            return False
        return True

    def send_hello(self):
        """ Send first hello message, that should begin the communication """
        self.send(
            message.base.Hello(
                client_ver=golem.__version__,
                rand_val=self.rand_val,
                proto_id=variables.PROTOCOL_CONST.ID,
                node_info=self.task_server.client.node,
            ),
            send_unverified=True
        )

    def read_msg_queue(self):
        if not self.key_id:
            logger.debug('skipping queue, no key_id')
            return
        if not self.verified:
            logger.debug('skipping queue, not verified. key_id=%r', self.key_id)
            return
        logger.debug('sending messages for key. %r', self.key_id)
        for msg in msg_queue.get(self.key_id):
            self.send(msg)

    #########################
    # Reactions to messages #
    #########################
    def _cannot_assign_task(self, task_id, reason):
        logger.debug("Cannot assign task: %r", reason)
        self.send(
            message.tasks.CannotAssignTask(
                task_id=task_id,
                reason=reason,
            ),
        )
        self.dropped()

    # pylint: disable=too-many-return-statements
    @defer.inlineCallbacks
    def _react_to_want_to_compute_task(self, msg):
        task_id = msg.task_id
        reasons = message.tasks.CannotAssignTask.REASON

        if msg.concent_enabled and not self.concent_service.enabled:
            self._cannot_assign_task(msg.task_id, reasons.ConcentDisabled)
            return

        is_task_api_task = self.requested_task_manager.task_exists(task_id)
        if not (is_task_api_task or self.task_manager.is_my_task(task_id)):
            self._cannot_assign_task(msg.task_id, reasons.NotMyTask)
            return

        try:
            msg.task_header.verify(self.my_public_key)
        except msg_exceptions.InvalidSignature:
            self._cannot_assign_task(msg.task_id, reasons.NotMyTask)
            return

        task_node_info = "task_id=%r, node=%r" % (
            msg.task_id, common.short_node_id(self.key_id))
        logger.info("Received offer to compute. %s", task_node_info)

        if is_task_api_task:
            self.requested_task_manager.work_offer_received(msg.task_id)
        else:
            self.task_manager.got_wants_to_compute(msg.task_id)

        offer_hash = binascii.hexlify(msg.get_short_hash()).decode('utf8')
        if not self.task_server.should_accept_provider(
                self.key_id, self.address, msg.task_id, msg.perf_index,
                msg.max_memory_size, offer_hash):
            logger.debug(
                "should_accept_provider False. provider=%s, task_id=%s",
                self.key_id, msg.task_id
            )
            self._cannot_assign_task(msg.task_id, reasons.NoMoreSubtasks)
            return

        if is_task_api_task:
            has_pending_subtasks = yield deferred_from_future(
                self.requested_task_manager.has_pending_subtasks(task_id))
            if not has_pending_subtasks:
                logger.debug("has_pending_subtasks False. %s", task_node_info)
                self._cannot_assign_task(task_id, reasons.NoMoreSubtasks)
                return
            if self.requested_task_manager.is_task_finished(task_id):
                logger.debug("is_task_finished True. %s", task_node_info)
                self._cannot_assign_task(task_id, reasons.TaskFinished)
                return

            current_task = self.requested_task_manager.get_requested_task(
                msg.task_id)
            current_app = self.task_server.app_manager.app(
                current_task.app_id)
            market_strategy = current_app.market_strategy
            max_price_per_hour = current_task.max_price_per_hour
        else:
            if not self.task_manager.check_next_subtask(
                    msg.task_id, msg.price):
                logger.debug("check_next_subtask False. %s", task_node_info)
                self._cannot_assign_task(msg.task_id, reasons.NoMoreSubtasks)
                return

            if self.task_manager.task_finished(msg.task_id):
                logger.debug("TaskFinished. %s", task_node_info)
                self._cannot_assign_task(msg.task_id, reasons.TaskFinished)
                return

            current_task = self.task_manager.tasks[msg.task_id]
            market_strategy = current_task.REQUESTOR_MARKET_STRATEGY
            max_price_per_hour = current_task.header.max_price

        if self._handshake_required(self.key_id):
            logger.warning('Can not accept offer: Resource handshake is'
                           ' required. %s', task_node_info)
            self.task_server.start_handshake(self.key_id)
            return

        elif self._handshake_in_progress(self.key_id):
            logger.warning('Can not accept offer: Resource handshake is in'
                           ' progress. %s', task_node_info)
            return

        # pylint:disable=too-many-instance-attributes,too-many-public-methods
        class OfferWithCallback(Offer):
            # pylint:disable=too-many-arguments
            def __init__(
                    self,
                    provider_id: str,
                    provider_performance: ProviderPerformance,
                    max_price: float,
                    price: float,
                    callback: Callable[..., None]) -> None:
                super().__init__(provider_id, provider_performance,
                                 max_price, price)
                self.callback = callback

        offer = OfferWithCallback(
            self.key_id,
            ProviderPerformance(msg.cpu_usage / 1e9),
            max_price_per_hour,
            msg.price,
            functools.partial(self._offer_chosen, True, msg=msg)
        )

        def resolution(market_strategy, task_id):
            for offer in market_strategy.resolve_task_offers(task_id):
                try:
                    offer.callback()
                except Exception as e:
                    logger.error(e)

        market_strategy.add(msg.task_id, offer)
        logger.debug("Offer accepted & added to pool. offer=%s", offer)

        if market_strategy.get_task_offer_count(msg.task_id) == 1:
            deferred.call_later(
                self.task_server.config_desc.offer_pooling_interval,
                resolution,
                market_strategy,
                msg.task_id
            )
            logger.info(
                "Will select providers for task %s in %.1f seconds",
                msg.task_id,
                self.task_server.config_desc.offer_pooling_interval
            )

    @defer.inlineCallbacks
    def _offer_chosen(  # pylint: disable=too-many-locals
            self,
            is_chosen: bool,
            msg: message.tasks.WantToComputeTask,
    ):
        assert self.key_id is not None
        task_id = msg.task_id

        task_node_info = "task_id=%r, node=%r" % (
            msg.task_id, common.short_node_id(self.key_id))
        reasons = message.tasks.CannotAssignTask.REASON
        if not is_chosen:
            logger.info("Provider not chosen by marketplace:%s", task_node_info)
            self._cannot_assign_task(msg.task_id, reasons.NoMoreSubtasks)
            return

        logger.info("Offer confirmed, assigning subtask(s)")

        task_class = self._get_task_class(msg.task_header)
        budget = task_class.REQUESTOR_MARKET_STRATEGY.calculate_budget(msg)

        for _i in range(msg.num_subtasks):
            ctd_res = yield self._get_next_ctd(msg)
            if ctd_res is None:
                logger.debug("_get_next_ctd None. %s", task_id)
                self._cannot_assign_task(task_id, reasons.NoMoreSubtasks)
                return
            ctd, package_hash, package_size = ctd_res
            logger.debug("CTD generated. %s, ctd=%s", task_node_info, ctd)

            ttc = message.tasks.TaskToCompute(
                compute_task_def=ctd,
                want_to_compute_task=msg,
                requestor_id=msg.task_header.task_owner.key,
                requestor_public_key=msg.task_header.task_owner.key,
                requestor_ethereum_public_key=msg.task_header.task_owner.key,
                provider_id=self.key_id,
                package_hash='sha1:' + package_hash,
                concent_enabled=msg.concent_enabled,
                price=budget,
                size=package_size,
                resources_options=self.task_server.get_share_options(
                    address=self.address).__dict__
            )
            ttc.generate_ethsig(self.my_private_key)
            if ttc.concent_enabled:
                logger.debug(
                    f"Signing promissory notes for GNTDeposit at: "
                    f"{self.deposit_contract_address}"
                )
                ttc.sign_all_promissory_notes(
                    deposit_contract_address=self.deposit_contract_address,
                    private_key=self.my_private_key
                )

            signed_ttc = msg_utils.copy_and_sign(
                msg=ttc,
                private_key=self.my_private_key,
            )

            self.send(ttc)

            logger.info(
                "Subtask assigned. %s, subtask_id=%r",
                task_node_info, ctd["subtask_id"]
            )

            history.add(
                msg=signed_ttc,
                node_id=self.key_id,
                local_role=Actor.Requestor,
                remote_role=Actor.Provider,
            )

    # pylint: disable=too-many-locals
    @defer.inlineCallbacks
    def _get_next_ctd(
            self,
            msg: message.tasks.WantToComputeTask,
    ) -> Optional[Generator[defer.Deferred, Any, None]]:
        assert self.key_id is not None
        task_id = msg.task_id

        if self.requested_task_manager.task_exists(task_id):
            has_pending_subtasks = yield deferred.deferred_from_future(
                self.requested_task_manager.has_pending_subtasks(task_id))
            if not has_pending_subtasks:
                return None
            node_name = ''
            node_info = nodeskeeper.get(self.key_id)
            if node_info and node_info.node_name:
                node_name = node_info.node_name
            subtask_definition = yield deferred.deferred_from_future(
                self.requested_task_manager.get_next_subtask(
                    task_id=task_id,
                    computing_node=ComputingNodeDefinition(
                        name=node_name,
                        node_id=self.key_id
                    )
                ))
            if subtask_definition is None:
                # Application refused to assign subtask to provider node
                return None

            task_resources_dir = self.requested_task_manager.\
                get_subtask_inputs_dir(task_id)

            rm = self.task_server.new_resource_manager
            share_options = self.task_server.get_share_options(
                timeout=deadline_to_timeout(subtask_definition.deadline))

            cdn_resources = yield defer.gatherResults([
                rm.share(task_resources_dir / r, share_options)
                for r in subtask_definition.resources
            ])
            new_ctd = {
                'task_id': task_id,
                'subtask_id': subtask_definition.subtask_id,
                'extra_data': subtask_definition.params,
                'deadline': subtask_definition.deadline,
                'resources': cdn_resources,
                'performance': msg.perf_index,
                # The lack of the 'docker_images' property causes
                # TTC.compute_task_def and RCT.task_to_compute.compute_task_def
                # to differ and fail signature verification
                'docker_images': None,
            }
            return new_ctd, '', 1

        offer_hash = binascii.hexlify(msg.get_short_hash()).decode('utf8')
        ctd = self.task_manager.get_next_subtask(
            self.key_id,
            msg.task_id,
            msg.perf_index,
            msg.price,
            offer_hash,
        )
        if ctd is None:
            return None

        task = self.task_manager.tasks[msg.task_id]
        task.accept_client(self.key_id, offer_hash, msg.num_subtasks)

        if ctd["resources"]:
            resources_result = yield add_resources(
                self.task_server.client,
                ctd["resources"],
                ctd["subtask_id"],
                common.deadline_to_timeout(ctd["deadline"])
            )
            _, _, package_hash, package_size = resources_result
            # overwrite resources so they are serialized by
            # resource_manager
            resources = self.task_server.get_resources(ctd['subtask_id'])
            ctd["resources"] = resources
            logger.info("resources_result: %r", resources_result)
        else:
            ctd["resources"] = self.task_server.get_resources(ctd['task_id'])
            task_state = self.task_manager.tasks_states[msg.task_id]
            package_hash = task_state.package_hash
            package_size = task_state.package_size
        return ctd, package_hash, package_size

    # pylint: disable=too-many-return-statements, too-many-branches
    @handle_attr_error
    @history.provider_history
    def _react_to_task_to_compute(self, msg: message.tasks.TaskToCompute):
        ctd: Optional[message.tasks.ComputeTaskDef] = msg.compute_task_def
        want_to_compute_task = msg.want_to_compute_task
        if ctd is None or want_to_compute_task is None:
            logger.debug(
                'TaskToCompute without ctd or want_to_compute_task: %r', msg)
            self.dropped()
            return

        try:
            want_to_compute_task.verify_signature(
                self.task_server.keys_auth.ecc.raw_pubkey)
        except msg_exceptions.InvalidSignature:
            logger.debug(
                'WantToComputeTask attached to TaskToCompute is not signed '
                'with key: %r.', want_to_compute_task.provider_public_key)
            self.dropped()
            return

        dispatcher.send(
            signal='golem.message',
            event='received',
            message=msg
        )

        logger.info(
            "Received subtask. task_id: %r, subtask_id: %r, requestor_id: %r",
            ctd["task_id"],
            ctd["subtask_id"],
            common.short_node_id(msg.requestor_id)
        )

        def _cannot_compute(reason):
            assert isinstance(reason, message.tasks.CannotComputeTask.REASON)
            logger.info(
                "Cannot compute subtask. subtask_id: %r, reason: %r",
                ctd["subtask_id"],
                reason
            )

            self.send(
                message.tasks.CannotComputeTask(
                    task_to_compute=msg,
                    reason=reason,
                ),
            )
            self.dropped()

        reasons = message.tasks.CannotComputeTask.REASON

        if not self.task_computer.can_take_work():
            _cannot_compute(reasons.OfferCancelled)
            self.task_server.requested_tasks.discard(ctd["task_id"])
            return

        if (
                self.concent_service.enabled
                and self.concent_service.required_as_provider
                and not msg.concent_enabled
        ):
            # Provider requires concent
            # if it's enabled locally and marked as required
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

        task_header = msg.want_to_compute_task.task_header
        total_task_price = calculate_subtask_payment(
            task_header.max_price,
            task_header.subtask_timeout
        ) * task_header.subtasks_count

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

            if not msg.verify_all_promissory_notes(
                    deposit_contract_address=self.deposit_contract_address):
                _cannot_compute(reasons.PromissoryNoteMissing)
                logger.debug(
                    f"Requestor failed to provide correct promissory"
                    f"note signatures to compute with the Concent:"
                    f"promissory_note_sig: {msg.promissory_note_sig}, "
                    f"concent_promissory_note_sig: "
                    f"{msg.concent_promissory_note_sig}."
                )
                return

        try:
            self._check_task_header(msg.want_to_compute_task.task_header)
            self._set_env_params(
                env_id=msg.want_to_compute_task.task_header.environment,
                ctd=ctd,
            )
        except exceptions.CannotComputeTask as e:
            _cannot_compute(e.reason)
            return

        if not self.task_server.task_given(msg):
            _cannot_compute(reasons.CannotTakeWork)
            return

    # pylint: enable=too-many-return-statements, too-many-branches

    def _check_resource_size(self, resource_size):
        max_resource_size_kib = self.task_server.config_desc.max_resource_size
        max_resource_size = int(max_resource_size_kib) * 1024
        if resource_size > max_resource_size:
            logger.info('Subtask with too big resources received: '
                        f'{resource_size}, only {max_resource_size} available')
            return False
        return True

    @defer.inlineCallbacks
    def _react_to_cannot_compute_task(self, msg):
        if not self.check_provider_for_subtask(msg.task_id, msg.subtask_id):
            self.dropped()
            return

        logger.info(
            "Provider can't compute subtask. subtask_id: %r, reason: %r",
            msg.subtask_id,
            msg.reason,
        )

        if self.requested_task_manager.subtask_exists(msg.subtask_id):
            yield deferred_from_future(
                self.requested_task_manager.abort_subtask(msg.subtask_id)
            )
        else:
            config = self.task_server.config_desc
            timeout = config.computation_cancellation_timeout
            self.task_manager.task_computation_cancelled(
                msg.subtask_id,
                msg.reason,
                timeout,
            )

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
        self.task_server.requested_tasks.discard(msg.task_id)
        reasons = message.tasks.CannotAssignTask.REASON
        if msg.reason is reasons.TaskFinished:
            # Requestor doesn't want us to ask again
            self.task_server.remove_task_header(msg.task_id)
        self.task_manager.comp_task_keeper.request_failure(msg.task_id)
        self.dropped()

    @history.requestor_history
    def _react_to_report_computed_task(self, msg):
        if not self.verify_owners(msg, my_role=Actor.Requestor):
            return

        if not self.check_provider_for_subtask(msg.task_id, msg.subtask_id):
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
            return

        def after_error():
            if msg.task_to_compute.concent_enabled:
                return
            # in case of resources failure, if we're not using the Concent
            # we're immediately sending a rejection message to the Provider
            self.task_server.send_result_rejected(
                report_computed_task=msg,
                reason=message.tasks.SubtaskResultsRejected.REASON
                .ResourcesFailure,
            )
            self.task_manager.task_computation_failure(
                msg.subtask_id,
                'Error downloading task result'
            )

        task_server_helpers.computed_task_reported(
            task_server=self.task_server,
            report_computed_task=msg,
            after_error=after_error,
        )

        logger.debug(
            "Task result hash received: %r from %r:%r",
            msg.multihash,
            self.address,
            self.port,
        )

    def _get_payment_value_and_budget(
            self, rct: message.tasks.ReportComputedTask):
        task_class = self._get_task_class(
            rct.task_to_compute.want_to_compute_task.task_header)
        market_strategy = task_class.PROVIDER_MARKET_STRATEGY
        payment_value = market_strategy.calculate_payment(rct)
        budget = market_strategy.calculate_budget(
            rct.task_to_compute.want_to_compute_task)
        return payment_value, budget

    @staticmethod
    def _adjust_requestor_assigned_sum(
            requestor_id: str, payment_value: int, budget: int):
        # because we have originally updated the requestor's assigned sum
        # with the budget value, when we accepted the job
        # now that we finally know what the actual payment amount is
        # we need to subtract the difference
        if payment_value < budget:
            update_requestor_assigned_sum(
                requestor_id,
                payment_value - budget
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

        payment_value, budget = self._get_payment_value_and_budget(
            msg.report_computed_task)
        self._adjust_requestor_assigned_sum(
            msg.requestor_id, payment_value, budget)

        logger.info(
            "Result accepted. subtask_id=%s, "
            "requestor_id=%s, payment_value=%s GNT",
            msg.subtask_id,
            msg.requestor_id,
            payment_value / denoms.ether,
        )

        self.task_server.subtask_accepted(
            sender_node_id=self.key_id,
            task_id=msg.task_id,
            subtask_id=msg.subtask_id,
            payer_address=msg.task_to_compute.requestor_ethereum_address,
            value=payment_value,
            accepted_ts=msg.payment_ts,
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

        def subtask_rejected():
            dispatcher.send(
                signal='golem.message',
                event='received',
                message=msg
            )
            self.task_server.subtask_rejected(
                sender_node_id=self.key_id,
                subtask_id=subtask_id,
            )

        payment_value, budget = self._get_payment_value_and_budget(
            msg.report_computed_task)
        self._adjust_requestor_assigned_sum(
            msg.requestor_id, payment_value, budget)

        if msg.task_to_compute.concent_enabled:
            self._handle_srr_with_concent_enabled(msg, subtask_rejected)
        else:
            subtask_rejected()

        self.dropped()

    def _handle_srr_with_concent_enabled(
            self, msg: message.tasks.SubtaskResultsRejected,
            subtask_rejected: Callable[[], None]):
        if msg.reason == (message.tasks.SubtaskResultsRejected.REASON
                          .VerificationNegative):
            logger.debug("_handle_srr_with_concent_enabled: triggering "
                         "additional verification")
            self._trigger_concent_additional_verification(msg)
            return

        fgtrf_msg: message.concents.ForceGetTaskResultFailed = \
            msg.force_get_task_result_failed

        if msg.reason == (message.tasks.SubtaskResultsRejected.REASON
                          .ForcedResourcesFailure) \
                and fgtrf_msg \
                and self.verify_owners(fgtrf_msg, my_role=Actor.Provider) \
                and (msg.report_computed_task.task_to_compute.subtask_id ==
                     fgtrf_msg.task_to_compute.subtask_id):
            subtask_id = msg.report_computed_task.subtask_id
            logger.info("Received ForcedResourcesFailure message. "
                        "subtask_id=%s", subtask_id)
            subtask_rejected()
            return

        # in case the reason for SRR is neither
        # a `VerificationNegative` nor `ForcedResourcesFailure`
        # the SRR is effectively broken so we're ignoring it
        # instead
        # we wait for timeout to trigger force accept,
        # so that the SRR can be verified independently by the Concent

    def _trigger_concent_additional_verification(
            self, msg: message.tasks.SubtaskResultsRejected):
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
            srv.sign_concent_promissory_note(
                deposit_contract_address=self.deposit_contract_address,
                private_key=self.my_private_key,
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

    def _react_to_task_failure(self, msg):
        if self.check_provider_for_subtask(msg.task_id, msg.subtask_id):
            self.task_server.subtask_failure(msg.subtask_id, msg.err)
        self.dropped()

    def _react_to_hello(self, msg):
        if not self.conn.opened:
            logger.info("Hello received after connection closed. msg=%s", msg)
            return

        if (msg.proto_id != variables.PROTOCOL_CONST.ID)\
                or (msg.node_info is None):
            logger.info(
                "Task protocol version mismatch %r (msg) vs %r (local)",
                msg.proto_id,
                variables.PROTOCOL_CONST.ID
            )
            self.disconnect(message.base.Disconnect.REASON.ProtocolVersion)
            return

        send_hello = False

        if self.key_id is None:
            self.key_id = msg.node_info.key
            try:
                existing_session = self.task_server.sessions[self.key_id]
            except KeyError:
                self.task_server.sessions[self.key_id] = self
            else:
                if (existing_session is not None)\
                        and existing_session is not self:
                    node_name = getattr(msg.node_info, 'node_name', '')
                    logger.debug(
                        'Duplicated session. Dropping. node=%s',
                        common.node_info_str(node_name, self.key_id),
                    )
                    self.dropped()
                    return
            send_hello = True

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

        if self.rand_val != msg.rand_val:
            self.disconnect(message.base.Disconnect.REASON.Unverified)

        self.verified = True
        self.task_server.verified_conn(self.conn_id, )
        self.read_msg_queue()

    def _react_to_start_session_response(self, msg):
        raise NotImplementedError(
            "Implement reversed task session request #4005",
        )

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
        subtask_known = False
        if keeper.check_task_owner_by_subtask(self.key_id, msg.subtask_id):
            self.concent_service.cancel_task_message(
                msg.subtask_id, 'ForceReportComputedTask')
            subtask_known = True
        logger.log(
            logging.INFO if subtask_known else logging.WARNING,
            "ReportComputedTask rejected by the requestor%s. "
            "requestor_id='%r', subtask_id='%r', reason='%s'",
            '' if subtask_known else ' and the subtask is unknown to us',
            self.key_id, msg.subtask_id, msg.reason
        )

    def disconnect(self, reason: message.base.Disconnect.REASON):
        if not self.conn.opened:
            return
        if not (self.verified and self.key_id):
            self.dropped()
            return
        super().disconnect(reason)

    def send(self, msg, send_unverified=False):
        if self.key_id and not self.conn.opened:
            msg_queue.put(self.key_id, msg)
            return
        if not self.verified and not send_unverified:
            if not self.key_id:
                raise RuntimeError('Connection unverified')
            msg_queue.put(self.key_id, msg)
            return
        BasicSafeSession.send(self, msg, send_unverified=send_unverified)
        self.task_server.set_last_message(
            "->",
            time.localtime(),
            msg,
            self.address,
            self.port
        )

    def check_provider_for_subtask(
            self,
            task_id: str,
            subtask_id: str
    ) -> bool:
        node_id = self.requested_task_manager.get_node_id_for_subtask(
            task_id,
            subtask_id)
        if node_id is None:
            node_id = self.task_manager.get_node_id_for_subtask(subtask_id)
        if node_id != self.key_id:
            logger.warning('Received message about subtask %r from different '
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

    def _check_task_header(self, header: message.tasks.TaskHeader) -> None:
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
