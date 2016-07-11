import logging
import time
from os import path, makedirs
from threading import Lock

from twisted.internet import task

from golem.appconfig import AppConfig
from golem.clientconfigdescriptor import ClientConfigDescriptor, ConfigApprover
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.simpleenv import get_local_datadir
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.manager.nodestatesnapshot import NodeStateSnapshot
from golem.model import Database
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
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


class ClientTaskManagerEventListener(TaskManagerEventListener):
    def __init__(self, client):
        self.client = client

    def task_status_updated(self, task_id):
        for l in self.client.listeners:
            l.task_updated(task_id)


class Client(object):
    def __init__(self, datadir=None, transaction_system=False,
                 connect_to_known_hosts=True, **config_overrides):

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
                raise AttributeError(
                    "Can't override nonexistent config entry '{}'".format(key))
            setattr(self.config_desc, key, val)

        self.keys_auth = EllipticalKeysAuth(self.config_desc.node_name)
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

        self.task_server = None
        self.last_nss_time = time.time()

        self.last_node_state_snapshot = None

        self.nodes_manager_client = None

        self.do_work_task = task.LoopingCall(self.__do_work)  # FIXME: do in start()
        self.do_work_task.start(0.1, False)

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

        self.connect_to_known_hosts = connect_to_known_hosts
        self.environments_manager = EnvironmentsManager()

        self.ipfs_manager = None
        self.resource_server = None
        self.resource_port = 0
        self.last_get_resource_peers_time = time.time()
        self.get_resource_peers_interval = 5.0

    def start(self):
        self.start_network()

    def start_network(self):
        logger.info("Starting network ...")

        # self.ipfs_manager = IPFSDaemonManager(connect_to_bootstrap_nodes=self.connect_to_known_hosts)
        # self.ipfs_manager.store_client_info()

        self.p2pservice = P2PService(self.node, self.config_desc, self.keys_auth,
                                     connect_to_known_hosts=self.connect_to_known_hosts)
        self.task_server = TaskServer(self.node, self.config_desc, self.keys_auth, self,
                                      use_ipv6=self.config_desc.use_ipv6)

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
        self.p2pservice.connect_to_network()

    def connect(self, socket_address):
        logger.debug("P2pservice connecting to {} on port {}".format(
                     socket_address.address, socket_address.port))
        self.p2pservice.connect(socket_address)

    def quit(self):
        self.task_server.quit()

    def key_changed(self):
        self.node.key = self.keys_auth.get_key_id()
        self.task_server.key_changed()
        self.p2pservice.key_changed()

    def stop_network(self):
        # FIXME: Implement this method proberly - send disconnect package, close connections etc.
        self.p2pservice = None
        self.task_server = None
        self.nodes_manager_client = None

    def enqueue_new_task(self, task):
        task_id = task.header.task_id
        self.task_server.task_manager.add_new_task(task)
        files = self.task_server.task_manager.get_resources(task_id, None, resource_types["hashes"])
        client_options = self.resource_server.resource_manager.build_client_options(self.keys_auth.key_id)
        self.resource_server.add_task(files, task_id, client_options=client_options)

    def get_resource_peers(self):
        self.p2pservice.send_get_resource_peers()

    def task_resource_send(self, task_id):
        self.task_server.task_manager.resources_send(task_id)

    def task_resource_collected(self, task_id, unpack_delta=True):
        self.task_server.task_computer.task_resource_collected(task_id, unpack_delta)

    def task_resource_failure(self, task_id, reason):
        self.task_server.task_computer.task_resource_failure(task_id, reason)

    def set_resource_port(self, resource_port):
        self.resource_port = resource_port
        self.p2pservice.set_resource_peer(self.node.prv_addr, self.resource_port)

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

    def get_node_name(self):
        return self.config_desc.node_name

    def increase_trust(self, node_id, stat, mod=1.0):
        self.ranking.increase_trust(node_id, stat, mod)

    def decrease_trust(self, node_id, stat, mod=1.0):
        self.ranking.decrease_trust(node_id, stat, mod)

    def get_neighbours_degree(self):
        return self.p2pservice.get_peers_degree()

    def get_suggested_addr(self, key_id):
        return self.p2pservice.suggested_address.get(key_id)

    def get_suggested_conn_reverse(self, key_id):
        return self.p2pservice.get_suggested_conn_reverse(key_id)

    def want_to_start_task_session(self, key_id, node_id, conn_id):
        self.p2pservice.want_to_start_task_session(key_id, node_id, conn_id)

    def inform_about_task_nat_hole(self, key_id, rv_key_id, addr, port, ans_conn_id):
        self.p2pservice.inform_about_task_nat_hole(key_id, rv_key_id, addr, port, ans_conn_id)

    def inform_about_nat_traverse_failure(self, key_id, res_key_id, conn_id):
        self.p2pservice.inform_about_nat_traverse_failure(key_id, res_key_id, conn_id)

    # CLIENT CONFIGURATION
    def register_listener(self, listener):
        assert isinstance(listener, GolemClientEventListener)
        self.listeners.append(listener)

    def change_config(self, new_config_desc):
        self.config_desc = self.config_approver.change_config(new_config_desc)
        self.cfg.change_config(self.config_desc)
        self.p2pservice.change_config(self.config_desc)
        self.task_server.change_config(self.config_desc)

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
        dir_manager = DirManager(self.datadir, self.config_desc.node_name)
        dir_manager.clear_dir(self.get_computed_files_dir())

    def remove_distributed_files(self):
        dir_manager = DirManager(self.datadir, self.config_desc.node_name)
        dir_manager.clear_dir(self.get_distributed_files_dir())

    def remove_received_files(self):
        dir_manager = DirManager(self.datadir, self.config_desc.node_name)
        dir_manager.clear_dir(self.get_received_files_dir())

    def get_environments(self):
        return self.environments_manager.get_environments()

    def change_accept_tasks_for_environment(self, env_id, state):
        self.environments_manager.change_accept_tasks(env_id, state)

    def get_computing_trust(self, node_id):
        return self.ranking.get_computing_trust(node_id)

    def send_gossip(self, gossip, send_to):
        return self.p2pservice.send_gossip(gossip, send_to)

    def send_stop_gossip(self):
        return self.p2pservice.send_stop_gossip()

    def get_requesting_trust(self, node_id):
        return self.ranking.get_requesting_trust(node_id)

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

            if time.time() - self.last_nss_time > self.config_desc.node_snapshot_interval:
                with self.snapshot_lock:
                    self.__make_node_state_snapshot()
                self.last_nss_time = time.time()
                for l in self.listeners:
                    l.check_network_state()

                    # self.manager_server.sendStateMessage(self.last_node_state_snapshot)

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
        if self.transaction_system:
            msg += "Budget: {}\n".format(self.transaction_system.budget)
        return msg

    def get_peers(self):
        return self.p2pservice.peers.values()

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
