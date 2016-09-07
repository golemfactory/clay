import atexit
import logging
import sys
import time
import uuid
from os import path, makedirs
from threading import Lock

from twisted.internet import task

from gnr.task.tasktester import TaskTester
from golem.appconfig import AppConfig
from golem.clientconfigdescriptor import ClientConfigDescriptor, ConfigApprover
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.simpleenv import get_local_datadir
from golem.core.variables import APP_VERSION
from golem.diag.service import DiagnosticsService, DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider
from golem.monitorconfig import monitor_config
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.manager.nodestatesnapshot import NodeStateSnapshot
from golem.model import Database, Account
from golem.monitor.monitor import SystemMonitor
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import PeerSessionInfo
from golem.network.transport.message import init_messages
from golem.ranking.ranking import Ranking, RankingStats
from golem.resource.base.resourceserver import BaseResourceServer
from golem.resource.dirmanager import DirManager
from golem.resource.swift.resourcemanager import OpenStackSwiftResourceManager
from golem.task.taskbase import resource_types
from golem.task.taskmanager import TaskManagerEventListener
from golem.task.taskserver import TaskServer
from golem.tools import filelock
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem

logger = logging.getLogger("golem.client")


class GolemClientEventListener:
    def __init__(self):
        pass

    def task_updated(self, task_id):
        pass

    def network_connected(self):
        pass


class GolemClientRemoteEventListener(GolemClientEventListener):
    def __init__(self, service_info):
        GolemClientEventListener.__init__(self)
        self.service_info = service_info
        self.remote_client = None

    def build(self, client_builder):
        self.remote_client = client_builder.build_client(self.service_info)
        return self.remote_client


class ClientTaskManagerEventListener(TaskManagerEventListener):
    def __init__(self, client):
        TaskManagerEventListener.__init__(self)
        self.client = client

    def task_status_updated(self, task_id):
        for l in self.client.listeners:
            l.task_updated(task_id)


class ClientTaskComputerEventListener(object):
    def __init__(self, client):
        self.client = client

    def toggle_config_dialog(self, on=True):
        self.client.toggle_config_dialog(on)

    def docker_config_changed(self):
        self.client.docker_config_changed()


class Client(object):
    def __init__(self, datadir=None, transaction_system=False, connect_to_known_hosts=True,
                 use_docker_machine_manager=True, use_monitor=True, **config_overrides):

        # TODO: Should we init it only once?
        init_messages()

        if not datadir:
            datadir = get_local_datadir('default')

        self.datadir = datadir
        self.__lock_datadir()

        config = AppConfig.load_config(datadir)
        self.config_desc = ClientConfigDescriptor()
        self.config_desc.init_from_app_config(config)
        for key, val in config_overrides.iteritems():
            if not hasattr(self.config_desc, key):
                self.quit()  # quit only closes underlying services (for now)
                raise AttributeError(
                    "Can't override nonexistent config entry '{}'".format(key))
            setattr(self.config_desc, key, val)

        self.keys_auth = EllipticalKeysAuth(self.datadir)
        self.config_approver = ConfigApprover(self.config_desc)

        # NETWORK
        self.node = Node(node_name=self.config_desc.node_name,
                         key=self.keys_auth.get_key_id(),
                         prv_addr=self.config_desc.node_address)

        # FIXME: do in start()
        self.node.collect_network_info(self.config_desc.seed_host,
                                       use_ipv6=self.config_desc.use_ipv6)

        logger.info('Client "{}", datadir: {}'.format(self.config_desc.node_name, datadir))
        logger.debug("Is super node? {}".format(self.node.is_super_node()))

        self.p2pservice = None
        self.diag_service = None

        self.task_server = None
        self.last_nss_time = time.time()
        self.last_net_check_time = time.time()

        self.last_node_state_snapshot = None

        self.nodes_manager_client = None

        self.do_work_task = task.LoopingCall(self.__do_work)

        self.listeners = []

        self.cfg = config
        self.send_snapshot = False
        self.snapshot_lock = Lock()

        self.db = Database(datadir)

        self.ranking = Ranking(self)

        if transaction_system:
            # Bootstrap transaction system if enabled.
            # TODO: Transaction system (and possible other modules) should be
            #       modeled as a Service that run independently.
            #       The Client/Application should be a collection of services.
            self.transaction_system = EthereumTransactionSystem(
                datadir, self.keys_auth._private_key)
        else:
            self.transaction_system = None

        self.use_docker_machine_manager = use_docker_machine_manager
        self.connect_to_known_hosts = connect_to_known_hosts
        self.environments_manager = EnvironmentsManager()

        self.rpc_server = None
        self.rpc_clients = []

        self.ipfs_manager = None
        self.resource_server = None
        self.resource_port = 0
        self.last_get_resource_peers_time = time.time()
        self.get_resource_peers_interval = 5.0
        self.use_monitor = use_monitor
        self.monitor = None
        self.session_id = uuid.uuid4().get_hex()

        atexit.register(self.quit)

    def start(self):
        if self.use_monitor:
            self.init_monitor()
        self.start_network()
        self.do_work_task.start(0.1, False)

    def start_network(self):
        logger.info("Starting network ...")

        # self.ipfs_manager = IPFSDaemonManager(connect_to_bootstrap_nodes=self.connect_to_known_hosts)
        # self.ipfs_manager.store_client_info()

        self.p2pservice = P2PService(self.node, self.config_desc, self.keys_auth,
                                     connect_to_known_hosts=self.connect_to_known_hosts)
        self.task_server = TaskServer(self.node, self.config_desc, self.keys_auth, self,
                                      use_ipv6=self.config_desc.use_ipv6,
                                      use_docker_machine_manager=self.use_docker_machine_manager)

        dir_manager = self.task_server.task_computer.dir_manager

        self.resource_server = BaseResourceServer(OpenStackSwiftResourceManager(dir_manager),
                                                  dir_manager, self.keys_auth, self)

        logger.info("Starting p2p server ...")
        self.p2pservice.start_accepting()
        time.sleep(1.0)

        logger.info("Starting resource server...")
        self.resource_server.start_accepting()
        time.sleep(1.0)

        self.p2pservice.set_resource_server(self.resource_server)
        self.p2pservice.set_metadata_manager(self)

        logger.info("Starting task server ...")
        self.task_server.start_accepting()

        self.p2pservice.set_task_server(self.task_server)
        self.task_server.task_manager.register_listener(ClientTaskManagerEventListener(self))
        self.task_server.task_computer.register_listener(ClientTaskComputerEventListener(self))
        self.p2pservice.connect_to_network()

        if self.monitor:
            self.diag_service.register(self.p2pservice, self.monitor.on_peer_snapshot)
            self.monitor.on_login()

    def init_monitor(self):
        metadata = NodeMetadataModel(self.get_client_id(), self.session_id, sys.platform, APP_VERSION,
                                     self.get_description(), self.config_desc)
        self.monitor = SystemMonitor(metadata, monitor_config)
        self.monitor.start()
        self.diag_service = DiagnosticsService(DiagnosticsOutputFormat.data)
        self.diag_service.register(VMDiagnosticsProvider(), self.monitor.on_vm_snapshot)
        self.diag_service.start_looping_call()

    def connect(self, socket_address):
        logger.debug("P2pservice connecting to {} on port {}".format(
                     socket_address.address, socket_address.port))
        self.p2pservice.connect(socket_address)

    def quit(self):
        if self.do_work_task.running:
            self.do_work_task.stop()
        if self.task_server:
            self.task_server.quit()
        if self.diag_service:
            self.diag_service.unregister_all()
        if self.monitor:
            self.monitor.on_logout()
            self.monitor.shut_down()
        if self.db:
            self.db.close()
        self._unlock_datadir()

    def key_changed(self):
        self.node.key = self.keys_auth.get_key_id()
        self.task_server.key_changed()
        self.p2pservice.key_changed()

    def stop_network(self):
        # FIXME: Implement this method properly - send disconnect package, close connections etc.
        self.p2pservice = None
        self.task_server = None
        self.nodes_manager_client = None

    def enqueue_new_task(self, task):
        task_id = task.header.task_id
        self.task_server.task_manager.add_new_task(task)
        files = self.task_server.task_manager.get_resources(task_id, None, resource_types["hashes"])
        client_options = self.resource_server.resource_manager.build_client_options(self.keys_auth.key_id)
        self.resource_server.add_task(files, task_id, client_options=client_options)

    def task_resource_send(self, task_id):
        self.task_server.task_manager.resources_send(task_id)

    def task_resource_collected(self, task_id, unpack_delta=True):
        self.task_server.task_computer.task_resource_collected(task_id, unpack_delta)

    def task_resource_failure(self, task_id, reason):
        self.task_server.task_computer.task_resource_failure(task_id, reason)

    def set_resource_port(self, resource_port):
        self.resource_port = resource_port
        self.p2pservice.set_resource_peer(self.node.prv_addr, self.resource_port)

    def run_test_task(self, t):
        def on_success(*args, **kwargs):
            for rpc_client in self.rpc_clients:
                rpc_client.test_task_computation_success(*args, **kwargs)

        def on_error(*args, **kwargs):
            for rpc_client in self.rpc_clients:
                rpc_client.test_task_computation_error(*args, **kwargs)

        tt = TaskTester(t, self.datadir, on_success, on_error)
        tt.run()

    def abort_task(self, task_id):
        self.task_server.task_manager.abort_task(task_id)

    def restart_task(self, task_id):
        self.task_server.task_manager.restart_task(task_id)

    def restart_subtask(self, subtask_id):
        self.task_server.task_manager.restart_subtask(subtask_id)

    def pause_task(self, task_id):
        self.task_server.task_manager.pause_task(task_id)

    def resume_task(self, task_id):
        self.task_server.task_manager.resume_task(task_id)

    def delete_task(self, task_id):
        self.task_server.remove_task_header(task_id)
        self.task_server.task_manager.delete_task(task_id)

    def increase_trust(self, node_id, stat, mod=1.0):
        self.ranking.increase_trust(node_id, stat, mod)

    def decrease_trust(self, node_id, stat, mod=1.0):
        self.ranking.decrease_trust(node_id, stat, mod)

    def get_node_name(self):
        return self.config_desc.node_name

    def get_neighbours_degree(self):
        return self.p2pservice.get_peers_degree()

    def get_suggested_addr(self, key_id):
        return self.p2pservice.suggested_address.get(key_id)

    def get_suggested_conn_reverse(self, key_id):
        return self.p2pservice.get_suggested_conn_reverse(key_id)

    def get_resource_peers(self):
        self.p2pservice.send_get_resource_peers()

    def get_peers(self):
        return self.p2pservice.peers.values()

    def get_peer_info(self):
        peers, info = self.get_peers(), []
        for p in peers:
            info.append(PeerSessionInfo(p))
        return info

    # TODO: simplify
    def get_keys_auth(self):
        return self.keys_auth

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
        return self.keys_auth.get_key_id()

    def get_node_key(self):
        return self.node.key

    def get_config(self):
        return self.config_desc

    def get_datadir(self):
        return self.datadir

    def get_p2p_port(self):
        return self.p2pservice.cur_port

    def get_task_server_port(self):
        return self.task_server.cur_port

    def get_task_count(self):
        return len(self.task_server.task_keeper.get_all_tasks())

    def get_tasks(self):
        return self.task_server.task_keeper.get_all_tasks()

    def get_supported_task_count(self):
        return len(self.task_server.task_keeper.supported_tasks)

    def get_computed_task_count(self):
        return self.task_server.task_computer.stats.computed_tasks

    def get_timeout_task_count(self):
        return self.task_server.task_computer.stats.tasks_with_timeout

    def get_error_task_count(self):
        return self.task_server.task_computer.stats.tasks_with_errors

    def get_payment_address(self):
        return self.transaction_system.get_payment_address()

    def get_balance(self):
        if self.use_transaction_system():
            return self.transaction_system.get_balance()
        return None, None, None

    def get_payments_list(self):
        if self.use_transaction_system():
            return self.transaction_system.get_payments_list()
        return ()

    def get_incomes_list(self):
        if self.transaction_system:
            return self.transaction_system.get_incoming_payments()
        # FIXME use method that connect payment with expected payments
        # if self.use_transaction_system():
        #    return self.transaction_system.get_incomes_list()
        return ()

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
            return "An error has occured {}".format(e)

    def change_description(self, description):
        self.get_description()
        q = Account.update(description=description).where(Account.node_id == self.get_client_id())
        q.execute()

    def use_ranking(self):
        return bool(self.ranking)

    def want_to_start_task_session(self, key_id, node_id, conn_id):
        self.p2pservice.want_to_start_task_session(key_id, node_id, conn_id)

    def inform_about_task_nat_hole(self, key_id, rv_key_id, addr, port, ans_conn_id):
        self.p2pservice.inform_about_task_nat_hole(key_id, rv_key_id, addr, port, ans_conn_id)

    def inform_about_nat_traverse_failure(self, key_id, res_key_id, conn_id):
        self.p2pservice.inform_about_nat_traverse_failure(key_id, res_key_id, conn_id)

    # CLIENT CONFIGURATION
    def register_listener(self, listener):
        assert isinstance(listener, GolemClientEventListener)

        if self.rpc_server:
            if isinstance(listener, GolemClientRemoteEventListener):
                self.rpc_clients.append(listener.build(self.rpc_server))

        self.listeners.append(listener)

    def set_rpc_server(self, rpc_server):
        self.rpc_server = rpc_server
        return self.rpc_server.add_service(self)

    def change_config(self, new_config_desc, run_benchmarks=False):
        self.config_desc = self.config_approver.change_config(new_config_desc)
        self.cfg.change_config(self.config_desc)
        self.p2pservice.change_config(self.config_desc)
        if self.task_server:
            self.task_server.change_config(self.config_desc, run_benchmarks=run_benchmarks)

    def register_nodes_manager_client(self, nodes_manager_client):
        self.nodes_manager_client = nodes_manager_client

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout):
        self.task_server.change_timeouts(task_id, full_task_timeout, subtask_timeout)

    def unregister_listener(self, listener):
        assert isinstance(listener, GolemClientEventListener)
        for i in range(len(self.listeners)):
            if self.listeners[i] is listener:
                del self.listeners[i]
                return
        logger.info("listener {} not registered".format(listener))

    def query_task_state(self, task_id):
        return self.task_server.task_manager.query_task_state(task_id)

    def pull_resources(self, task_id, list_files, client_options=None):
        self.resource_server.add_files_to_get(list_files, task_id, client_options=client_options)

    def add_resource_peer(self, node_name, addr, port, key_id, node_info):
        self.resource_server.add_resource_peer(node_name, addr, port, key_id, node_info)

    def get_res_dirs(self):
        dirs = {"computing": self.get_computed_files_dir(),
                "received": self.get_received_files_dir(),
                "distributed": self.get_distributed_files_dir()
                }
        return dirs

    def get_computed_files_dir(self):
        return self.task_server.get_task_computer_root()

    def get_received_files_dir(self):
        return self.task_server.task_manager.get_task_manager_root()

    def get_distributed_files_dir(self):
        return self.resource_server.get_distributed_resource_root()

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
        self.p2pservice.remove_task(task_id)

    def remove_task_header(self, task_id):
        self.task_server.remove_task_header(task_id)

    def get_environments(self):
        return self.environments_manager.get_environments()

    def change_accept_tasks_for_environment(self, env_id, state):
        self.environments_manager.change_accept_tasks(env_id, state)

    def send_gossip(self, gossip, send_to):
        return self.p2pservice.send_gossip(gossip, send_to)

    def send_stop_gossip(self):
        return self.p2pservice.send_stop_gossip()

    def collect_gossip(self):
        return self.p2pservice.pop_gossip()

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
            self.decrease_trust(node_id, RankingStats.payment)

    def toggle_config_dialog(self, on=True):
        for rpc_client in self.rpc_clients:
            rpc_client.toggle_config_dialog(on)

    def docker_config_changed(self):
        for rpc_client in self.rpc_clients:
            rpc_client.docker_config_changed()

    def __try_to_change_to_number(self, old_value, new_value, to_int=False, to_float=False, name="Config"):
        try:
            if to_int:
                new_value = int(new_value)
            elif to_float:
                new_value = float(new_value)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, new_value))
            new_value = old_value
        return new_value

    def __do_work(self):
        if self.p2pservice:
            if self.config_desc.send_pings:
                self.p2pservice.ping_peers(self.config_desc.pings_interval)

            self.p2pservice.sync_network()
            self.task_server.sync_network()
            self.resource_server.sync_network()
            self.ranking.sync_network()

            self.check_payments()

            if time.time() - self.last_nss_time > max(self.config_desc.node_snapshot_interval, 1):
                if self.monitor:
                    self.monitor.on_stats_snapshot(self.get_task_count(), self.get_supported_task_count(),
                                                   self.get_computed_task_count(), self.get_error_task_count(),
                                                   self.get_timeout_task_count())
                    self.monitor.on_task_computer_snapshot(self.task_server.task_computer.waiting_for_task,
                                                           self.task_server.task_computer.counting_task,
                                                           self.task_server.task_computer.task_requested,
                                                           self.task_server.task_computer.compute_tasks,
                                                           self.task_server.task_computer.assigned_subtasks.keys())
                # with self.snapshot_lock:
                #     self.__make_node_state_snapshot()
                    # self.manager_server.sendStateMessage(self.last_node_state_snapshot)
                self.last_nss_time = time.time()

            if time.time() - self.last_net_check_time >= self.config_desc.network_check_interval:
                for l in self.listeners:
                    l.check_network_state()
                self.last_net_check_time = time.time()

    def __make_node_state_snapshot(self, is_running=True):

        peers_num = len(self.p2pservice.peers)
        last_network_messages = self.p2pservice.get_last_messages()

        if self.task_server:
            tasks_num = len(self.task_server.task_keeper.task_headers)
            remote_tasks_progresses = self.task_server.task_computer.get_progresses()
            local_tasks_progresses = self.task_server.task_manager.get_progresses()
            last_task_messages = self.task_server.get_last_messages()
            self.last_node_state_snapshot = NodeStateSnapshot(is_running,
                                                              self.config_desc.node_name,
                                                              peers_num,
                                                              tasks_num,
                                                              self.p2pservice.node.pub_addr,
                                                              self.p2pservice.node.pub_port,
                                                              last_network_messages,
                                                              last_task_messages,
                                                              remote_tasks_progresses,
                                                              local_tasks_progresses)
        else:
            self.last_node_state_snapshot = NodeStateSnapshot(self.config_desc.node_name, peers_num)

        if self.nodes_manager_client:
            self.nodes_manager_client.send_client_state_snapshot(self.last_node_state_snapshot)

    def get_metadata(self):
        metadata = dict()
        # if self.ipfs_manager:
        #     metadata.update(self.ipfs_manager.get_metadata())
        return metadata

    def interpret_metadata(self, metadata, address, port, node_info):
        pass
        # if self.config_desc and node_info and metadata:
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
            for k, v in progress.iteritems():
                msg = "{} \n {} ({}%)\n".format(msg, k, v.get_progress() * 100)
        elif self.config_desc.accept_tasks:
            msg = "Waiting for tasks...\n"
        else:
            msg = "Not accepting tasks\n"

        peers = self.p2pservice.get_peers()

        msg += "Active peers in network: {}\n".format(len(peers))
        return msg

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
        # FIXME: Client should have close() method
        self.__datadir_lock.close()  # Closing file unlocks it.
