import atexit
import logging
import sys
import time
import uuid
from collections import Iterable
from copy import copy
from os import path, makedirs
from threading import Lock

from pydispatch import dispatcher
from twisted.internet import task
from twisted.internet.defer import (inlineCallbacks, returnValue, Deferred)

from golem.appconfig import (AppConfig, PUBLISH_BALANCE_INTERVAL,
                             PUBLISH_TASKS_INTERVAL)
from golem.clientconfigdescriptor import ClientConfigDescriptor, ConfigApprover
from golem.config.presets import HardwarePresetsMixin
from golem.core.async import AsyncRequest, async_run
from golem.core.common import to_unicode
from golem.core.fileshelper import du
from golem.core.hardware import HardwarePresets
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.simpleenv import get_local_datadir
from golem.core.simpleserializer import DictSerializer
from golem.core.variables import APP_VERSION
from golem.diag.service import DiagnosticsService, DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.manager.nodestatesnapshot import NodeStateSnapshot
from golem.model import Database, Account
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MONITOR_CONFIG
from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.network.p2p.node import Node
from golem.network.p2p.peersession import PeerSessionInfo
from golem.network.p2p.taskservice import TaskService
from golem.network.transport.tcpnetwork import SocketAddress
from golem.ranking.helper.trust import Trust
from golem.ranking.ranking import Ranking
from golem.report import Component, Stage, StatusPublisher, report_calls
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.dirmanager import DirManager, DirectoryType
# noqa
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.rpc.mapping.aliases import Task, Network, Environment, UI, Payments
from golem.rpc.session import Publisher
from golem.task import taskpreset
from golem.task.taskbase import resource_types
from golem.task.taskserver import TaskServer
from golem.task.taskstate import TaskTestStatus
from golem.task.tasktester import TaskTester
from golem.tools import filelock
from golem.transactions.ethereum.ethereumtransactionsystem import \
    EthereumTransactionSystem
from golem.utils import encode_hex

from devp2p.app import BaseApp
from devp2p.discovery import NodeDiscovery
from devp2p.peermanager import PeerManager
from devp2p.service import BaseService
import ethereum.slogging as slogging
from golem.network.p2p.golemservice import GolemService

devp2plog = slogging.get_logger('app')
log = logging.getLogger("golem.client")


class ClientTaskComputerEventListener(object):
    def __init__(self, client):
        self.client = client

    def lock_config(self, on=True):
        self.client.lock_config(on)

    def config_changed(self):
        self.client.config_changed()


class Client(BaseApp, HardwarePresetsMixin):
    client_name = 'golem'
    default_config = dict(BaseApp.default_config)
    available_services = [NodeDiscovery, PeerManager, GolemService, TaskService]

    def __init__(
            self,
            datadir=None,
            transaction_system=False,
            connect_to_known_hosts=True,
            use_docker_machine_manager=True,
            use_monitor=True,
            geth_port=None,
            **config_overrides):

        slogging.configure(u':info')
        devp2plog.info('starting')

        if not datadir:
            datadir = get_local_datadir('default')

        self.datadir = datadir
        self.__lock_datadir()
        self.lock = Lock()
        self.task_tester = None

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
        self.cfg = config
        self.resource_port = 0
        self.get_resource_peers_interval = 5.0
        self.use_monitor = use_monitor
        self.session_id = str(uuid.uuid4())
        self.send_snapshot = False
        self.snapshot_lock = Lock()

        self.use_docker_machine_manager = use_docker_machine_manager
        self.connect_to_known_hosts = connect_to_known_hosts

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
        self.environments_manager = EnvironmentsManager()

        self.task_server = None
        self.resource_server = None
        self.diag_service = None
        self.daemon_manager = None
        self.rpc_publisher = None
        self.monitor = None
        self.nodes_manager_client = None

        self.node = Node(node_name=self.config_desc.node_name,
                         prv_addr=self.config_desc.node_address,
                         key=self.keys_auth.get_key_id())


        self.last_nss_time = time.time()
        self.last_net_check_time = time.time()
        self.last_balance_time = time.time()
        self.last_tasks_time = time.time()
        self.last_get_resource_peers_time = time.time()
        self.last_node_state_snapshot = None

        self.do_work_task = task.LoopingCall(self.__do_work)
        self.publish_task = task.LoopingCall(self.__publish_events)

        self.ranking = Ranking(self)
        if transaction_system:
            # Bootstrap transaction system if enabled.
            # TODO: Transaction system (and possible other modules) should be
            #       modeled as a Service that run independently.
            #       The Client/Application should be a collection of services.
            self.transaction_system = EthereumTransactionSystem(
                datadir, encode_hex(self.keys_auth._private_key), geth_port)
        else:
            self.transaction_system = None

        dispatcher.connect(
            self.p2p_listener,
            signal='golem.p2p'
        )
        dispatcher.connect(
            self.taskmanager_listener,
            signal='golem.taskmanager'
        )

        from golem.p2pconfig import p2pconfig
        self.configp2p = p2pconfig
        BaseApp.__init__(self, self.configp2p)

        atexit.register(self.quit)

    def configure_rpc(self, rpc_session):
        self.rpc_publisher = Publisher(rpc_session)
        StatusPublisher.set_publisher(self.rpc_publisher)

    def p2p_listener(self, sender, signal, event='default', **kwargs):
        if event != 'unreachable':
            return
        self.node.port_status = kwargs.get('description', '')

    def taskmanager_listener(self, sender, signal, event='default', **kwargs):
        if event != 'task_status_updated':
            return
        self._publish(Task.evt_task_status, kwargs['task_id'])

    # TODO: re-enable
    def sync(self):
        pass

    @report_calls(Component.client, 'start', stage=Stage.pre)
    def start(self):
        if self.use_monitor and not self.monitor:
            self.init_monitor()
        try:
            self.start_network()
        except Exception:
            log.critical('Can\'t start network. Giving up.', exc_info=True)
            sys.exit(1)

        self.do_work_task.start(1, False)
        self.publish_task.start(1, True)

    @report_calls(Component.client, 'stop', stage=Stage.post)
    def stop(self):
        self.stop_network()
        if self.do_work_task.running:
            self.do_work_task.stop()
        if self.publish_task.running:
            self.publish_task.stop()
        if self.task_server:
            self.task_server.task_computer.quit()
        if self.use_monitor and self.monitor:
            self.stop_monitor()
            self.monitor = None

    @report_calls(Component.client, 'start')
    def start_network(self):
        self.node.collect_network_info(self.config_desc.seed_host,
                                       use_ipv6=self.config_desc.use_ipv6)
        log.debug("Is super node? %s", self.node.is_super_node())

        self.task_server = TaskServer(
            self.node,
            self.config_desc,
            self.keys_auth,
            client=self,
            task_service=self.services['task_service'],
            use_ipv6=self.config_desc.use_ipv6,
            use_docker_machine_manager=self.use_docker_machine_manager)

        dir_manager = self.task_server.task_computer.dir_manager

        log.info("Starting resource server ...")

        if not self.daemon_manager:
            self.daemon_manager = HyperdriveDaemonManager(self.datadir)
            self.daemon_manager.start()

        if not self.resource_server:
            resource_manager = HyperdriveResourceManager(dir_manager)
            self.resource_server = BaseResourceServer(resource_manager,
                                                      dir_manager,
                                                      self.keys_auth, self)

        self.services['golem_service'].set_task_server(self.task_server)

        hyperdrive_ports = self.daemon_manager.ports()
        dispatcher.send(signal='golem.p2p', event='listening',
                        port=[self.get_p2p_port()] + list(hyperdrive_ports))

    def start_devp2p(self):
        log.info("Starting network ...")

        self.config['node'] = {}
        self.config['node']['privkey_hex'] = encode_hex(
            self.keys_auth._private_key)
        self.config['node']['pubkey_hex'] = encode_hex(
            self.keys_auth.public_key)
        self.config['node']['id'] = encode_hex(self.keys_auth.public_key)
        self.config['node']['node_name'] = self.config_desc.node_name

        self.config['discovery']['bootstrap_nodes'].append(
            str("enode://%s@%s:%s" % (self.configp2p['node']['pubkey_hex'],
                "127.0.0.1", self.config['p2p']["listen_port"])).encode(
                'utf-8')
        )

        devp2plog.info(self.config['discovery']['bootstrap_nodes'])

        for service in Client.available_services:
            assert issubclass(service, BaseService)
            assert service.name not in self.services
            service.register_with_app(self)
            assert hasattr(self.services, service.name)

        BaseApp.start(self)

    def stop_network(self):
        pass

    def pause(self):
        if self.do_work_task.running:
            self.do_work_task.stop()
        if self.publish_task.running:
            self.publish_task.stop()

        if self.task_server:
            self.task_server.pause()
            self.task_server.disconnect()
            self.task_server.task_computer.quit()

    def resume(self):
        if not self.do_work_task.running:
            self.do_work_task.start(1, False)
        if not self.publish_task.running:
            self.publish_task.start(1, True)

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
        self.diag_service.start_looping_call()

    def stop_monitor(self):
        self.monitor.shut_down()
        self.diag_service.stop_looping_call()

    def connect(self, socket_address=None, node_id=""):
        self.services['peermanager'].connect(socket_address, node_id)

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

    def key_changed(self):
        self.node.key = self.keys_auth.get_key_id()
        self.task_server.key_changed()

    def enqueue_new_task(self, task_dict):
        # FIXME: Statement only for DummyTask compatibility
        if isinstance(task_dict, dict):
            task = self.task_server.task_manager.create_task(task_dict)
        else:
            task = task_dict

        resource_manager = self.resource_server.resource_manager
        task_manager = self.task_server.task_manager
        task_manager.add_new_task(task)

        task_id = task.header.task_id
        key_id = self.keys_auth.key_id

        options = resource_manager.build_client_options(key_id)
        files = task.get_resources(None, resource_types["hashes"])

        def add_task(_):
            request = AsyncRequest(task_manager.start_task, task_id)
            async_run(request, None, error)

        def error(e):
            log.error("Task %s creation failed: %s", task_id, e)

        deferred = self.resource_server.add_task(files, task_id, options)
        deferred.addCallbacks(add_task, error)
        return task

    def task_resource_send(self, task_id):
        self.task_server.task_manager.resources_send(task_id)

    def task_resource_collected(self, task_id, unpack_delta=True):
        self.task_server.task_computer.resource_given(task_id)

    def task_resource_failure(self, task_id, reason):
        self.task_server.task_computer.task_resource_failure(task_id, reason)

    def set_resource_port(self, resource_port):
        self.resource_port = resource_port

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
        self.task_server.task_manager.restart_task(task_id)

    def restart_frame_subtasks(self, task_id, frame):
        self.task_server.task_manager.restart_frame_subtasks(task_id, frame)

    def restart_subtask(self, subtask_id):
        self.task_server.task_manager.restart_subtask(subtask_id)

    def pause_task(self, task_id):
        self.task_server.task_manager.pause_task(task_id)

    def resume_task(self, task_id):
        self.task_server.task_manager.resume_task(task_id)

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
        pass

    def get_suggested_addr(self, key_id):
        return self.services['golem_service'].suggested_address.get(key_id)

    def get_suggested_conn_reverse(self, key_id):
        return self.services['golem_service'].get_suggested_conn_reverse(key_id)

    def get_resource_peers(self):
        pass

    def get_peers(self):
        return self.services['peermanager'].peers

    def get_known_peers(self):
        peers = self.get_peers()
        return [
            DictSerializer.dump(PeerSessionInfo(p), typed=False) for p in peers
        ]

    def get_connected_peers(self):
        peers = self.get_peers()
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
        return self.configp2p["p2p"]['listen_port']

    def get_task_count(self):
        return len(self.task_server.task_keeper.get_all_tasks())

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

    def get_task_stats(self):
        return {
            'in_network': self.get_task_count(),
            'supported': self.get_supported_task_count(),
            'subtasks_computed': self.get_computed_task_count(),
            'subtasks_with_errors': self.get_error_task_count(),
            'subtasks_with_timeout': self.get_timeout_task_count()
        }

    def get_supported_task_count(self):
        return len(self.task_server.task_keeper.supported_tasks)

    def get_computed_task_count(self):
        return self.task_server.task_computer.stats.get_stats('computed_tasks')

    def get_timeout_task_count(self):
        return self.task_server\
            .task_computer.stats.get_stats('tasks_with_timeout')

    def get_error_task_count(self):
        return self.task_server\
            .task_computer.stats.get_stats('tasks_with_errors')

    def get_payment_address(self):
        address = self.transaction_system.get_payment_address()
        return str(address) if address else None

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

    def get_description(self):
        try:
            account, _ = Account.get_or_create(node_id=self.get_client_id())
            return account.description
        except Exception as e:
            return "An error has occurred {}".format(e)

    def change_description(self, description):
        self.get_description()
        q = Account.update(description=description)\
            .where(Account.node_id == self.get_client_id())
        q.execute()

    def use_ranking(self):
        return bool(self.ranking)

    def want_to_start_task_session(self, key_id, node_id, conn_id):
        pass

    def inform_about_task_nat_hole(
            self,
            key_id,
            rv_key_id,
            addr,
            port,
            ans_conn_id
            ):
        pass

    def inform_about_nat_traverse_failure(self, key_id, res_key_id, conn_id):
        pass

    # CLIENT CONFIGURATION
    def set_rpc_server(self, rpc_server):
        self.rpc_server = rpc_server
        return self.rpc_server.add_service(self)

    def change_config(self, new_config_desc, run_benchmarks=False):
        self.config_desc = self.config_approver.change_config(new_config_desc)
        self.cfg.change_config(self.config_desc)
        self.upsert_hw_preset(HardwarePresets.from_config(self.config_desc))
        if self.task_server:
            self.task_server.change_config(
                self.config_desc,
                run_benchmarks=run_benchmarks
            )
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

    def clear_dir(self, dir_type):
        if dir_type == DirectoryType.COMPUTED:
            return self.remove_computed_files()
        elif dir_type == DirectoryType.DISTRIBUTED:
            return self.remove_distributed_files()
        elif dir_type == DirectoryType.RECEIVED:
            return self.remove_received_files()
        raise Exception("Unknown dir type: {}".format(dir_type))

    def remove_computed_files(self):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(self.get_computed_files_dir())

    def remove_distributed_files(self):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(self.get_distributed_files_dir())

    def remove_received_files(self):
        dir_manager = DirManager(self.datadir)
        dir_manager.clear_dir(self.get_received_files_dir())

    def remove_task(self, task_id):
        self.services['golem_service'].remove_task(task_id)

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
            'supported': env.supported(),
            'accepted': env.is_accepted(),
            'performance': env.get_performance(self.config_desc),
            'description': str(env.short_description)
        } for env in envs]

    @inlineCallbacks
    def run_benchmark(self, env_id):
        # TODO: move benchmarks to environments
        from apps.blender.blenderenvironment import BlenderEnvironment
        from apps.lux.luxenvironment import LuxRenderEnvironment

        deferred = Deferred()

        if env_id == BlenderEnvironment.get_id():
            self.task_server.task_computer.run_blender_benchmark(
                deferred.callback, deferred.errback
            )
        elif env_id == LuxRenderEnvironment.get_id():
            self.task_server.task_computer.run_lux_benchmark(
                deferred.callback, deferred.errback
            )
        else:
            raise Exception("Unknown environment: {}".format(env_id))

        result = yield deferred
        returnValue(result)

    def enable_environment(self, env_id):
        self.environments_manager.change_accept_tasks(env_id, True)

    def disable_environment(self, env_id):
        self.environments_manager.change_accept_tasks(env_id, False)

    def send_gossip(self, gossip, send_to):
        pass

    def send_stop_gossip(self):
        pass

    def collect_gossip(self):
        return []

    def collect_stopped_peers(self):
        pass

    def collect_neighbours_loc_ranks(self):
        return []

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
            APP_VERSION,
            self.get_description(),
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

    def __do_work(self):
        try:
            self.services['golem_service'].get_tasks()
        except Exception:
            log.exception("golem service task roadcast failed")
        try:
            self.task_server.sync_network()
        except Exception:
            log.exception("task_server.sync_network failed")
        try:
            self.resource_server.sync_network()
        except Exception:
            log.exception("resource_server.sync_network failed")
        try:
            self.ranking.sync_network()
        except Exception:
            log.exception("ranking.sync_network failed")
        try:
            self.check_payments()
        except Exception:
            log.exception("check_payments failed")

    @inlineCallbacks
    def __publish_events(self):
        now = time.time()
        delta = now - self.last_nss_time

        if delta > max(self.config_desc.node_snapshot_interval, 1):
            dispatcher.send(
                signal='golem.monitor',
                event='stats_snapshot',
                known_tasks=self.get_task_count(),
                supported_tasks=self.get_supported_task_count(),
                stats=self.task_server.task_computer.stats,
            )
            dispatcher.send(
                signal='golem.monitor',
                event='task_computer_snapshot',
                task_computer=self.task_server.task_computer,
            )
            # with self.snapshot_lock:
            #     self.__make_node_state_snapshot()
            #     self.manager_server.sendStateMessage(self.last_node_state_snapshot)
            self.last_nss_time = time.time()

        delta = now - self.last_net_check_time
        if delta >= self.config_desc.network_check_interval:
            self.last_net_check_time = time.time()
            self._publish(Network.evt_connection, self.connection_status())

        if now - self.last_tasks_time >= PUBLISH_TASKS_INTERVAL:
            self._publish(Task.evt_task_list, self.get_tasks())

        if now - self.last_balance_time >= PUBLISH_BALANCE_INTERVAL:
            try:
                gnt, av_gnt, eth = yield self.get_balance()
            except Exception as exc:
                log.debug('Error retrieving balance: {}'.format(exc))
            else:
                self._publish(Payments.evt_balance, {
                    'GNT': str(gnt),
                    'GNT_available': str(av_gnt),
                    'ETH': str(eth)
                })

    def __make_node_state_snapshot(self, is_running=True):
        peers_num = 0  # len(self.p2pservice.peers)
        last_network_messages = ''  # self.p2pservice.get_last_messages()

        if self.task_server:
            tasks_num = len(self.task_server.task_keeper.task_headers)
            r_tasks_progs = self.task_server.task_computer.get_progresses()
            l_tasks_progs = self.task_server.task_manager.get_progresses()
            last_task_messages = self.task_server.get_last_messages()
            self.last_node_state_snapshot = NodeStateSnapshot(
                is_running,
                self.config_desc.node_name,
                peers_num,
                tasks_num,
                '',  # self.p2pservice.node.pub_addr,
                '',  # self.p2pservice.node.pub_port,
                last_network_messages,
                last_task_messages,
                r_tasks_progs,
                l_tasks_progs
            )
        else:
            self.last_node_state_snapshot = NodeStateSnapshot(
                self.config_desc.node_name,
                peers_num
            )

        if self.nodes_manager_client:
            self.nodes_manager_client.send_client_state_snapshot(
                self.last_node_state_snapshot
            )

    def connection_status(self):
        listen_port = self.get_p2p_port()
        if listen_port == 0:
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

    def get_metadata(self):
        metadata = dict()
        #  if self.ipfs_manager:
        #     metadata.update(self.ipfs_manager.get_metadata())
        return metadata

    def interpret_metadata(self, metadata, address, port, node_info):
        pass
        #  if self.config_desc and node_info and metadata:
        #     seed_addresses = self.p2pservice.get_seeds()
        #     node_addresses = [
        #         (address, port),
        #         (node_info.pub_addr, node_info.pub_port)
        #     ]
        #     self.ipfs_manager.interpret_metadata(metadata,
        #                                          seed_addresses,
        #                                          node_addresses)

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

        peers = self.services['peermanager'].peers

        msg += "Active peers in network: {}\n".format(len(peers))
        return msg

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
            #  Create datadir if not exists yet.
            #  TODO: It looks we have the same code in many places
            makedirs(self.datadir)
        self.__datadir_lock = open(path.join(self.datadir, "LOCK"), 'w')
        flags = filelock.LOCK_EX | filelock.LOCK_NB
        try:
            filelock.lock(self.__datadir_lock, flags)
        except IOError:
            raise IOError("Data dir {} used by other Golem instance"
                          .format(self.datadir))

    def _unlock_datadir(self):
        #  solves locking issues on OS X
        try:
            filelock.unlock(self.__datadir_lock)
        except Exception:
            pass
        self.__datadir_lock.close()
