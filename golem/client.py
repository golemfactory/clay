import atexit
import logging
import sys
import time
import uuid
from collections import Iterable
from copy import copy, deepcopy
from os import path, makedirs
from threading import Lock, Thread
from typing import Dict

from pydispatch import dispatcher
from twisted.internet.defer import (inlineCallbacks, returnValue, gatherResults,
                                    Deferred)

import golem
from golem.appconfig import (AppConfig, PUBLISH_BALANCE_INTERVAL,
                             PUBLISH_TASKS_INTERVAL,
                             TASKARCHIVE_MAINTENANCE_INTERVAL)
from golem.clientconfigdescriptor import ClientConfigDescriptor, ConfigApprover
from golem.config.presets import HardwarePresetsMixin
from golem.core.async import AsyncRequest, async_run
from golem.core.common import to_unicode, string_to_timeout
from golem.core.fileshelper import du
from golem.core.hardware import HardwarePresets
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.service import LoopingCallService
from golem.core.simpleenv import get_local_datadir
from golem.core.simpleserializer import DictSerializer
from golem.core.threads import callback_wrapper
from golem.diag.service import DiagnosticsService, DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider
from golem.environments.environment import Environment as DefaultEnvironment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.model import Database
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MONITOR_CONFIG
from golem.network.concent.client import ConcentClientService
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
# noqa
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.resource.resource import get_resources_for_task, ResourceType
from golem.rpc.mapping.rpceventnames import Task, Network, Environment, UI, \
    Payments
from golem.rpc.session import Publisher
from golem.task import taskpreset
from golem.task.taskmanager import TaskManager
from golem.task.taskserver import TaskServer
from golem.task.taskstate import TaskTestStatus
from golem.task.tasktester import TaskTester
from golem.task.taskarchiver import TaskArchiver
from golem.tools import filelock
from golem.transactions.ethereum.ethereumtransactionsystem import \
    EthereumTransactionSystem

log = logging.getLogger("golem.client")


class ClientTaskComputerEventListener(object):
    def __init__(self, client):
        self.client = client

    def lock_config(self, on=True):
        self.client.lock_config(on)

    def config_changed(self):
        self.client.config_changed()


class Client(HardwarePresetsMixin):
    _services = []  # type: List[IService]

    def __init__(
            self,
            datadir=None,
            transaction_system=False,
            connect_to_known_hosts=True,
            use_docker_machine_manager=True,
            use_monitor=True,
            start_geth=False,
            start_geth_port=None,
            geth_address=None,
            **config_overrides):

        if not datadir:
            datadir = get_local_datadir('default')

        self.datadir = datadir
        self.__lock_datadir()
        self.lock = Lock()
        self.task_tester = None

        self.task_archiver = TaskArchiver(datadir)

        # Read and validate configuration
        config = AppConfig.load_config(datadir)
        self.config_desc = ClientConfigDescriptor()
        self.config_desc.init_from_app_config(config)

        for key, val in list(config_overrides.items()):
            if not hasattr(self.config_desc, key):
                self.quit()  # quit only closes underlying services (for now)
                raise AttributeError(
                    "Can't override nonexistent config entry '{}'".format(key))
            setattr(self.config_desc, key, val)

        self.config_approver = ConfigApprover(self.config_desc)

        log.info(
            'Client "%s", datadir: %s',
            self.config_desc.node_name,
            datadir
        )

        # Initialize database
        self.db = Database(datadir)

        # Hardware configuration
        HardwarePresets.initialize(self.datadir)
        HardwarePresets.update_config(self.config_desc.hardware_preset_name,
                                      self.config_desc)

        self.keys_auth = EllipticalKeysAuth(self.datadir)

        # NETWORK
        self.node = Node(node_name=self.config_desc.node_name,
                         prv_addr=self.config_desc.node_address,
                         key=self.keys_auth.get_key_id())

        self.p2pservice = None
        self.diag_service = None
        self.concent_service = ConcentClientService(
            enabled=False,
            signing_key=self.keys_auth._private_key,
            public_key=self.keys_auth.public_key,
        )

        self.task_server = None
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
                    interval_seconds=max(1, int(clean_resources_older_than/10)),
                    older_than_seconds=clean_resources_older_than))

        self.cfg = config

        self.ranking = Ranking(self)

        if transaction_system:
            # Bootstrap transaction system if enabled.
            # TODO: Transaction system (and possible other modules) should be
            #       modeled as a Service that run independently.
            #       The Client/Application should be a collection of services.
            self.transaction_system = EthereumTransactionSystem(
                datadir,
                self.keys_auth._private_key,
                start_geth=start_geth,
                start_port=start_geth_port,
                address=geth_address,
            )
        else:
            self.transaction_system = None

        self.use_docker_machine_manager = use_docker_machine_manager
        self.connect_to_known_hosts = connect_to_known_hosts
        self.environments_manager = EnvironmentsManager()
        self.daemon_manager = None

        self.rpc_publisher = None

        self.resource_server = None
        self.resource_port = 0
        self.last_get_resource_peers_time = time.time()
        self.get_resource_peers_interval = 5.0
        self.use_monitor = use_monitor
        self.monitor = None
        self.session_id = str(uuid.uuid4())

        dispatcher.connect(
            self.p2p_listener,
            signal='golem.p2p'
        )
        dispatcher.connect(
            self.taskmanager_listener,
            signal='golem.taskmanager'
        )

        atexit.register(self.quit)

    def configure_rpc(self, rpc_session):
        self.rpc_publisher = Publisher(rpc_session)
        StatusPublisher.set_publisher(self.rpc_publisher)

        if self.transaction_system:
            self._services.append(BalancePublisherService(
                self.rpc_publisher,
                self.transaction_system))

    def p2p_listener(self, sender, signal, event='default', **kwargs):
        if event == 'unreachable':
            self.node.port_status = kwargs.get('description', '')
            return
        if event == 'new_version':
            log.warning(
                'New version of golem available: %s',
                kwargs['version']
            )
            self._publish(Network.new_version, str(kwargs['version']))
            return

    def taskmanager_listener(self, sender, signal, event='default', **kwargs):
        if event != 'task_status_updated':
            return
        self._publish(Task.evt_task_status, kwargs['task_id'])

    # TODO: re-enable
    def sync(self):
        pass

    @report_calls(Component.client, 'start', stage=Stage.pre)
    def start(self):
        self.environments_manager.load_config(self.datadir)
        self.concent_service.start()

        if self.use_monitor and not self.monitor:
            self.init_monitor()
        try:
            self.start_network()
        except Exception:
            log.critical('Can\'t start network. Giving up.', exc_info=True)
            sys.exit(1)

        for service in self._services:
            if not service.running:
                service.start()

    @report_calls(Component.client, 'stop', stage=Stage.post)
    def stop(self):
        self.stop_network()

        for service in self._services:
            if service.running:
                service.stop()
        self.concent_service.stop()
        if self.task_server:
            self.task_server.task_computer.quit()
        if self.use_monitor and self.monitor:
            self.stop_monitor()
            self.monitor = None

    def start_network(self):
        log.info("Starting network ...")
        self.node.collect_network_info(self.config_desc.seed_host,
                                       use_ipv6=self.config_desc.use_ipv6)

        log.debug("Is super node? %s", self.node.is_super_node())

        if not self.p2pservice:
            self.p2pservice = P2PService(
                self.node,
                self.config_desc,
                self.keys_auth,
                connect_to_known_hosts=self.connect_to_known_hosts
            )

        if not self.task_server:
            self.task_server = TaskServer(
                self.node,
                self.config_desc,
                self.keys_auth, self,
                use_ipv6=self.config_desc.use_ipv6,
                use_docker_machine_manager=self.use_docker_machine_manager,
                task_archiver=self.task_archiver)

            monitoring_publisher_service = MonitoringPublisherService(
                    self.task_server,
                    interval_seconds=max(
                        int(self.config_desc.node_snapshot_interval),
                        1))
            monitoring_publisher_service.start()
            self._services.append(monitoring_publisher_service)

            if self.rpc_publisher:
                tasks_publisher_service = TasksPublisherService(
                    self.rpc_publisher,
                    self.task_server.task_manager)
                tasks_publisher_service.start()
                self._services.append(tasks_publisher_service)

            clean_tasks_older_than = \
                self.config_desc.clean_tasks_older_than_seconds
            if clean_tasks_older_than > 0:
                task_cleaner_service = TaskCleanerService(
                    self,
                    interval_seconds=max(1, int(clean_tasks_older_than/10)),
                    older_than_seconds=clean_tasks_older_than)
                task_cleaner_service.start()
                self._services.append(task_cleaner_service)

        dir_manager = self.task_server.task_computer.dir_manager

        log.info("Starting resource server ...")

        if not self.daemon_manager:
            self.daemon_manager = HyperdriveDaemonManager(self.datadir)
            self.daemon_manager.start()

        hyperdrive_addrs = self.daemon_manager.public_addresses(
            self.node.pub_addr)
        hyperdrive_ports = self.daemon_manager.ports()

        if not self.resource_server:
            resource_manager = HyperdriveResourceManager(dir_manager,
                                                         hyperdrive_addrs)
            self.resource_server = BaseResourceServer(resource_manager,
                                                      dir_manager,
                                                      self.keys_auth, self)
            self.task_server.restore_resources()

        def connect(ports):
            p2p_port, task_port = ports
            all_ports = ports + list(hyperdrive_ports)

            log.info('P2P server is listening on port %s', p2p_port)
            log.info('Task server is listening on port %s', task_port)

            if self.config_desc.use_upnp:
                self.start_upnp(all_ports)

            dispatcher.send(signal='golem.p2p', event='listening',
                            port=all_ports)

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
            log.error("Golem cannot listen on ports: %s", exceptions)
            StatusPublisher.publish(Component.client, 'start',
                                    stage=Stage.exception,
                                    data=[to_unicode(e) for e in exceptions])
            sys.exit(1)

        task = Deferred()
        p2p = Deferred()

        gatherResults([p2p, task], consumeErrors=True).addCallbacks(connect,
                                                                    terminate)
        log.info("Starting p2p server ...")
        resource_manager = self.resource_server.resource_manager
        self.p2pservice.task_server = self.task_server
        self.p2pservice.set_resource_server(self.resource_server)
        self.p2pservice.set_metadata_manager(resource_manager.peer_manager)
        self.p2pservice.start_accepting(listening_established=p2p.callback,
                                        listening_failure=p2p.errback)

        log.info("Starting task server ...")
        self.task_server.start_accepting(listening_established=task.callback,
                                         listening_failure=task.errback)

    def start_upnp(self, ports):
        self.port_mapper = PortMapperManager()
        self.port_mapper.discover()

        if self.port_mapper.available:
            for port in ports:
                self.port_mapper.create_mapping(port)
            self.port_mapper.update_node(self.node)

    def stop_network(self):
        if self.p2pservice:
            self.p2pservice.stop_accepting()
            self.p2pservice.disconnect()
        if self.task_server:
            self.task_server.stop_accepting()
            self.task_server.disconnect()
        if self.port_mapper:
            self.port_mapper.quit()

    def pause(self):
        for service in self._services:
            if service.running:
                service.stop()

        if self.p2pservice:
            self.p2pservice.pause()
            self.p2pservice.disconnect()
        if self.task_server:
            self.task_server.pause()
            self.task_server.disconnect()
            self.task_server.task_computer.quit()

    def resume(self):
        for service in self._services:
            if not service.running:
                service.start()

        if self.p2pservice:
            self.p2pservice.resume()
            self.p2pservice.connect_to_network()
        if self.task_server:
            self.task_server.resume()

    def init_monitor(self):
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
        self.monitor.shut_down()
        self.diag_service.stop()

    def connect(self, socket_address):
        if isinstance(socket_address, Iterable):
            socket_address = SocketAddress(
                socket_address[0],
                int(socket_address[1])
            )

        log.debug(
            "P2pservice connecting to %s on port %s",
            socket_address.address,
            socket_address.port
        )
        self.p2pservice.connect(socket_address)

    @report_calls(Component.client, 'quit', once=True)
    def quit(self):
        self.stop()

        if self.transaction_system:
            self.transaction_system.stop()
        if self.diag_service:
            self.diag_service.unregister_all()
        if self.daemon_manager:
            self.daemon_manager.stop()

        dispatcher.send(signal='golem.monitor', event='shutdown')

        if self.db:
            self.db.close()
        self._unlock_datadir()

    def enqueue_new_task(self, task_dict):
        # FIXME: Statement only for old DummyTask compatibility
        if isinstance(task_dict, dict):
            task = self.task_server.task_manager.create_task(task_dict)
        else:
            task = task_dict

        task_manager = self.task_server.task_manager
        task_manager.add_new_task(task)

        task_id = task.header.task_id

        tmp_dir = task.tmp_dir if hasattr(task, 'tmp_dir') else None
        files = get_resources_for_task(resource_header=None,
                                       resource_type=ResourceType.HASHES,
                                       tmp_dir=tmp_dir,
                                       resources=task.get_resources())

        def add_task(result):
            task_state = task_manager.tasks_states[task_id]
            task_state.resource_hash = result[0]

            request = AsyncRequest(task_manager.start_task, task_id)
            async_run(request, None, error)

        def error(e):
            log.error("Task %s creation failed: %s", task_id, e)

        deferred = self.resource_server.add_task(files, task_id)
        deferred.addCallbacks(add_task, error)
        return task

    def task_resource_send(self, task_id):
        self.task_server.task_manager.resources_send(task_id)

    def task_resource_collected(self, task_id, unpack_delta=True):
        self.task_server.task_computer.task_resource_collected(
            task_id,
            unpack_delta
        )

    def task_resource_failure(self, task_id, reason):
        self.task_server.task_computer.task_resource_failure(task_id, reason)

    def set_resource_port(self, resource_port):
        self.resource_port = resource_port
        self.p2pservice.set_resource_peer(
            self.node.prv_addr,
            self.resource_port
        )

    def run_test_task(self, t_dict):
        if self.task_tester is None:
            request = AsyncRequest(self._run_test_task, t_dict)
            async_run(request)
            return True

        if self.rpc_publisher:
            self.rpc_publisher.publish(
                Task.evt_task_test_status,
                TaskTestStatus.error,
                "Another test is running"
            )
        return False

    def _run_test_task(self, t_dict):

        def on_success(*args, **kwargs):
            self.task_tester = None
            self._publish(Task.evt_task_test_status,
                          TaskTestStatus.success, *args, **kwargs)

        def on_error(*args, **kwargs):
            self.task_tester = None
            self._publish(Task.evt_task_test_status,
                          TaskTestStatus.error, *args, **kwargs)

        try:
            dictionary = DictSerializer.load(t_dict)
            task = self.task_server.task_manager.create_task(
                dictionary=dictionary, minimal=True
            )
        except Exception as e:
            return on_error(to_unicode(e))

        self.task_tester = TaskTester(task, self.datadir, on_success, on_error)
        self.task_tester.run()
        self._publish(Task.evt_task_test_status, TaskTestStatus.started, True)

    def abort_test_task(self):
        with self.lock:
            if self.task_tester is not None:
                self.task_tester.end_comp()
                return True
            return False

    def create_task(self, t_dict):
        try:
            task = self.enqueue_new_task(t_dict)
            return str(task.header.task_id)
        except Exception:
            log.exception("Cannot create task {}".format(t_dict))

    def abort_task(self, task_id):
        self.task_server.task_manager.abort_task(task_id)

    def restart_task(self, task_id):
        task_manager = self.task_server.task_manager

        # Task state is changed to restarted and stays this way until it's
        # deleted from task manager.
        task_manager.put_task_in_restarted_state(task_id)

        # Create new task that is a copy of the definition of the old one.
        # It has a new deadline and a new task id.
        task_dict = deepcopy(
            task_manager.get_task_definition_dict(
                task_manager.tasks[task_id]))
        del task_dict['id']

        return self.create_task(task_dict)

    def restart_frame_subtasks(self, task_id, frame):
        self.task_server.task_manager.restart_frame_subtasks(task_id, frame)

    def restart_subtask(self, subtask_id):
        self.task_server.task_manager.restart_subtask(subtask_id)

    def delete_task(self, task_id):
        self.remove_task_header(task_id)
        self.remove_task(task_id)
        self.task_server.task_manager.delete_task(task_id)

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

    def get_resource_peers(self):
        self.p2pservice.send_get_resource_peers()

    def get_peers(self):
        return list(self.p2pservice.peers.values())

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

    def load_keys_from_file(self, file_name):
        if file_name != "":
            return self.keys_auth.load_from_file(file_name)
        return False

    def save_keys_to_files(self, private_key_path, public_key_path):
        return self.keys_auth.save_to_files(private_key_path, public_key_path)

    def get_key_id(self):
        return self.get_client_id()

    def get_difficulty(self):
        return self.keys_auth.get_difficulty()

    def get_client_id(self):
        key_id = self.keys_auth.get_key_id()
        return str(key_id) if key_id else None

    def get_node_key(self):
        key = self.node.key
        return str(key) if key else None

    def get_settings(self):
        return DictSerializer.dump(self.config_desc)

    def get_setting(self, key):
        if not hasattr(self.config_desc, key):
            raise KeyError("Unknown setting: {}".format(key))

        value = getattr(self.config_desc, key)
        if key in ConfigApprover.numeric_opt:
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

    def get_task(self, task_id):
        return self.task_server.task_manager.get_task_dict(task_id)

    def get_tasks(self, task_id=None):
        if task_id:
            return self.task_server.task_manager.get_task_dict(task_id)
        return self.task_server.task_manager.get_tasks_dict()

    def get_subtasks(self, task_id):
        return self.task_server.task_manager.get_subtasks_dict(task_id)

    def get_subtasks_borders(self, task_id, part=1):
        return self.task_server.task_manager.get_subtasks_borders(task_id,
                                                                  part)

    def get_subtasks_frames(self, task_id):
        return self.task_server.task_manager.get_output_states(task_id)

    def get_subtask(self, subtask_id):
        return self.task_server.task_manager.get_subtask_dict(subtask_id)

    def get_task_preview(self, task_id, single=False):
        return self.task_server.task_manager.get_task_preview(task_id,
                                                              single=single)

    def get_task_stats(self) -> Dict[str, int]:
        return {
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

    @inlineCallbacks
    def get_balance(self):
        if self.use_transaction_system():
            req = AsyncRequest(self.transaction_system.get_balance)
            b, ab, d = yield async_run(req)
            if b is not None:
                returnValue((str(b), str(ab), str(d)))
        returnValue((None, None, None))

    def get_payments_list(self):
        if self.use_transaction_system():
            return self.transaction_system.get_payments_list()
        return ()

    def get_incomes_list(self):
        if self.use_transaction_system():
            return self.transaction_system.get_incoming_payments()
        return []

    def get_task_cost(self, task_id):
        """
        Get current cost of the task defined by @task_id
        :param task_id: Task ID
        :return: Cost of the task
        """
        cost = self.task_server.task_manager.get_payment_for_task_id(task_id)
        if cost is None:
            return 0.0
        return cost

    def use_transaction_system(self):
        return bool(self.transaction_system)

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
        self.cfg.change_config(self.config_desc)
        self.upsert_hw_preset(HardwarePresets.from_config(self.config_desc))

        if self.p2pservice:
            self.p2pservice.change_config(self.config_desc)
        if self.task_server:
            self.task_server.change_config(self.config_desc,
                                           run_benchmarks=run_benchmarks)
        dispatcher.send(
            signal='golem.monitor',
            event='config_update',
            meta_data=self.__get_nodemetadatamodel()
        )

    def register_nodes_manager_client(self, nodes_manager_client):
        self.nodes_manager_client = nodes_manager_client

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout):
        self.task_server.change_timeouts(
            task_id,
            full_task_timeout,
            subtask_timeout
        )

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
        return {"computing": self.get_computed_files_dir(),
                "received": self.get_received_files_dir(),
                "distributed": self.get_distributed_files_dir()}

    def get_res_dirs_sizes(self):
        return {str(name): str(du(d))
                for name, d in list(self.get_res_dirs().items())}

    def get_res_dir(self, dir_type):
        if dir_type == DirectoryType.COMPUTED:
            return self.get_computed_files_dir()
        elif dir_type == DirectoryType.DISTRIBUTED:
            return self.get_distributed_files_dir()
        elif dir_type == DirectoryType.RECEIVED:
            return self.get_received_files_dir()
        raise Exception("Unknown dir type: {}".format(dir_type))

    def get_computed_files_dir(self):
        return str(self.task_server.get_task_computer_root())

    def get_received_files_dir(self):
        return str(self.task_server.task_manager.get_task_manager_root())

    def get_distributed_files_dir(self):
        return str(self.resource_server.get_distributed_resource_root())

    def clear_dir(self, dir_type, older_than_seconds: int = 0):
        if dir_type == DirectoryType.COMPUTED:
            return self.remove_computed_files(older_than_seconds)
        elif dir_type == DirectoryType.DISTRIBUTED:
            return self.remove_distributed_files(older_than_seconds)
        elif dir_type == DirectoryType.RECEIVED:
            return self.remove_received_files(older_than_seconds)
        raise Exception("Unknown dir type: {}".format(dir_type))

    def remove_computed_files(self, older_than_seconds: int = 0):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(self.get_computed_files_dir(), older_than_seconds)

    def remove_distributed_files(self, older_than_seconds: int = 0):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(self.get_distributed_files_dir(),
                              older_than_seconds)

    def remove_received_files(self, older_than_seconds: int = 0):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(self.get_received_files_dir(), older_than_seconds)

    def remove_task(self, task_id):
        self.p2pservice.remove_task(task_id)

    def remove_task_header(self, task_id):
        self.task_server.remove_task_header(task_id)

    def get_known_tasks(self):
        headers = {}
        for key, header in list(self.task_server.task_keeper.task_headers.items()):  # noqa
            headers[str(key)] = DictSerializer.dump(header)
        return headers

    def get_environments(self):
        envs = copy(self.environments_manager.get_environments())
        return [{
            'id': str(env.get_id()),
            'supported': bool(env.check_support()),
            'accepted': env.is_accepted(),
            'performance': env.get_performance(),
            'description': str(env.short_description)
        } for env in envs]

    @inlineCallbacks
    def run_benchmark(self, env_id):
        deferred = Deferred()

        if env_id != DefaultEnvironment.get_id():
            benchmark_manager = self.task_server.benchmark_manager
            benchmark_manager.run_benchmark_for_env_id(env_id,
                                                       deferred.callback,
                                                       deferred.errback)
            result = yield deferred
            returnValue(result)
        else:

            kwargs = {'func': DefaultEnvironment.run_default_benchmark,
                      'callback': deferred.callback,
                      'errback': deferred.errback,
                      'num_cores': self.config_desc.num_cores,
                      'save': True}
            Thread(target=callback_wrapper, kwargs=kwargs).start()
            result = yield deferred
            returnValue(result)

    def enable_environment(self, env_id):
        self.environments_manager.change_accept_tasks(env_id, True)

    def disable_environment(self, env_id):
        self.environments_manager.change_accept_tasks(env_id, False)

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

    def check_payments(self):
        if not self.transaction_system:
            return
        after_deadline_nodes = self.transaction_system.check_payments()
        for node_id in after_deadline_nodes:
            Trust.PAYMENT.decrease(node_id)

    @staticmethod
    def save_task_preset(preset_name, task_type, data):
        taskpreset.save_task_preset(preset_name, task_type, data)

    @staticmethod
    def get_task_presets(task_type):
        log.info("Loading presets for {}".format(task_type))
        return taskpreset.get_task_presets(task_type)

    @staticmethod
    def delete_task_preset(task_type, preset_name):
        taskpreset.delete_task_preset(task_type, preset_name)

    def get_estimated_cost(self, task_type, options):
        options['price'] = float(options['price'])
        options['subtask_time'] = float(options['subtask_time'])
        options['num_subtasks'] = int(options['num_subtasks'])
        return self.task_server.task_manager.get_estimated_cost(task_type,
                                                                options)

    def get_performance_values(self):
        return self.environments_manager.get_performance_values()

    def _publish(self, event_name, *args, **kwargs):
        if self.rpc_publisher:
            self.rpc_publisher.publish(event_name, *args, **kwargs)

    def lock_config(self, on=True):
        self._publish(UI.evt_lock_config, on)

    def config_changed(self):
        self._publish(Environment.evt_opts_changed)

    def __get_nodemetadatamodel(self):
        return NodeMetadataModel(
            self.get_client_id(),
            self.session_id,
            sys.platform,
            golem.__version__,
            self.config_desc
        )

    def __try_to_change_to_number(
        self,
        old_value,
        new_value,
        to_int=False,
        to_float=False,
        name="Config"
    ):
        try:
            if to_int:
                new_value = int(new_value)
            elif to_float:
                new_value = float(new_value)
        except ValueError:
            log.warning("%s value '%s' is not a number", name, new_value)
            new_value = old_value
        return new_value

    def connection_status(self):
        listen_port = self.get_p2p_port()
        task_server_port = self.get_task_server_port()

        if listen_port == 0 or task_server_port == 0:
            return "Application not listening, check config file."

        messages = []

        if self.node.port_status:
            statuses = self.node.port_status.split('\n')
            failures = [e for e in statuses if e.find('open') == -1]
            messages.append("Port " + ", ".join(failures) + ".")

        if self.get_connected_peers():
            messages.append("Connected")
        else:
            messages.append("Not connected to Golem Network, "
                            "check seed parameters.")

        return ' '.join(messages)

    def get_status(self):
        progress = self.task_server.task_computer.get_progresses()
        if len(progress) > 0:
            msg = "Computing {} subtask(s):".format(len(progress))
            for k, v in list(progress.items()):
                msg = "{} \n {} ({}%)\n".format(msg, k, v.get_progress() * 100)
        elif self.config_desc.accept_tasks:
            msg = "Waiting for tasks...\n"
        else:
            msg = "Not accepting tasks\n"

        peers = self.p2pservice.get_peers()

        msg += "Active peers in network: {}\n".format(len(peers))
        return msg

    @staticmethod
    def get_golem_version():
        return golem.__version__

    @staticmethod
    def get_golem_status():
        return StatusPublisher.last_status()

    def activate_hw_preset(self, name, run_benchmarks=False):
        HardwarePresets.update_config(name, self.config_desc)
        if hasattr(self, 'task_server') and self.task_server:
            self.task_server.change_config(
                self.config_desc,
                run_benchmarks=run_benchmarks
            )

    def __lock_datadir(self):
        if not path.exists(self.datadir):
            # Create datadir if not exists yet.
            # TODO: It looks we have the same code in many places
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


class DoWorkService(LoopingCallService):
    _client = None  # type: Client

    def __init__(self, client: Client):
        super().__init__(interval_seconds=1)
        self._client = client

    def start(self):
        super().start(now=False)

    def _run(self):
        # TODO: split it into separate services

        if self._client.config_desc.send_pings:
            self._client.p2pservice.ping_peers(
                self._client.config_desc.pings_interval)

        try:
            self._client.p2pservice.sync_network()
        except Exception:
            log.exception("p2pservice.sync_network failed")
        try:
            self._client.task_server.sync_network()
        except Exception:
            log.exception("task_server.sync_network failed")
        try:
            self._client.resource_server.sync_network()
        except Exception:
            log.exception("resource_server.sync_network failed")
        try:
            self._client.ranking.sync_network()
        except Exception:
            log.exception("ranking.sync_network failed")
        try:
            self._client.check_payments()
        except Exception:
            log.exception("check_payments failed")


class MonitoringPublisherService(LoopingCallService):
    _task_server = None  # type: TaskServer

    def __init__(self,
                 task_server: TaskServer,
                 interval_seconds: int):
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


class NetworkConnectionPublisherService(LoopingCallService):
    _client = None  # type: Client

    def __init__(self,
                 client: Client,
                 interval_seconds: int):
        super().__init__(interval_seconds)
        self._client = client

    def _run(self):
        self._client._publish(Network.evt_connection,
                              self._client.connection_status())


class TasksPublisherService(LoopingCallService):
    _rpc_publisher = None  # type: Publisher
    _task_manager = None  # type: TaskManager

    def __init__(self,
                 rpc_publisher: Publisher,
                 task_manager: TaskManager):
        super().__init__(interval_seconds=int(PUBLISH_TASKS_INTERVAL))
        self._rpc_publisher = rpc_publisher
        self._task_manager = task_manager

    def _run(self):
        self._rpc_publisher.publish(Task.evt_task_list,
                                    self._task_manager.get_tasks_dict())


class TaskArchiverService(LoopingCallService):
    _task_archiver = None  # type: TaskArchiver

    def __init__(self,
                 task_archiver: TaskArchiver):
        super().__init__(interval_seconds=TASKARCHIVE_MAINTENANCE_INTERVAL)
        self._task_archiver = task_archiver

    def _run(self):
        self._task_archiver.do_maintenance()


class BalancePublisherService(LoopingCallService):

    _rpc_publisher = None  # type: Publisher
    _transaction_system = None  # type: EthereumTransactionSystem

    def __init__(self,
                 rpc_publisher: Publisher,
                 transaction_system: EthereumTransactionSystem):
        super().__init__(interval_seconds=int(PUBLISH_BALANCE_INTERVAL))
        self._rpc_publisher = rpc_publisher
        self._transaction_system = transaction_system

    def _run(self):
        try:
            gnt, av_gnt, eth = self._transaction_system.get_balance()
        except Exception as exc:
            log.debug('Error retrieving balance: %s', exc)
        else:
            self._rpc_publisher.publish(Payments.evt_balance, {
                'GNT': str(gnt),
                'GNT_available': str(av_gnt),
                'ETH': str(eth)
            })


class ResourceCleanerService(LoopingCallService):
    _client = None  # type: Client
    older_than_seconds = 0  # type: int

    def __init__(self,
                 client: Client,
                 interval_seconds: int,
                 older_than_seconds: int):
        super().__init__(interval_seconds)
        self._client = client
        self.older_than_seconds = older_than_seconds

    def _run(self):
        # TODO: is any synchronization needed here? golemcli has none.
        self._client.remove_computed_files(self.older_than_seconds)
        self._client.remove_distributed_files(self.older_than_seconds)
        self._client.remove_received_files(self.older_than_seconds)


class TaskCleanerService(LoopingCallService):
    _client = None  # type: Client
    older_than_seconds = 0  # type: int

    def __init__(self,
                 client: Client,
                 interval_seconds: int,
                 older_than_seconds: int):
        super().__init__(interval_seconds)
        self._client = client
        self.older_than_seconds = older_than_seconds

    def _run(self):
        now = time.time()
        for task in self._client.get_tasks():
            deadline = task['time_started'] \
                       + string_to_timeout(task['timeout'])\
                       + self.older_than_seconds
            if deadline <= now:
                log.info('Task %s got too old. Deleting.', task['id'])
                self._client.delete_task(task['id'])
