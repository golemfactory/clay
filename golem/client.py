# pylint: disable=too-many-lines

import collections
import json
import logging
import random
import sys
import time
import uuid
from copy import copy, deepcopy
from os import path, makedirs
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Hashable, Optional, Union, List, Iterable, Tuple

from ethereum.utils import denoms
from golem_messages import helpers as msg_helpers
from pydispatch import dispatcher
from twisted.internet.defer import (
    inlineCallbacks,
    gatherResults,
    Deferred)

import golem
from apps.appsmanager import AppsManager
from apps.core.task.coretask import CoreTask
from apps.rendering.task import framerenderingtask
from golem.appconfig import TASKARCHIVE_MAINTENANCE_INTERVAL, AppConfig
from golem.clientconfigdescriptor import ConfigApprover, ClientConfigDescriptor
from golem.config.presets import HardwarePresetsMixin
from golem.core import variables
from golem.core.async import AsyncRequest, async_run
from golem.core.common import (
    deadline_to_timeout,
    datetime_to_timestamp_utc,
    get_timestamp_utc,
    string_to_timeout,
    to_unicode,
)
from golem.core.fileshelper import du
from golem.core.hardware import HardwarePresets
from golem.core.keysauth import KeysAuth
from golem.core.service import LoopingCallService
from golem.core.simpleserializer import DictSerializer
from golem.database import Database
from golem.diag.service import DiagnosticsService, DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot
from golem.ethereum.exceptions import NotEnoughFunds
from golem.ethereum.fundslocker import FundsLocker
from golem.ethereum.paymentskeeper import PaymentStatus
from golem.ethereum.transactionsystem import TransactionSystem
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MONITOR_CONFIG
from golem.network.concent.client import ConcentClientService
from golem.network.concent.filetransfers import ConcentFiletransferService
from golem.network.history import MessageHistoryService
from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import PeerSessionInfo
from golem.network.transport.tcpnetwork import SocketAddress
from golem.network.upnp.mapper import PortMapperManager
from golem.ranking.helper.trust import Trust
from golem.ranking.ranking import Ranking
from golem.report import Component, Stage, StatusPublisher, report_calls
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.dirmanager import DirManager, DirectoryType
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.resource.resource import get_resources_for_task, ResourceType
from golem.rpc.mapping.rpceventnames import Task, Network, Environment, UI
from golem.task import taskpreset
from golem.task.masking import Mask
from golem.task.taskarchiver import TaskArchiver
from golem.task.taskbase import Task as TaskBase
from golem.task.taskmanager import TaskManager
from golem.task.taskserver import TaskServer
from golem.task.taskstate import TaskTestStatus, SubtaskStatus
from golem.task.tasktester import TaskTester
from golem.tools import filelock
from golem.tools.talkback import enable_sentry_logger


logger = logging.getLogger(__name__)


class CreateTaskError(Exception):
    pass


class ClientTaskComputerEventListener(object):

    def __init__(self, client):
        self.client = client

    def lock_config(self, on=True):
        self.client.lock_config(on)

    def config_changed(self):
        self.client.config_changed()


class Client(HardwarePresetsMixin):
    _services = []  # type: List[IService]

    def __init__(  # noqa pylint: disable=too-many-arguments
            self,
            datadir: str,
            app_config: AppConfig,
            config_desc: ClientConfigDescriptor,
            keys_auth: KeysAuth,
            database: Database,
            transaction_system: TransactionSystem,
            connect_to_known_hosts: bool = True,
            use_docker_manager: bool = True,
            use_monitor: bool = True,
            # SEE: golem.core.variables.CONCENT_CHOICES
            concent_variant: dict = variables.CONCENT_CHOICES['disabled'],
            geth_address: Optional[str] = None,
            apps_manager: AppsManager = AppsManager(),
            task_finished_cb=None) -> None:

        self.apps_manager = apps_manager
        self.datadir = datadir
        self.__lock_datadir()
        self.lock = Lock()
        self.task_tester = None

        self.task_archiver = TaskArchiver(datadir)

        # Read and validate configuration
        self.app_config = app_config
        self.config_desc = config_desc
        self.config_approver = ConfigApprover(self.config_desc)

        if self.config_desc.in_shutdown:
            self.update_setting('in_shutdown', False)

        logger.info(
            'Client "%s", datadir: %s',
            self.config_desc.node_name,
            datadir
        )
        self.db = database

        # Hardware configuration
        HardwarePresets.initialize(self.datadir)
        HardwarePresets.update_config(self.config_desc.hardware_preset_name,
                                      self.config_desc)

        self.keys_auth = keys_auth

        # NETWORK
        self.node = Node(node_name=self.config_desc.node_name,
                         prv_addr=self.config_desc.node_address,
                         key=self.keys_auth.key_id)

        self.p2pservice = None
        self.diag_service = None
        self.concent_service = ConcentClientService(
            variant=concent_variant,
            keys_auth=self.keys_auth,
        )
        self.concent_filetransfers = ConcentFiletransferService(
            keys_auth=self.keys_auth,
            variant=concent_variant,
        )

        self.task_server: Optional[TaskServer] = None
        self.port_mapper = None

        self.nodes_manager_client = None

        self._services = [
            NetworkConnectionPublisherService(
                self,
                int(self.config_desc.network_check_interval)),
            TaskArchiverService(self.task_archiver),
            MessageHistoryService(),
            DoWorkService(self),
        ]

        clean_resources_older_than = \
            self.config_desc.clean_resources_older_than_seconds
        if clean_resources_older_than > 0:
            self._services.append(
                ResourceCleanerService(
                    self,
                    interval_seconds=max(
                        1, int(clean_resources_older_than / 10)),
                    older_than_seconds=clean_resources_older_than))

        self.ranking = Ranking(self)

        self.transaction_system = transaction_system
        self.transaction_system.start()

        self.funds_locker = FundsLocker(self.transaction_system,
                                        Path(self.datadir))
        self._services.append(self.funds_locker)

        self.use_docker_manager = use_docker_manager
        self.connect_to_known_hosts = connect_to_known_hosts
        self.environments_manager = EnvironmentsManager()
        self.daemon_manager = None

        self.rpc_publisher = None
        self.task_test_result = None

        self.resource_server = None
        self.resource_port = 0
        self.use_monitor = use_monitor
        self.monitor = None
        self.session_id = str(uuid.uuid4())
        self._task_finished_cb = task_finished_cb

        dispatcher.connect(
            self.p2p_listener,
            signal='golem.p2p'
        )
        dispatcher.connect(
            self.taskmanager_listener,
            signal='golem.taskmanager'
        )

        logger.debug('Client init completed')

    def set_rpc_publisher(self, rpc_publisher):
        self.rpc_publisher = rpc_publisher

    def p2p_listener(self, event='default', **kwargs):
        if event == 'unreachable':
            self.on_unreachable(**kwargs)
        elif event == 'unsynchronized':
            self.on_unsynchronized(**kwargs)
        elif event == 'new_version':
            self.on_new_version(**kwargs)

    def on_unreachable(self, port, description, **_):
        logger.warning('Port %d unreachable: %s', port, description)
        self.node.port_statuses[port] = description

    @staticmethod
    def on_unsynchronized(time_diff, **_):
        logger.warning(
            'Node time unsynchronized with monitor. Time diff: %f (s)',
            time_diff)

    def on_new_version(self, version, **_):
        logger.warning('New version of golem available: %s', version)
        self._publish(Network.new_version, str(version))

    def taskmanager_listener(self, sender, signal, event='default', **kwargs):
        if event != 'task_status_updated':
            return
        logger.debug(
            'taskmanager_listen (sender: %r, signal: %r, event: %r, args: %r)',
            sender, signal, event, kwargs
        )

        op = kwargs['op'] if 'op' in kwargs else None

        if op is not None and op.subtask_related():
            self._publish(Task.evt_subtask_status, kwargs['task_id'],
                          kwargs['subtask_id'], op.value)
        else:
            op_class_name: str = op.__class__.__name__ \
                                 if op is not None else None
            op_value: int = op.value if op is not None else None
            self._publish(Task.evt_task_status, kwargs['task_id'],
                          op_class_name, op_value)

    @report_calls(Component.client, 'sync')
    def sync(self):
        pass

    @report_calls(Component.client, 'start', stage=Stage.pre)
    def start(self):

        logger.debug('Starting client services ...')
        self.environments_manager.load_config(self.datadir)
        self.concent_service.start()
        self.concent_filetransfers.start()

        if self.use_monitor and not self.monitor:
            self.init_monitor()
        try:
            self.start_network()
        except Exception:
            logger.critical('Can\'t start network. Giving up.', exc_info=True)
            sys.exit(1)

        for service in self._services:
            if not service.running:
                service.start()
        logger.debug('Started client services')

    @report_calls(Component.client, 'stop', stage=Stage.post)
    def stop(self):
        logger.debug('Stopping client services ...')
        self.stop_network()

        for service in self._services:
            if service.running:
                service.stop()
        self.concent_service.stop()
        if self.concent_filetransfers.running:
            self.concent_filetransfers.stop()
        if self.task_server:
            self.task_server.task_computer.quit()
        if self.use_monitor and self.monitor:
            self.stop_monitor()
            self.monitor = None
        logger.debug('Stopped client services')

    def start_network(self):
        logger.info("Starting network ...")
        self.node.collect_network_info(self.config_desc.seed_host,
                                       use_ipv6=self.config_desc.use_ipv6)

        logger.debug("Is super node? %s", self.node.is_super_node())

        self.p2pservice = P2PService(
            self.node,
            self.config_desc,
            self.keys_auth,
            connect_to_known_hosts=self.connect_to_known_hosts
        )
        self.p2pservice.add_metadata_provider(
            'performance', self.environments_manager.get_performance_values)

        self.task_server = TaskServer(
            self.node,
            self.config_desc,
            self,
            use_ipv6=self.config_desc.use_ipv6,
            use_docker_manager=self.use_docker_manager,
            task_archiver=self.task_archiver,
            apps_manager=self.apps_manager,
            task_finished_cb=self._task_finished_cb,
        )

        monitoring_publisher_service = MonitoringPublisherService(
            self.task_server,
            interval_seconds=max(
                int(self.config_desc.node_snapshot_interval),
                60))
        monitoring_publisher_service.start()
        self._services.append(monitoring_publisher_service)

        if self.config_desc.net_masking_enabled:
            mask_udpate_service = MaskUpdateService(
                task_manager=self.task_server.task_manager,
                interval_seconds=self.config_desc.mask_update_interval,
                update_num_bits=self.config_desc.mask_update_num_bits
            )
            mask_udpate_service.start()
            self._services.append(mask_udpate_service)

        dir_manager = self.task_server.task_computer.dir_manager

        logger.info("Starting resource server ...")

        self.daemon_manager = HyperdriveDaemonManager(self.datadir)
        self.daemon_manager.start()

        hyperdrive_addrs = self.daemon_manager.public_addresses(
            self.node.pub_addr)
        hyperdrive_ports = self.daemon_manager.ports()

        self.node.hyperdrive_prv_port = next(iter(hyperdrive_ports))

        clean_tasks_older_than = \
            self.config_desc.clean_tasks_older_than_seconds
        if clean_tasks_older_than > 0:
            self.clean_old_tasks()

        resource_manager = HyperdriveResourceManager(
            dir_manager=dir_manager,
            daemon_address=hyperdrive_addrs
        )
        self.resource_server = BaseResourceServer(
            resource_manager=resource_manager,
            dir_manager=dir_manager,
            keys_auth=self.keys_auth,
            client=self
        )
        self.task_server.restore_resources()

        # Start service after restore_resources() to avoid race conditions
        if clean_tasks_older_than:
            task_cleaner_service = TaskCleanerService(
                client=self,
                interval_seconds=max(1, clean_tasks_older_than // 10)
            )
            task_cleaner_service.start()
            self._services.append(task_cleaner_service)

        def connect(ports):
            logger.info(
                'Golem is listening on ports: P2P=%s, Task=%s, Hyperdrive=%r',
                self.node.p2p_prv_port,
                self.node.prv_port,
                self.node.hyperdrive_prv_port
            )

            if self.config_desc.use_upnp:
                self.start_upnp(ports + list(hyperdrive_ports))
            self.node.update_public_info()

            public_ports = [
                self.node.p2p_pub_port,
                self.node.pub_port,
                self.node.hyperdrive_pub_port
            ]

            dispatcher.send(
                signal='golem.p2p',
                event='listening',
                ports=public_ports)

            listener = ClientTaskComputerEventListener(self)
            self.task_server.task_computer.register_listener(listener)
            self.p2pservice.connect_to_network()

            if self.monitor:
                self.diag_service.register(self.p2pservice,
                                           self.monitor.on_peer_snapshot)
                self.monitor.on_login()

            StatusPublisher.publish(Component.client, 'start',
                                    stage=Stage.post)

        def terminate(*exceptions):
            logger.error("Golem cannot listen on ports: %s", exceptions)
            StatusPublisher.publish(Component.client, 'start',
                                    stage=Stage.exception,
                                    data=[to_unicode(e) for e in exceptions])
            sys.exit(1)

        task = Deferred()
        p2p = Deferred()

        gatherResults([p2p, task], consumeErrors=True).addCallbacks(connect,
                                                                    terminate)
        logger.info("Starting p2p server ...")
        self.p2pservice.task_server = self.task_server
        self.p2pservice.set_resource_server(self.resource_server)
        self.p2pservice.start_accepting(listening_established=p2p.callback,
                                        listening_failure=p2p.errback)

        logger.info("Starting task server ...")
        self.task_server.start_accepting(listening_established=task.callback,
                                         listening_failure=task.errback)

    def start_upnp(self, ports):
        logger.debug("Starting upnp ...")
        self.port_mapper = PortMapperManager()
        self.port_mapper.discover()

        if self.port_mapper.available:
            for port in ports:
                self.port_mapper.create_mapping(port)
            self.port_mapper.update_node(self.node)

    def stop_network(self):
        logger.info("Stopping network ...")
        if self.p2pservice:
            self.p2pservice.stop_accepting()
            self.p2pservice.disconnect()
        if self.task_server:
            self.task_server.stop_accepting()
            self.task_server.disconnect()
        if self.port_mapper:
            self.port_mapper.quit()

    @inlineCallbacks
    def pause(self):
        logger.info("Pausing ...")
        for service in self._services:
            if service.running:
                service.stop()

        if self.p2pservice:
            self.p2pservice.pause()
            self.p2pservice.disconnect()
        if self.task_server:
            yield self.task_server.pause()
            self.task_server.disconnect()
            self.task_server.task_computer.quit()
        logger.info("Paused")

    def resume(self):
        logger.info("Resuming ...")
        for service in self._services:
            if not service.running:
                service.start()

        if self.p2pservice:
            self.p2pservice.resume()
            self.p2pservice.connect_to_network()
        if self.task_server:
            self.task_server.resume()
        logger.info("Resumed")

    def init_monitor(self):
        logger.debug("Starting monitor ...")
        metadata = self.__get_nodemetadatamodel()
        self.monitor = SystemMonitor(metadata, MONITOR_CONFIG)
        self.monitor.start()
        self.diag_service = DiagnosticsService(DiagnosticsOutputFormat.data)
        self.diag_service.register(
            VMDiagnosticsProvider(),
            self.monitor.on_vm_snapshot
        )
        self.diag_service.start()

    def stop_monitor(self):
        logger.debug("Stopping monitor ...")
        self.monitor.shut_down()
        self.diag_service.stop()

    def connect(self, socket_address):
        if isinstance(socket_address, collections.Iterable):
            socket_address = SocketAddress(
                socket_address[0],
                int(socket_address[1])
            )

        logger.debug(
            "P2pservice connecting to %s on port %s",
            socket_address.address,
            socket_address.port
        )
        self.p2pservice.connect(socket_address)

    @report_calls(Component.client, 'quit', once=True)
    def quit(self):
        logger.info('Shutting down ...')
        self.stop()

        self.transaction_system.stop()
        if self.diag_service:
            self.diag_service.unregister_all()
        if self.daemon_manager:
            self.daemon_manager.stop()

        dispatcher.send(signal='golem.monitor', event='shutdown')

        if self.db:
            self.db.close()
        self._unlock_datadir()

    def enqueue_new_task(self, task_dict) -> Tuple[Deferred, str]:
        """
        :return: (deferred, task_id) - deferred returns Task object when it's
        successfully created.
        """
        if self.config_desc.in_shutdown:
            raise CreateTaskError(
                'Can not enqueue task: shutdown is in progress, '
                'toggle shutdown mode off to create a new tasks.')
        if self.task_server is None:
            raise CreateTaskError("Golem is not ready")

        task_manager = self.task_server.task_manager
        _result = Deferred()

        # FIXME: Statement only for old DummyTask compatibility #2467
        task: TaskBase
        if isinstance(task_dict, dict):
            logger.warning('enqueue_new_task called with deprecated dict type')
            task = task_manager.create_task(task_dict)
        else:
            task = task_dict

        if task.header.fixed_header.concent_enabled and \
                not self.concent_service.enabled:
            raise CreateTaskError(
                "Cannot create task with concent enabled when "
                "concent service is disabled")

        task_id = task.header.task_id
        self.funds_locker.lock_funds(task)

        if self.concent_service.enabled:
            min_amount, opt_amount = msg_helpers.requestor_deposit_amount(
                task.price,
            )
            # This is a bandaid solution for unlocking funds when task creation
            # fails. This case is most common but, the better way it to always
            # unlock them when the task fails regardless of the reason.
            try:
                self.transaction_system.concent_deposit(
                    required=min_amount,
                    expected=opt_amount,
                )
            except NotEnoughFunds:
                self.funds_locker.remove_task(task_id)
                raise

        logger.info('Enqueue new task "%r"', task_id)
        files = get_resources_for_task(resource_header=None,
                                       resource_type=ResourceType.HASHES,
                                       tmp_dir=getattr(task, 'tmp_dir', None),
                                       resources=task.get_resources())

        def package_created(packager_result):
            package_path, package_sha1 = packager_result
            task.header.resource_size = path.getsize(package_path)

            if self.config_desc.net_masking_enabled:
                task.header.mask = self._get_mask_for_task(task)
            else:
                task.header.mask = Mask()

            estimated_fee = self.transaction_system.eth_for_batch_payment(
                task.total_tasks)
            task_manager.add_new_task(task, estimated_fee=estimated_fee)

            client_options = self.task_server.get_share_options(task_id, None)
            client_options.timeout = deadline_to_timeout(task.header.deadline)

            _resources = self.resource_server.add_task(
                package_path, package_sha1, task_id, task.header.resource_size,
                client_options=client_options)
            _resources.addCallbacks(task_created, error)

        def task_created(resource_server_result):
            resource_manager_result, package_path,\
                package_hash, package_size = resource_server_result

            try:
                task_state = task_manager.tasks_states[task_id]
                task_state.package_path = package_path
                task_state.package_hash = package_hash
                task_state.package_size = package_size
                task_state.resource_hash = resource_manager_result[0]
                logger.debug(
                    "Setting task state - package_path: %s, package_hash: %s, "
                    "package_size: %s, resource_hash: %s",
                    task_state.package_path, task_state.package_hash,
                    task_state.package_size, task_state.resource_hash
                )
            except Exception as exc:  # pylint: disable=broad-except
                error(exc)
                return

            request = AsyncRequest(task_manager.start_task, task_id)
            async_run(request, lambda _: _result.callback(task), error)

        def error(exception):
            logger.error("Task '%s' creation failed: %r", task_id, exception)
            _result.errback(exception)

        _package = self.resource_server.create_resource_package(files, task_id)
        _package.addCallbacks(package_created, error)
        return _result, task_id

    def _get_mask_for_task(self, task: CoreTask) -> Mask:
        desired_num_workers = max(
            task.get_total_tasks() *
            self.config_desc.initial_mask_size_factor,
            self.config_desc.min_num_workers_for_mask)

        assert isinstance(self.p2pservice, P2PService)
        assert isinstance(self.task_server, TaskServer)

        network_size = self.p2pservice.get_estimated_network_size()
        min_perf = self.task_server.get_min_performance_for_task(task)
        perf_rank = self.p2pservice.get_performance_percentile_rank(
            min_perf, task.header.environment)
        potential_num_workers = int(network_size * (1 - perf_rank))

        mask = Mask.get_mask_for_task(
            desired_num_workers=desired_num_workers,
            potential_num_workers=potential_num_workers
        )
        logger.info(
            f'Task {task.header.task_id} '
            f'initial mask size: {mask.num_bits} '
            f'expected number of providers: {desired_num_workers} '
            f'potential number of providers: {potential_num_workers}'
        )

        return mask

    def task_resource_send(self, task_id):
        self.task_server.task_manager.resources_send(task_id)

    def task_resource_collected(self, task_id, unpack_delta=True):
        self.task_server.task_computer.task_resource_collected(
            task_id,
            unpack_delta
        )

    def task_resource_failure(self, task_id, reason):
        self.task_server.task_computer.task_resource_failure(task_id, reason)

    def run_test_task(self, t_dict):
        logger.info('Running test task "%r" ...', t_dict)
        if self.task_tester is None:
            request = AsyncRequest(self._run_test_task, t_dict)
            async_run(request)
            return True

        if not self.task_test_result:
            self.task_test_result = json.dumps(
                {
                    "status": TaskTestStatus.error,
                    "error": "Another test is running"
                })
        return False

    def _run_test_task(self, t_dict):

        def on_success(result, estimated_memory, time_spent, **kwargs):
            logger.info('Test task succes "%r"', t_dict)
            self.task_tester = None
            self.task_test_result = json.dumps(
                {
                    "status": TaskTestStatus.success,
                    "result": result,
                    "estimated_memory": estimated_memory,
                    "time_spent": time_spent,
                    "more": kwargs
                })

        def on_error(*args, **kwargs):
            logger.warning('Test task error "%r": %r', t_dict, args)
            self.task_tester = None
            self.task_test_result = json.dumps(
                {"status": TaskTestStatus.error, "error": args, "more": kwargs})

        try:
            dictionary = DictSerializer.load(t_dict)
            task = self.task_server.task_manager.create_task(
                dictionary=dictionary, minimal=True
            )
        except Exception as e:
            return on_error(to_unicode(e))

        self.task_test_result = json.dumps(
            {"status": TaskTestStatus.started, "error": True})
        self.task_tester = TaskTester(task, self.datadir, on_success, on_error)
        self.task_tester.run()

    def abort_test_task(self):
        logger.debug('Aborting test task ...')
        with self.lock:
            if self.task_tester is not None:
                self.task_tester.end_comp()
                return True
            return False

    def check_test_status(self):
        logger.debug('Checking test task status ...')
        if self.task_test_result is None:
            return False
        if not json.loads(
                self.task_test_result)['status'] == TaskTestStatus.started:
            result = copy(self.task_test_result)
            # when client receive the eventual result we'll clean result for
            # the next one.
            self.task_test_result = None
            return result
        return self.task_test_result

    def create_task(self, t_dict) -> Tuple[Optional[str], Optional[str]]:
        """
        :return: (task_id, None) on success; (task_id or None, error_message)
                 on failure
        """
        try:
            deferred, task_id = self.enqueue_new_task(t_dict)
            # We want to return quickly from create_task without waiting for
            # deferred completion.
            deferred.addErrback(
                lambda err: logger.error("Cannot create task: %r", err))
            return task_id, None
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Cannot create task %r: %s", t_dict, str(ex))
            return None, str(ex)

    def abort_task(self, task_id):
        logger.debug('Aborting task "%r" ...', task_id)
        self.task_server.task_manager.abort_task(task_id)

    def restart_task(self, task_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        :return: (new_task_id, None) on success; (None, error_message)
                 on failure
        """
        logger.debug('Restarting task "%r" ...', task_id)
        task_manager = self.task_server.task_manager

        # Task state is changed to restarted and stays this way until it's
        # deleted from task manager.
        try:
            task_manager.assert_task_can_be_restarted(task_id)
        except task_manager.AlreadyRestartedError:
            return None, "Task already restarted: '{}'".format(task_id)

        # Create new task that is a copy of the definition of the old one.
        # It has a new deadline and a new task id.
        try:
            task_dict = deepcopy(
                task_manager.get_task_definition_dict(
                    task_manager.tasks[task_id]))
        except KeyError:
            return None, "Task not found: '{}'".format(task_id)

        task_dict.pop('id', None)
        new_task_id, msg = self.create_task(task_dict)
        if new_task_id:
            task_manager.put_task_in_restarted_state(task_id)

        return new_task_id, msg

    def restart_subtasks_from_task(
            self, task_id: str, subtask_ids: Iterable[str]):

        assert isinstance(self.task_server, TaskServer)
        task_manager = self.task_server.task_manager

        try:
            task_manager.put_task_in_restarted_state(task_id, clear_tmp=False)
            old_task = task_manager.tasks[task_id]
            finished_subtask_ids = set(
                sub_id for sub_id, sub in old_task.subtasks_given.items()
                if sub['status'] == SubtaskStatus.finished
            )
            subtask_ids_to_copy = finished_subtask_ids - set(subtask_ids)
        except task_manager.AlreadyRestartedError:
            logger.error('Task already restarted: %r', task_id)
            return None
        except KeyError:
            logger.error('Task not found: %r', task_id)
            return None

        task_dict = deepcopy(task_manager.get_task_definition_dict(old_task))
        del task_dict['id']

        def copy_results(task: TaskBase):
            task_manager.copy_results(
                old_task_id=task_id,
                new_task_id=task.header.task_id,
                subtask_ids_to_copy=subtask_ids_to_copy
            )

        deferred, _ = self.enqueue_new_task(task_dict)

        deferred.addCallbacks(
            copy_results,
            lambda err: logger.error('Task creation failed: %r', err))

    def restart_frame_subtasks(self, task_id, frame):
        self.task_server.task_manager.restart_frame_subtasks(task_id, frame)

    def restart_subtask(self, subtask_id):
        self.task_server.task_manager.restart_subtask(subtask_id)

    def delete_task(self, task_id):
        logger.debug('Deleting task "%r" ...', task_id)
        self.remove_task_header(task_id)
        self.remove_task(task_id)
        self.task_server.task_manager.delete_task(task_id)
        self.funds_locker.remove_task(task_id)

    def get_node(self):
        return self.node.to_dict()

    def get_node_name(self):
        name = self.config_desc.node_name
        return str(name) if name else ''

    def get_neighbours_degree(self):
        return self.p2pservice.get_peers_degree()

    def get_suggested_addr(self, key_id):
        return self.p2pservice.suggested_address.get(key_id)

    def get_suggested_conn_reverse(self, key_id):
        return self.p2pservice.get_suggested_conn_reverse(key_id)

    def get_peers(self):
        if self.p2pservice:
            return list(self.p2pservice.peers.values())
        return list()

    def get_known_peers(self):
        peers = self.p2pservice.incoming_peers or dict()
        return [
            DictSerializer.dump(p['node'], typed=False)
            for p in list(peers.values())
        ]

    def get_connected_peers(self):
        peers = self.get_peers() or []
        return [
            DictSerializer.dump(PeerSessionInfo(p), typed=False) for p in peers
        ]

    def get_public_key(self):
        return self.keys_auth.public_key

    def get_dir_manager(self):
        if self.task_server:
            return self.task_server.task_computer.dir_manager

    def get_key_id(self):
        return self.keys_auth.key_id

    def get_difficulty(self):
        return self.keys_auth.get_difficulty()

    def get_node_key(self):
        key = self.node.key
        return str(key) if key else None

    def get_settings(self):
        settings = DictSerializer.dump(self.config_desc, typed=False)

        for key, value in settings.items():
            if ConfigApprover.is_big_int(key):
                settings[key] = str(value)

        return settings

    def get_setting(self, key):
        if not hasattr(self.config_desc, key):
            raise KeyError("Unknown setting: {}".format(key))

        value = getattr(self.config_desc, key)
        if ConfigApprover.is_numeric(key):
            return str(value)
        return value

    def update_setting(self, key, value):
        if not hasattr(self.config_desc, key):
            raise KeyError("Unknown setting: {}".format(key))
        setattr(self.config_desc, key, value)
        self.change_config(self.config_desc)

    def update_settings(self, settings_dict, run_benchmarks=False):
        for key, value in list(settings_dict.items()):
            if not hasattr(self.config_desc, key):
                raise KeyError("Unknown setting: {}".format(key))
            setattr(self.config_desc, key, value)
        self.change_config(self.config_desc, run_benchmarks)

    def get_datadir(self):
        return str(self.datadir)

    def get_p2p_port(self):
        return self.p2pservice.cur_port

    def get_task_server_port(self):
        return self.task_server.cur_port

    def get_task_count(self):
        if self.task_server:
            return len(self.task_server.task_keeper.get_all_tasks())
        return 0

    def get_task(self, task_id: str) -> Optional[dict]:
        assert isinstance(self.task_server, TaskServer)

        task_dict = self.task_server.task_manager.get_task_dict(task_id)
        if not task_dict:
            return None

        task_state = self.task_server.task_manager.query_task_state(task_id)
        subtask_ids = list(task_state.subtask_states.keys())

        # Get total value and total fee for payments for the given subtask IDs
        subtasks_payments = \
            self.transaction_system.get_subtasks_payments(subtask_ids)
        all_sent = all(
            p.status in [PaymentStatus.sent, PaymentStatus.confirmed]
            for p in subtasks_payments)
        if not subtasks_payments or not all_sent:
            task_dict['cost'] = None
            task_dict['fee'] = None
        else:
            # Because details are JSON field
            task_dict['cost'] = sum(p.value or 0 for p in subtasks_payments)
            task_dict['fee'] = \
                sum(p.details.fee or 0 for p in subtasks_payments)

        # Convert to string because RPC serializer fails on big numbers
        for k in ('cost', 'fee', 'estimated_cost', 'estimated_fee'):
            if task_dict[k] is not None:
                task_dict[k] = str(task_dict[k])

        return task_dict

    def get_tasks(self, task_id: Optional[str] = None) \
            -> Union[Optional[dict], Iterable[dict]]:
        if not self.task_server:
            return []

        if task_id:
            return self.get_task(task_id)

        task_ids = list(self.task_server.task_manager.tasks.keys())
        tasks = (self.get_task(task_id) for task_id in task_ids)
        # Filter Nones because get_task returns Optional[dict]
        return list(filter(None, tasks))

    def get_subtasks(self, task_id: str) \
            -> Optional[List[Dict]]:
        try:
            assert isinstance(self.task_server, TaskServer)
            subtasks = self.task_server.task_manager.get_subtasks_dict(task_id)
            return subtasks
        except KeyError:
            logger.info("Task not found: '%s'", task_id)

    def get_subtasks_borders(self, task_id, part=1):
        return self.task_server.task_manager.get_subtasks_borders(task_id,
                                                                  part)

    def get_subtasks_frames(self, task_id):
        return self.task_server.task_manager.get_output_states(task_id)

    def get_subtask(self, subtask_id: str) \
            -> Tuple[Optional[Dict], Optional[str]]:
        try:
            assert isinstance(self.task_server, TaskServer)
            subtask = self.task_server.task_manager.get_subtask_dict(subtask_id)
            return subtask, None
        except KeyError:
            return None, "Subtask not found: '{}'".format(subtask_id)

    def get_task_preview(self, task_id, single=False):
        return self.task_server.task_manager.get_task_preview(task_id,
                                                              single=single)

    def get_task_stats(self) -> Dict[str, int]:
        return {
            'host_state': self.get_task_state(),
            'provider_state': self.get_provider_status(),
            'in_network': self.get_task_count(),
            'supported': self.get_supported_task_count(),
            'subtasks_computed': self.get_computed_task_count(),
            'subtasks_with_errors': self.get_error_task_count(),
            'subtasks_with_timeout': self.get_timeout_task_count()
        }

    def get_supported_task_count(self) -> int:
        if self.task_server:
            return len(self.task_server.task_keeper.supported_tasks)
        return 0

    def get_task_state(self):
        if self.task_server and self.task_server.task_computer:
            return self.task_server.task_computer.get_host_state()

    def get_computed_task_count(self):
        return self.get_task_computer_stat('computed_tasks')

    def get_timeout_task_count(self):
        return self.get_task_computer_stat('tasks_with_timeout')

    def get_error_task_count(self):
        return self.get_task_computer_stat('tasks_with_errors')

    def get_unsupport_reasons(self, last_days):
        if last_days < 0:
            raise ValueError("Incorrect number of days: {}".format(last_days))
        if last_days > 0:
            return self.task_archiver.get_unsupport_reasons(last_days)
        else:
            return self.task_server.task_keeper.get_unsupport_reasons()

    def get_payment_address(self):
        address = self.transaction_system.get_payment_address()
        return str(address) if address else None

    def get_task_computer_stat(self, name):
        if self.task_server and self.task_server.task_computer:
            return self.task_server.task_computer.stats.get_stats(name)
        return None, None

    def get_balance(self):
        balances = self.transaction_system.get_balance()
        gnt_total = balances['gnt_available'] + balances['gnt_nonconverted']
        return {
            'av_gnt': str(balances['gnt_available']),
            'gnt': str(gnt_total),
            'gnt_lock': str(balances['gnt_locked']),
            'gnt_nonconverted': str(balances['gnt_nonconverted']),
            'eth': str(balances['eth_available']),
            'eth_lock': str(balances['eth_locked']),
            'block_number': str(balances['block_number']),
            'last_gnt_update': str(balances['gnt_update_time']),
            'last_eth_update': str(balances['eth_update_time']),
        }

    def get_payments_list(self):
        return self.transaction_system.get_payments_list()

    def get_incomes_list(self):
        incomes = self.transaction_system.get_incomes_list()

        def item(o):
            status = "confirmed" if o.transaction else "awaiting"

            return {
                "subtask": to_unicode(o.subtask),
                "payer": to_unicode(o.sender_node),
                "value": to_unicode(o.value),
                "status": to_unicode(status),
                "transaction": to_unicode(o.transaction),
                "created": datetime_to_timestamp_utc(o.created_date),
                "modified": datetime_to_timestamp_utc(o.modified_date)
            }

        return [item(income) for income in incomes]

    def get_withdraw_gas_cost(
            self,
            amount: Union[str, int],
            destination: str,
            currency: str) -> int:
        if isinstance(amount, str):
            amount = int(amount)
        return self.transaction_system.get_withdraw_gas_cost(
            amount,
            destination,
            currency,
        )

    def withdraw(
            self,
            amount: Union[str, int],
            destination: str,
            currency: str) -> List[str]:
        if isinstance(amount, str):
            amount = int(amount)
        # It returns a list for backwards compatibility with Electron.
        return [self.transaction_system.withdraw(
            amount,
            destination,
            currency,
        )]

    # It's defined here only for RPC exposure in
    # golem.rpc.mapping.rpcmethodnames
    def get_subtasks_count(  # pylint: disable=no-self-use
            self,
            total_subtasks: int,
            optimize_total: bool,
            use_frames: bool,
            frames: list):
        """Returns computed number of subtasks, before task creation."""
        return framerenderingtask.calculate_subtasks_count(
            total_subtasks=total_subtasks,
            optimize_total=optimize_total,
            use_frames=use_frames,
            frames=frames,
        )

    def get_computing_trust(self, node_id):
        if self.use_ranking():
            return self.ranking.get_computing_trust(node_id)
        return None

    def get_requesting_trust(self, node_id):
        if self.use_ranking():
            return self.ranking.get_requesting_trust(node_id)
        return None

    def use_ranking(self):
        return bool(self.ranking)

    def want_to_start_task_session(self, key_id, node_id, conn_id):
        self.p2pservice.want_to_start_task_session(key_id, node_id, conn_id)

    # CLIENT CONFIGURATION
    def set_rpc_server(self, rpc_server):
        self.rpc_server = rpc_server
        return self.rpc_server.add_service(self)

    def change_config(self, new_config_desc, run_benchmarks=False):
        self.config_desc = self.config_approver.change_config(new_config_desc)
        self.upsert_hw_preset(HardwarePresets.from_config(self.config_desc))

        if self.p2pservice:
            self.p2pservice.change_config(self.config_desc)
        if self.task_server:
            self.task_server.change_config(self.config_desc,
                                           run_benchmarks=run_benchmarks)

        self.enable_talkback(self.config_desc.enable_talkback)
        self.app_config.change_config(self.config_desc)

        dispatcher.send(
            signal='golem.monitor',
            event='config_update',
            meta_data=self.__get_nodemetadatamodel()
        )

    def register_nodes_manager_client(self, nodes_manager_client):
        self.nodes_manager_client = nodes_manager_client

    def query_task_state(self, task_id):
        state = self.task_server.task_manager.query_task_state(task_id)
        if state:
            return DictSerializer.dump(state)

    def pull_resources(self, task_id, resources, client_options=None):
        self.resource_server.download_resources(
            resources,
            task_id,
            client_options=client_options
        )

    def add_resource_peer(self, node_name, addr, port, key_id, node_info):
        self.resource_server.add_resource_peer(
            node_name,
            addr,
            port,
            key_id,
            node_info
        )

    def get_res_dirs(self):
        return {"total received data": self.get_received_files_dir(),
                "total distributed data": self.get_distributed_files_dir()}

    def get_res_dirs_sizes(self):
        return {str(name): str(du(d))
                for name, d in list(self.get_res_dirs().items())}

    def get_res_dir(self, dir_type):
        if dir_type == DirectoryType.DISTRIBUTED:
            return self.get_distributed_files_dir()
        elif dir_type == DirectoryType.RECEIVED:
            return self.get_received_files_dir()
        raise Exception("Unknown dir type: {}".format(dir_type))

    def get_received_files_dir(self):
        return str(self.task_server.task_manager.get_task_manager_root())

    def get_distributed_files_dir(self):
        return str(self.resource_server.get_distributed_resource_root())

    def clear_dir(self, dir_type, older_than_seconds: int = 0):
        if dir_type == DirectoryType.DISTRIBUTED:
            return self.remove_distributed_files(older_than_seconds)
        elif dir_type == DirectoryType.RECEIVED:
            return self.remove_received_files(older_than_seconds)
        raise Exception("Unknown dir type: {}".format(dir_type))

    def remove_distributed_files(self, older_than_seconds: int = 0):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(self.get_distributed_files_dir(),
                              older_than_seconds)

    def remove_received_files(self, older_than_seconds: int = 0):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(
            self.get_received_files_dir(), older_than_seconds)

    def remove_task(self, task_id):
        self.p2pservice.remove_task(task_id)

    def remove_task_header(self, task_id):
        self.task_server.remove_task_header(task_id)

    def clean_old_tasks(self):
        now = get_timestamp_utc()
        for task in self.get_tasks():
            deadline = task['time_started'] \
                + string_to_timeout(task['timeout'])\
                + self.config_desc.clean_tasks_older_than_seconds
            if deadline <= now:
                logger.info('Task %s got too old. Deleting.', task['id'])
                self.delete_task(task['id'])

    def get_known_tasks(self):
        headers = {}
        for key, header in list(self.task_server.task_keeper.task_headers.items()):  # noqa
            headers[str(key)] = DictSerializer.dump(header)
        return headers

    def get_environments(self):
        envs = copy(self.environments_manager.get_environments())
        return [{
            'id': env_id,
            'supported': bool(env.check_support()),
            'accepted': env.is_accepted(),
            'performance': env.get_performance(),
            'min_accepted': env.get_min_accepted_performance(),
            'description': str(env.short_description)
        } for env_id, env in envs.items()]

    @inlineCallbacks
    def run_benchmark(self, env_id):
        deferred = Deferred()

        self.task_server.benchmark_manager.run_benchmark_for_env_id(
            env_id, deferred.callback, deferred.errback)

        result = yield deferred
        return result

    def enable_environment(self, env_id):
        try:
            self.environments_manager.change_accept_tasks(env_id, True)
        except KeyError:
            return "No such environment"

    def disable_environment(self, env_id):
        try:
            self.environments_manager.change_accept_tasks(env_id, False)
        except KeyError:
            return "No such environment"

    def send_gossip(self, gossip, send_to):
        return self.p2pservice.send_gossip(gossip, send_to)

    def send_stop_gossip(self):
        return self.p2pservice.send_stop_gossip()

    def collect_gossip(self):
        return self.p2pservice.pop_gossips()

    def collect_stopped_peers(self):
        return self.p2pservice.pop_stop_gossip_form_peers()

    def collect_neighbours_loc_ranks(self):
        return self.p2pservice.pop_neighbours_loc_ranks()

    def push_local_rank(self, node_id, loc_rank):
        self.p2pservice.push_local_rank(node_id, loc_rank)

    @staticmethod
    def save_task_preset(preset_name, task_type, data):
        taskpreset.save_task_preset(preset_name, task_type, data)

    @staticmethod
    def get_task_presets(task_type):
        logger.info("Loading presets for {}".format(task_type))
        return taskpreset.get_task_presets(task_type)

    @staticmethod
    def delete_task_preset(task_type, preset_name):
        taskpreset.delete_task_preset(task_type, preset_name)

    def get_estimated_cost(self, task_type, options):
        if self.task_server is None:
            raise Exception('Cannot estimate costs')
        options['price'] = float(options['price'])
        options['subtask_time'] = float(options['subtask_time'])
        options['num_subtasks'] = int(options['num_subtasks'])
        return {
            'GNT': self.task_server.task_manager.get_estimated_cost(task_type,
                                                                    options),
            'ETH': float(self.transaction_system.eth_for_batch_payment(
                options['num_subtasks']) / denoms.ether),
        }

    def get_performance_values(self):
        return self.environments_manager.get_performance_values()

    @staticmethod
    def get_performance_mult() -> float:
        return MinPerformanceMultiplier.get()

    @staticmethod
    def set_performance_mult(multiplier: float):
        MinPerformanceMultiplier.set(multiplier)

    def _publish(self, event_name, *args, **kwargs):
        if self.rpc_publisher:
            self.rpc_publisher.publish(event_name, *args, **kwargs)

    def lock_config(self, on=True):
        self._publish(UI.evt_lock_config, on)

    def config_changed(self):
        self._publish(Environment.evt_opts_changed)

    def __get_nodemetadatamodel(self):
        return NodeMetadataModel(
            client=self,
            os=sys.platform,
            ver=golem.__version__
        )

    def connection_status(self):
        listen_port = self.get_p2p_port()
        task_server_port = self.get_task_server_port()

        if listen_port == 0 or task_server_port == 0:
            return "Application not listening, check config file."

        messages = []

        if self.node.port_statuses:
            status = ", ".join(
                "{}: {}".format(port, status)
                for port, status in self.node.port_statuses.items())
            messages.append("Port {}.".format(status))

        if self.get_connected_peers():
            messages.append("Connected")
        else:
            messages.append("Not connected to Golem Network, "
                            "check seed parameters.")

        return ' '.join(messages)

    def get_provider_status(self) -> Dict[str, Any]:
        # golem is starting
        if self.task_server is None:
            return {
                'status': 'golem is starting',
            }

        task_computer = self.task_server.task_computer

        # computing
        subtask_progress: Optional[ComputingSubtaskStateSnapshot] = \
            task_computer.get_progress()
        if subtask_progress is not None:
            return {
                'status': 'computing',
                'subtask': subtask_progress.__dict__,
            }

        # trying to get subtask from task
        waiting_for_task: Optional[str] = task_computer.waiting_for_task
        if waiting_for_task is not None:
            return {
                'status': 'waiting for task',
                'task_id_waited_for': waiting_for_task,
            }

        # not accepting tasks
        if not self.config_desc.accept_tasks:
            return {
                'status': 'not accepting tasks',
            }

        return {
            'status': 'idle',
        }

    @staticmethod
    def get_golem_version():
        return golem.__version__

    @staticmethod
    def get_golem_status():
        return StatusPublisher.last_status()

    @inlineCallbacks
    def activate_hw_preset(self, name, run_benchmarks=False):
        config_changed = HardwarePresets.update_config(name, self.config_desc)
        run_benchmarks = run_benchmarks or config_changed

        if hasattr(self, 'task_server') and self.task_server:
            deferred = self.task_server.change_config(
                self.config_desc, run_benchmarks=run_benchmarks)

            result = yield deferred
            logger.info('change hw config result: %r', result)
            return self.get_performance_values()

    def __lock_datadir(self):
        if not path.exists(self.datadir):
            # Create datadir if not exists yet.
            makedirs(self.datadir)
        self.__datadir_lock = open(path.join(self.datadir, "LOCK"), 'w')
        flags = filelock.LOCK_EX | filelock.LOCK_NB
        try:
            filelock.lock(self.__datadir_lock, flags)
        except IOError:
            raise IOError("Data dir {} used by other Golem instance"
                          .format(self.datadir))

    def _unlock_datadir(self):
        # solves locking issues on OS X
        try:
            filelock.unlock(self.__datadir_lock)
        except Exception:
            pass
        self.__datadir_lock.close()

    @staticmethod
    def enable_talkback(value):
        enable_sentry_logger(value)

    def block_node(self, node_id: str) -> Tuple[bool, Optional[str]]:
        if self.task_server is not None:
            try:
                self.task_server.acl.disallow(node_id, persist=True)
                return True, None

            except Exception as e:  # pylint: disable=broad-except
                return False, str(e)

        return False, 'Client is not ready'


class DoWorkService(LoopingCallService):
    _client = None  # type: Client

    def __init__(self, client: Client):
        super().__init__(interval_seconds=1)
        self._client = client
        self._check_ts = {}

    def start(self):
        super().start(now=False)

    def _run(self):
        # TODO: split it into separate services. Issue #2431

        if self._client.config_desc.send_pings:
            self._client.p2pservice.ping_peers(
                self._client.config_desc.pings_interval)

        try:
            self._client.p2pservice.sync_network()
        except Exception:
            logger.exception("p2pservice.sync_network failed")
        try:
            self._client.task_server.sync_network()
        except Exception:
            logger.exception("task_server.sync_network failed")
        try:
            self._client.resource_server.sync_network()
        except Exception:
            logger.exception("resource_server.sync_network failed")
        try:
            self._client.ranking.sync_network()
        except Exception:
            logger.exception("ranking.sync_network failed")

    def _time_for(self, key: Hashable, interval_seconds: float):
        now = time.time()
        if now >= self._check_ts.get(key, 0):
            self._check_ts[key] = now + interval_seconds
            return True
        return False


class MonitoringPublisherService(LoopingCallService):
    _task_server = None  # type: TaskServer

    def __init__(self,
                 task_server: TaskServer,
                 interval_seconds: int) -> None:
        super().__init__(interval_seconds)
        self._task_server = task_server

    def _run(self):
        dispatcher.send(
            signal='golem.monitor',
            event='stats_snapshot',
            known_tasks=len(self._task_server.task_keeper.get_all_tasks()),
            supported_tasks=len(self._task_server.task_keeper.supported_tasks),
            stats=self._task_server.task_computer.stats,
        )
        dispatcher.send(
            signal='golem.monitor',
            event='task_computer_snapshot',
            task_computer=self._task_server.task_computer,
        )
        dispatcher.send(
            signal='golem.monitor',
            event='requestor_stats_snapshot',
            current_stats=(self._task_server.task_manager
                           .requestor_stats_manager.get_current_stats()),
            finished_stats=(self._task_server.task_manager
                            .requestor_stats_manager.get_finished_stats())
        )


class NetworkConnectionPublisherService(LoopingCallService):
    _client = None  # type: Client

    def __init__(self,
                 client: Client,
                 interval_seconds: int) -> None:
        super().__init__(interval_seconds)
        self._client = client

    def _run_async(self):
        # Skip the async_run call and publish events in the main thread
        self._run()

    def _run(self):
        self._client._publish(Network.evt_connection,
                              self._client.connection_status())


class TaskArchiverService(LoopingCallService):
    _task_archiver = None  # type: TaskArchiver

    def __init__(self,
                 task_archiver: TaskArchiver) -> None:
        super().__init__(interval_seconds=TASKARCHIVE_MAINTENANCE_INTERVAL)
        self._task_archiver = task_archiver

    def _run(self):
        self._task_archiver.do_maintenance()


class ResourceCleanerService(LoopingCallService):
    _client = None  # type: Client
    older_than_seconds = 0  # type: int

    def __init__(self,
                 client: Client,
                 interval_seconds: int,
                 older_than_seconds: int) -> None:
        super().__init__(interval_seconds)
        self._client = client
        self.older_than_seconds = older_than_seconds

    def _run(self):
        # TODO: is any synchronization needed here? golemcli has none.
        # Issue #2432
        self._client.remove_distributed_files(self.older_than_seconds)
        self._client.remove_received_files(self.older_than_seconds)


class TaskCleanerService(LoopingCallService):
    _client = None  # type: Client

    def __init__(self,
                 client: Client,
                 interval_seconds: int) -> None:
        super().__init__(interval_seconds)
        self._client = client

    def _run(self):
        self._client.clean_old_tasks()


class MaskUpdateService(LoopingCallService):

    def __init__(
            self,
            task_manager: TaskManager,
            interval_seconds: int,
            update_num_bits: int
    ) -> None:
        self._task_manager: TaskManager = task_manager
        self._update_num_bits = update_num_bits
        self._interval = interval_seconds
        super().__init__(interval_seconds)

    def _run(self) -> None:
        logger.info('Updating masks')
        # Using list() because tasks could be changed by another thread
        for task_id, task in list(self._task_manager.tasks.items()):
            if not self._task_manager.task_needs_computation(task_id):
                continue
            task_state = self._task_manager.query_task_state(task_id)
            if task_state.elapsed_time < self._interval:
                continue

            self._task_manager.decrease_task_mask(
                task_id=task_id,
                num_bits=self._update_num_bits)
            logger.info('Updating mask for task %r Mask size: %r',
                        task_id, task.header.mask.num_bits)
