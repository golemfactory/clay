from enum import Enum, auto

from devp2p import slogging
from devp2p.service import WiredService

from golem.docker.environment import DockerEnvironment
from golem.model import db, Payment
from golem.network.p2p.taskprotocol import TaskProtocol
from golem.network.transport.tcpnetwork import SocketAddress
from golem.task.taskbase import result_types, ComputeTaskDef
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo

logger = slogging.get_logger('golem.service')


class TaskRequestRejection(Enum):

    TASK_ID_UNKNOWN = 0
    DOWNLOADING_RESULT = 1
    NO_MORE_SUBTASKS = 2


class TaskRejection(Enum):

    INVALID_CTD = 0
    INVALID_DOCKER_IMAGES = 1
    INVALID_PUBKEY = 2
    INVALID_ADDRESS = 3
    INVALID_ENVIRONMENT = 4
    MISSING_DOCKER_IMAGE = 5
    MISSING_SOURCE_CODE = 6


class ResultRejection(Enum):

    SUBTASK_ID_UNKNOWN = 0
    SUBTASK_ID_MISMATCH = 1
    RESULT_TYPE_UNKNOWN = 2
    DOWNLOAD_FAILED = 3
    DECRYPTION_FAILED = 4
    EXTRACTION_FAILED = 5
    VERIFICATION_FAILED = 6


class PaymentRejection(Enum):

    PAYMENT_UNKNOWN = 0


class TaskService(WiredService):

    # required by WiredService
    wire_protocol = TaskProtocol
    name = 'task_service'

    def __init__(self, client):
        super(TaskService, self).__init__(client)
        self.peer_manager = client.services.peermanager
        self.task_server = None
        self.task_manager = None
        self.task_computer = None

    def set_task_server(self, task_server):
        self.task_server = task_server
        self.task_manager = task_server.task_manager
        self.task_computer = task_server.task_computer

    def get_peer(self, pubkey):
        for peer in self.peer_manager.peers:
            if peer.remote_pubkey == pubkey:
                return peer

    def on_wire_protocol_start(self, proto):
        assert isinstance(proto, self.wire_protocol)

        logger.debug('----------------------------------')
        logger.debug('on_wire_protocol_start', proto=proto)

        # register callbacks
        proto.receive_reject_callbacks(self.receive_reject)
        proto.receive_task_request_callbacks(self.receive_task_request)
        proto.receive_task_callbacks(self.receive_task)
        proto.receive_failure_callbacks(self.receive_failure)
        proto.receive_result_callbacks(self.receive_result)
        proto.receive_accept_result_callbacks(self.receive_accept_result)
        proto.receive_payment_request_callbacks(self.receive_payment_request)
        proto.receive_payment_callbacks(self.receive_payment)

    def on_wire_protocol_stop(self, proto):
        assert isinstance(proto, self.wire_protocol)

        logger.debug('----------------------------------')
        logger.debug('on_wire_protocol_stop', proto=proto)

    # ======================================================================== #
    #                              TASK REQUEST
    # ======================================================================== #

    @staticmethod
    def send_task_request(proto, task_id, performance, price, max_disk,
                          max_memory, max_cpus):
        proto.send_task_request(task_id, performance, price, max_disk,
                                max_memory, max_cpus)

    def receive_task_request(self, proto, task_id, performance, price,
                             max_disk, max_memory, max_cpus):

        pubkey = proto.peer.remote_pubkey
        name = proto.peer.node_name or ''
        ip, port = proto.peer.connection.getpeername()
        ctd, wrong_task, wait = None, False, False

        if self.task_server.should_accept_provider(pubkey):
            # FIXME: This is the point where tasks are assigned to providers
            ctd, wrong_task, wait = self.task_manager.get_next_subtask(
                pubkey, name, task_id, performance, price,
                max_disk, max_memory, max_cpus, ip
            )

        if ctd:
            self.send_task(proto, ctd)
        elif wrong_task:
            self.send_reject_task_request(
                proto, task_id, TaskRequestRejection.TASK_ID_UNKNOWN)
        elif wait:
            self.send_reject_task_request(
                proto, task_id, TaskRequestRejection.DOWNLOADING_RESULT)
        else:
            self.send_reject_task_request(
                proto, task_id, TaskRequestRejection.NO_MORE_SUBTASKS)

    def send_reject_task_request(self, proto, task_id, reason):
        cmd_id = TaskProtocol.task_request.cmd_id
        self.send_reject(proto, cmd_id, reason, task_id)

    def _receive_reject_task_request(self, proto, reason, payload):
        task_id = payload
        # TODO: Convert reason enum to message
        self.task_computer.task_request_rejected(task_id, reason)
        self.task_server.remove_task_header(task_id)
        self.task_computer.session_closed()

    # ======================================================================== #
    #                                  TASK
    # ======================================================================== #

    @staticmethod
    def send_task(proto, ctd):
        proto.send_task(ctd)

    def receive_task(self, proto, definition, resources, resource_options):

        task_keeper = self.task_manager.comp_task_keeper
        pubkey = proto.peer.remote_pubkey

        try:
            self._validate_ctd(definition, pubkey)
            self._set_ctd_env_params(definition)
            if not task_keeper.receive_subtask(definition):
                raise RuntimeError("No requests made for subtask_id")

        except (ValueError, RuntimeError) as exc:
            logger.error("Received invalid task definition: %s", exc)
            self.task_computer.session_closed()
            return self.send_reject_task(proto, TaskRejection.INVALID_CTD,
                                         definition.subtask_id)

        self.task_server.add_task_session(definition, self)
        self.task_computer.task_given(definition)

        client = self.task_server.client
        resource_manager = client.resource_server.resource_manager
        resources = resource_manager.from_wire(resources)

        self.task_server.pull_resources(definition.task_id, resources,
                                        client_options=resource_options)

    def send_reject_task(self, proto, task_id, reason):
        cmd_id = TaskProtocol.task.cmd_id
        self.send_reject(proto, cmd_id, reason, task_id)

    def _receive_reject_task(self, proto, reason, payload):
        pubkey = proto.peer.remote_pubkey
        subtask_id = payload

        if self.task_manager.get_node_id_for_subtask(subtask_id) == pubkey:
            msg = 'Task computation rejected: {}'.format(reason)
            self.task_manager.task_computation_failure(subtask_id, msg)

    # ======================================================================== #
    #                        TASK COMPUTATION RESULT
    # ======================================================================== #

    def send_result(self, proto, subtask_id, computation_time,
                    resource_hash, resource_secret, resource_options,
                    eth_account):

        proto.send_result(subtask_id, computation_time, resource_hash,
                          resource_secret, resource_options, eth_account)

    def receive_result(self, proto, subtask_id, computation_time,
                       resource_hash, resource_secret, resource_options,
                       node_info, eth_account):

        logger.debug("Task result: received hash %r (options: %r)",
                     resource_hash, resource_options)

        task_id = self.task_manager.subtask2task_mapping.get(subtask_id)
        task = self.task_manager.tasks.get(task_id)

        if not task:
            logger.error("Task result: unknown subtask_id '%s'", subtask_id)
            return self.send_reject_result(proto, subtask_id,
                                           ResultRejection.SUBTASK_ID_UNKNOWN)

        def on_success(extracted_pkg, *args, **kwargs):
            logger.debug("Task result: extracted {}"
                         .format(extracted_pkg.__dict__))

            metadata = extracted_pkg.to_extra_data()
            self._result_downloaded(proto, subtask_id, metadata)

        def on_error(exc, *args, **kwargs):
            logger.error("Task result: error downloading {} ({})"
                         .format(subtask_id, exc or "unspecified"))

            self.task_server.reject_result(subtask_id, proto.eth_account_info)
            self.task_manager.task_computation_failure(
                subtask_id, 'Error downloading task result')

            self.send_reject_result(proto, subtask_id,
                                    ResultRejection.DOWNLOAD_FAILED)

        self._set_eth_account(proto, node_info, eth_account)
        self.task_server.receive_subtask_computation_time(
            subtask_id, computation_time)

        self.task_manager.task_result_incoming(subtask_id)
        self.task_manager.task_result_manager.pull_package(
            resource_hash,
            task_id,
            subtask_id,
            resource_secret,
            success=on_success,
            error=on_error,
            client_options=resource_options,
            output_dir=getattr(task, 'tmp_dir', None)
        )

    @staticmethod
    def send_accept_result(proto, subtask_id, remuneration):
        proto.send_accept_result(subtask_id, remuneration)

    def receive_accept_result(self, proto, subtask_id, remuneration):
        self.task_server.subtask_accepted(subtask_id, remuneration)

    def send_reject_result(self, proto, subtask_id, reason):
        cmd_id = TaskProtocol.result.cmd_id
        self.send_reject(proto, cmd_id, reason, subtask_id, drop_peer=True)

    def _receive_reject_result(self, proto, reason, payload):
        self.task_server.subtask_rejected(payload)

    # ======================================================================== #
    #                        TASK COMPUTATION FAILURE
    # ======================================================================== #

    @staticmethod
    def send_failure(proto, subtask_id, reason):
        proto.send_failure(subtask_id, reason)

    def receive_failure(self, proto, subtask_id, reason):
        self.task_server.subtask_failure(subtask_id, reason)

    # ======================================================================== #
    #                            PAYMENT REQUEST
    # ======================================================================== #

    @staticmethod
    def send_payment_request(proto, subtask_id):
        proto.send_payment_request(subtask_id)

    def receive_payment_request(self, proto, subtask_id):
        try:
            with db.atomic():
                payment = Payment.get(Payment.subtask == subtask_id)
        except Payment.DoesNotExist:
            logger.info('Payment does not exist yet: %r', subtask_id)
            self.send_reject_payment_request(proto, subtask_id,
                                             PaymentRejection.PAYMENT_UNKNOWN)
        else:
            self.send_payment(proto, payment)

    def send_reject_payment_request(self, proto, subtask_id, reason):
        cmd_id = TaskProtocol.payment.cmd_id
        self.send_reject(proto, cmd_id, reason, subtask_id)

    @staticmethod
    def _receive_reject_payment_request(proto, reason, payload):
        logger.error("Payment information request denied: %r %r",
                     reason, payload)

    # ======================================================================== #
    #                                PAYMENT
    # ======================================================================== #

    def send_payment(self, proto, payment):
        proto.send_payment(
            payment.subtask,
            payment.details.get('tx'),
            payment.value,
            payment.details.get('block_number')
        )

    def receive_payment(self, proto, subtask_id, transaction_id, remuneration,
                        block_number):
        if transaction_id is None:
            logger.debug(
                'PAYMENT PENDING %r for %r',
                remuneration,
                subtask_id
            )
            return

        if block_number is None:
            logger.debug(
                'PAYMENT NOT MINED: %r for %r tid: %r',
                remuneration,
                subtask_id,
                transaction_id
            )
            return

        self.task_server.reward_for_subtask_paid(
            subtask_id=subtask_id,
            reward=remuneration,
            transaction_id=transaction_id,
            block_number=block_number
        )

    # ======================================================================== #
    #                                 REJECT
    # ======================================================================== #

    @staticmethod
    def send_reject(proto, cmd_id, reason, payload, drop_peer=False):
        proto.send_reject(cmd_id, reason, payload)
        if drop_peer:
            proto.send_disconnect(proto.disconnect.reason.useless_peer)

    def receive_reject(self, proto, cmd_id, reason, payload):
        # Task request rejected
        if cmd_id == TaskProtocol.task_request.cmd_id:
            return self._receive_reject_task_request(proto, reason, payload)
        # Task rejected
        elif cmd_id == TaskProtocol.task.cmd_id:
            return self._receive_reject_task(proto, reason, payload)
        # Task result rejected
        elif cmd_id == TaskProtocol.result.cmd_id:
            return self._receive_reject_result(proto, reason, payload)
        # Payment request rejected
        elif cmd_id == TaskProtocol.payment_request.cmd_id:
            return self._receive_reject_payment_request(proto, reason, payload)

        logger.warning('Received a rejection of an unknown request type: %d',
                       cmd_id)

    # ======================================================================== #
    # ======================================================================== #

    def _result_downloaded(self, proto, subtask_id, metadata):
        result = metadata.get('result')
        result_type = metadata.get("result_type")
        result_subtask_id = metadata.get("subtask_id")

        if subtask_id != result_subtask_id:
            logger.error("Subtask id mismatch: %s != %s",
                         subtask_id, result_subtask_id)
            return self.send_reject_result(proto, subtask_id,
                                           ResultRejection.SUBTASK_ID_MISMATCH)

        if result_type not in result_types.values():
            logger.error("Unknown result type: %s", result_type)
            return self.send_reject_result(proto, subtask_id,
                                           ResultRejection.RESULT_TYPE_UNKNOWN)

        self.task_manager.computed_task_received(subtask_id, result,
                                                 result_type)

        if not self.task_manager.verify_subtask(subtask_id):
            return self.send_reject_result(proto, subtask_id,
                                           ResultRejection.VERIFICATION_FAILED)

        payment = self.task_server.accept_result(subtask_id,
                                                 proto.eth_account_info)

        self.send_accept_result(proto, subtask_id, payment.value)

    @staticmethod
    def _validate_ctd(ctd, pubkey):
        if not isinstance(ctd, ComputeTaskDef):
            raise ValueError(TaskRejection.INVALID_CTD)
        if ctd.key_id != pubkey or ctd.task_owner.key != pubkey:
            raise ValueError(TaskRejection.INVALID_PUBKEY)
        if not SocketAddress.is_proper_address(ctd.return_address,
                                               ctd.return_port):
            raise ValueError(TaskRejection.INVALID_ADDRESS)

    @staticmethod
    def _set_ctd_docker_images(ctd, env):
        for image in ctd.docker_images:
            for env_image in env.docker_images:
                if env_image.cmp_name_and_tag(image):
                    ctd.docker_images = [image]
                    return

        logger.error("Missing Docker images {} for environment {}"
                     .format(ctd.docker_images, env))
        raise RuntimeError(TaskRejection.INVALID_DOCKER_IMAGES)

    def _set_ctd_env_params(self, ctd):
        task_keeper = self.task_manager.comp_task_keeper
        env_id = task_keeper.get_task_env(ctd.task_id)
        env = self.task_server.get_environment_by_id(env_id)

        if not env:
            logger.error("Unknown environment: %s", env_id)
            raise RuntimeError(TaskRejection.INVALID_ENVIRONMENT)

        if isinstance(env, DockerEnvironment):
            self._set_ctd_docker_images(ctd, env)

        if not env.allow_custom_main_program_file:
            ctd.src_code = env.get_source_code()

        if not ctd.src_code:
            raise RuntimeError(TaskRejection.MISSING_SOURCE_CODE)

    def _set_eth_account(self, proto, node_info, eth_account):
        pubkey = proto.peer.remote_pubkey
        name = proto.peer.node_name
        ip, port = proto.peer.connection.getpeername()
        account = EthAccountInfo(pubkey, port, ip, name, node_info, eth_account)

        proto.eth_account_info = account
