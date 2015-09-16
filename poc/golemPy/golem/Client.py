import time
import datetime
import logging

from twisted.internet import task
from threading import Lock

from golem.network.p2p.P2PService import P2PService
from golem.network.p2p.Node import Node
from golem.task.TaskServer import TaskServer
from golem.task.TaskManager import TaskManagerEventListener

from golem.core.keys_auth import EllipticalKeysAuth

from golem.manager.NodeStateSnapshot import NodeStateSnapshot

from golem.AppConfig import AppConfig

from golem.Model import Database
from golem.network.transport.message import init_messages
from golem.ClientConfigDescriptor import ClientConfigDescriptor, ConfigApprover
from golem.environments.EnvironmentsManager import EnvironmentsManager
from golem.resource.ResourceServer import ResourceServer
from golem.resource.dir_manager import DirManager
from golem.ranking.Ranking import Ranking, RankingDatabase

from golem.transactions.Ethereum.ethereum_transaction_system import EthereumTransactionSystem

logger = logging.getLogger(__name__)


def empty_add_nodes(*args):
    pass


def start_client():
    init_messages()

    cfg = AppConfig.load_config()

    opt_num_peers = cfg.get_optimal_peer_num()
    manager_address = cfg.get_manager_address()
    manager_port = cfg.get_manager_listen_port()
    start_port = cfg.get_start_port()
    end_port = cfg.get_end_port()
    seed_host = cfg.get_seed_host()
    seed_host_port = cfg.get_seed_host_port()
    send_pings = cfg.get_send_pings()
    pings_interval = cfg.get_pings_interval()
    client_uid = cfg.get_client_uid()
    add_tasks = cfg.get_add_tasks()
    root_path = cfg.get_root_path()
    num_cores = cfg.get_num_cores()
    max_resource_size = cfg.get_max_resource_size()
    max_memory_size = cfg.get_max_memory_size()
    dist_res_num = cfg.get_distributed_res_num()
    app_name = cfg.get_app_name()
    app_version = cfg.get_app_version()
    plugin_port = cfg.get_plugin_port()

    getting_peers_interval = cfg.get_getting_peers_interval()
    getting_tasks_interval = cfg.get_getting_tasks_interval()
    task_request_interval = cfg.get_task_request_interval()
    use_waiting_for_task_timeout = cfg.get_use_waiting_for_task_timeout()
    waiting_for_task_timeout = cfg.get_waiting_for_task_timeout()
    p2p_session_timeout = cfg.get_p2p_session_timeout()
    task_session_timeout = cfg.get_task_session_timeout()
    resource_session_timeout = cfg.get_resource_session_timeout()

    estimated_performance = cfg.get_estimated_performance()
    node_snapshot_interval = cfg.get_node_snapshot_interval()
    use_distributed_resource_management = cfg.get_use_distributed_resource_management()
    requesting_trust = cfg.get_requesting_trust()
    computing_trust = cfg.get_computing_trust()

    eth_account = cfg.get_eth_account()
    use_ipv6 = cfg.get_use_ipv6()

    config_desc = ClientConfigDescriptor()

    config_desc.client_uid = client_uid
    config_desc.start_port = start_port
    config_desc.end_port = end_port
    config_desc.manager_address = manager_address
    config_desc.manager_port = manager_port
    config_desc.opt_num_peers = opt_num_peers
    config_desc.send_pings = send_pings
    config_desc.pings_interval = pings_interval
    config_desc.add_tasks = add_tasks
    config_desc.client_version = 1
    config_desc.root_path = root_path
    config_desc.num_cores = num_cores
    config_desc.max_resource_size = max_resource_size
    config_desc.max_memory_size = max_memory_size
    config_desc.dist_res_num = dist_res_num

    config_desc.seed_host = seed_host
    config_desc.seed_host_port = seed_host_port

    config_desc.app_version = app_version
    config_desc.app_name = app_name

    config_desc.plugin_port = plugin_port
    config_desc.getting_peers_interval = getting_peers_interval
    config_desc.getting_tasks_interval = getting_tasks_interval
    config_desc.task_request_interval = task_request_interval
    config_desc.use_waiting_for_task_timeout = use_waiting_for_task_timeout
    config_desc.waiting_for_task_timeout = waiting_for_task_timeout
    config_desc.p2p_session_timeout = p2p_session_timeout
    config_desc.task_session_timeout = task_session_timeout
    config_desc.resource_session_timeout = resource_session_timeout

    config_desc.estimated_performance = estimated_performance
    config_desc.node_snapshot_interval = node_snapshot_interval
    config_desc.max_results_sending_delay = cfg.get_max_results_sending_delay()
    config_desc.use_distributed_resource_management = use_distributed_resource_management
    config_desc.requesting_trust = requesting_trust
    config_desc.computing_trust = computing_trust

    config_desc.eth_account = eth_account
    config_desc.use_ipv6 = use_ipv6

    logger.info("Adding tasks {}".format(add_tasks))
    logger.info("Creating public client interface with uuid: {}".format(client_uid))
    c = Client(config_desc, config=cfg)

    logger.info("Starting all asynchronous services")
    c.start_network()

    return c


class GolemClientEventListener:
    ############################
    def __init__(self):
        pass

    ############################
    def task_updated(self, task_id):
        pass

    ############################
    def network_connected(self):
        pass


class ClientTaskManagerEventListener(TaskManagerEventListener):
    #############################
    def __init__(self, client):
        self.client = client

    #######################
    def task_status_updated(self, task_id):
        for l in self.client.listeners:
            l.task_updated(task_id)

    #######################
    def task_finished(self, task_id):
        self.client.task_finished(task_id)


class Client:
    ############################
    def __init__(self, config_desc, root_path="", config=""):
        self.config_desc = config_desc
        self.keys_auth = EllipticalKeysAuth(config_desc.client_uid)
        self.config_approver = ConfigApprover(config_desc)

        # NETWORK
        self.node = Node(self.config_desc.client_uid, self.keys_auth.get_key_id())
        self.node.collect_network_info(self.config_desc.seed_host, use_ipv6=self.config_desc.use_ipv6)
        logger.debug("Is super node? {}".format(self.node.is_super_node()))
        self.p2pservice = None

        self.task_server = None
        self.task_adder_server = None
        self.last_nss_time = time.time()

        self.last_node_state_snapshot = None

        self.nodes_manager_client = None

        self.do_work_task = task.LoopingCall(self.__do_work)
        self.do_work_task.start(0.1, False)

        self.listeners = []

        self.root_path = root_path
        self.cfg = config
        self.send_snapshot = False
        self.snapshot_lock = Lock()

        self.db = Database()
        self.db.check_node(self.config_desc.client_uid)

        self.ranking = Ranking(self, RankingDatabase(self.db))

        self.transaction_system = EthereumTransactionSystem(self.config_desc.client_uid, self.config_desc.eth_account)

        self.environments_manager = EnvironmentsManager()

        self.resource_server = None
        self.resource_port = 0
        self.last_get_resource_peers_time = time.time()
        self.get_resource_peers_interval = 5.0

    ############################
    def start_network(self):
        logger.info("Starting network ...")

        logger.info("Starting p2p server ...")
        self.p2pservice = P2PService(self.node, self.config_desc, self.keys_auth)
        time.sleep(1.0)

        logger.info("Starting resource server...")
        self.resource_server = ResourceServer(self.config_desc, self.keys_auth, self, use_ipv6=self.config_desc.use_ipv6)
        self.resource_server.start_accepting()
        time.sleep(1.0)
        self.p2pservice.set_resource_server(self.resource_server)

        logger.info("Starting task server ...")
        self.task_server = TaskServer(self.node, self.config_desc, self.keys_auth, self,
                                      use_ipv6=self.config_desc.use_ipv6)
        self.task_server.start_accepting()

        self.p2pservice.set_task_server(self.task_server)

        time.sleep(0.5)
        self.task_server.task_manager.register_listener(ClientTaskManagerEventListener(self))

    def run_add_task_server(self):
        from PluginServer import start_task_adder_server
        from multiprocessing import Process, freeze_support
        freeze_support()
        self.task_adder_server = Process(target=start_task_adder_server, args=(self.get_plugin_port(),))
        self.task_adder_server.start()

    def quit(self):
        if self.task_adder_server:
            self.task_adder_server.terminate()

    def key_changed(self):
        self.node.key = self.keys_auth.get_key_id()
        self.task_server.key_changed()
        self.p2pservice.key_changed()

    def stop_network(self):
        # FIXME: Pewnie cos tu trzeba jeszcze dodac. Zamykanie serwera i wysylanie DisconnectPackege
        self.p2pservice = None
        self.task_server = None
        self.nodes_manager_client = None

    def enqueue_new_task(self, task):
        self.task_server.task_manager.add_new_task(task)
        if self.config_desc.use_distributed_resource_management:
            self.get_resource_peers()
            res_files = self.resource_server.add_files_to_send(task.task_resources, task.header.task_id,
                                                               self.config_desc.dist_res_num)
            task.set_res_files(res_files)

    ############################
    def get_resource_peers(self):
        self.p2pservice.send_get_resource_peers()

    ############################
    def task_resource_send(self, task_id):
        self.task_server.task_manager.resources_send(task_id)

    ############################
    def task_resource_collected(self, task_id):
        self.task_server.task_computer.task_resource_collected(task_id)

    ############################
    def set_resource_port(self, resource_port):
        self.resource_port = resource_port
        self.p2pservice.set_resource_peer(self.node.prv_addr, self.resource_port)

    ############################
    def abort_task(self, task_id):
        self.task_server.task_manager.abort_task(task_id)

    ############################
    def restart_task(self, task_id):
        self.task_server.task_manager.restart_task(task_id)

    ############################
    def restart_subtask(self, subtask_id):
        self.task_server.task_manager.restart_subtask(subtask_id)

    ############################
    def pause_task(self, task_id):
        self.task_server.task_manager.pause_task(task_id)

    ############################
    def resume_task(self, task_id):
        self.task_server.task_manager.resume_task(task_id)

    ############################
    def delete_task(self, task_id):
        self.task_server.remove_task_header(task_id)
        self.task_server.task_manager.delete_task(task_id)

    ############################
    def get_id(self):
        return self.config_desc.client_uid

    ############################
    def get_root_path(self):
        return self.config_desc.root_path

    ############################
    def increase_trust(self, node_id, stat, mod=1.0):
        self.ranking.increase_trust(node_id, stat, mod)

    ############################
    def decrease_trust(self, node_id, stat, mod=1.0):
        self.ranking.decrease_trust(node_id, stat, mod)

    ############################
    def get_neighbours_degree(self):
        return self.p2pservice.get_peers_degree()

    ############################
    def get_suggested_addr(self, key_id):
        return self.p2pservice.suggested_address.get(key_id)

    ############################
    def want_to_start_task_session(self, key_id, node_id, conn_id):
        self.p2pservice.want_to_start_task_session(key_id, node_id, conn_id)

    ############################
    def inform_about_task_nat_hole(self, key_id, rv_key_id, addr, port, ans_conn_id):
        self.p2pservice.inform_about_task_nat_hole(key_id, rv_key_id, addr, port, ans_conn_id)

    ############################
    def inform_about_nat_traverse_failure(self, key_id, res_key_id, conn_id):
        self.p2pservice.inform_about_nat_traverse_failure(key_id, res_key_id, conn_id)

    # TRANSACTION SYSTEM OPERATIONS
    ############################
    def accept_result(self, task_id, subtask_id, price_mod, account_info):
        self.transaction_system.add_payment_info(task_id, subtask_id, price_mod, account_info)

    ############################
    def task_reward_paid(self, task_id, price):
        return self.transaction_system.task_reward_paid(task_id, price)

    ############################
    def task_reward_payment_failure(self, task_id, price):
        return self.transaction_system.task_reward_payment_failure(task_id, price)

    ############################
    def global_pay_for_task(self, task_id, payments):
        self.transaction_system.global_pay_for_task(task_id, payments)

    ############################
    def get_reward(self, reward):
        self.transaction_system.get_reward(reward)

    ############################
    def get_new_payments_tasks(self):
        return self.transaction_system.get_new_payments_tasks()

    # CLIENT CONFIGURATION
    ############################
    def register_listener(self, listener):
        assert isinstance(listener, GolemClientEventListener)
        self.listeners.append(listener)

    ############################
    def change_config(self, new_config_desc):
        self.config_desc = self.config_approver.change_config(new_config_desc)
        self.cfg.change_config(self.config_desc)
        self.resource_server.change_resource_dir(self.config_desc)
        self.p2pservice.change_config(self.config_desc)
        self.task_server.change_config(self.config_desc)

    ############################
    def register_nodes_manager_client(self, nodes_manager_client):
        self.nodes_manager_client = nodes_manager_client

    ############################
    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout, min_subtask_time):
        self.task_server.change_timeouts(task_id, full_task_timeout, subtask_timeout, min_subtask_time)

    ############################
    def unregister_listener(self, listener):
        assert isinstance(listener, GolemClientEventListener)
        for i in range(len(self.listeners)):
            if self.listeners[i] is listener:
                del self.listeners[i]
                return
        logger.info("listener {} not registered".format(listener))

    ############################
    def querry_task_state(self, task_id):
        return self.task_server.task_manager.querry_task_state(task_id)

    ############################
    def pull_resources(self, task_id, list_files):
        self.resource_server.add_files_to_get(list_files, task_id)
        self.get_resource_peers()

    ############################
    def add_resource_peer(self, client_id, addr, port, key_id, node_info):
        self.resource_server.add_resource_peer(client_id, addr, port, key_id, node_info)

    ############################
    def supported_task(self, th_dict_repr):
        supported = self.__check_supported_environment(th_dict_repr)
        return supported and self.__check_supported_version(th_dict_repr)

    ############################
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

    ############################
    def remove_computed_files(self):
        dir_manager = DirManager(self.config_desc.root_path, self.config_desc.client_uid)
        dir_manager.clear_dir(self.get_computed_files_dir())

        ############################

    def remove_distributed_files(self):
        dir_manager = DirManager(self.config_desc.root_path, self.config_desc.client_uid)
        dir_manager.clear_dir(self.get_distributed_files_dir())

        ############################

    def remove_received_files(self):
        dir_manager = DirManager(self.config_desc.root_path, self.config_desc.client_uid)
        dir_manager.clear_dir(self.get_received_files_dir())

    ############################
    def get_environments(self):
        return self.environments_manager.get_environments()

    ############################
    def change_accept_tasks_for_environment(self, env_id, state):
        self.environments_manager.change_accept_tasks(env_id, state)

    ############################
    def get_computing_trust(self, node_id):
        return self.ranking.get_computing_trust(node_id)

    ############################
    def send_gossip(self, gossip, send_to):
        return self.p2pservice.send_gossip(gossip, send_to)

    ############################
    def send_stop_gossip(self):
        return self.p2pservice.send_stop_gossip()

    ############################
    def get_requesting_trust(self, node_id):
        return self.ranking.get_requesting_trust(node_id)

    ############################
    def collect_gossip(self):
        return self.p2pservice.pop_gossip()

    ############################
    def collect_stopped_peers(self):
        return self.p2pservice.pop_stop_gossip_form_peers()

    ############################
    def collect_neighbours_loc_ranks(self):
        return self.p2pservice.pop_neighbours_loc_ranks()

    ############################
    def push_local_rank(self, node_id, loc_rank):
        self.p2pservice.push_local_rank(node_id, loc_rank)

    ############################
    def get_plugin_port(self):
        return self.config_desc.plugin_port

    ############################
    def get_eth_account(self):
        return self.config_desc.eth_account

    ############################
    def task_finished(self, task_id):
        self.transaction_system.task_finished(task_id)

    ############################
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

    ############################
    def __check_supported_environment(self, th_dict_repr):
        env = th_dict_repr.get("environment")
        if not env:
            return False
        if not self.environments_manager.supported(env):
            return False
        return self.environments_manager.accept_tasks(env)

    #############################
    def __check_supported_version(self, th_dict_repr):
        min_v = th_dict_repr.get("min_version")
        if not min_v:
            return True
        try:
            supported = float(self.config_desc.app_version) >= float(min_v)
            return supported
        except ValueError:
            logger.error(
                "Wrong app version - app version {}, required version {}".format(
                    self.config_desc.app_version,
                    min_v
                )
            )
            return False

    ############################
    def __do_work(self):
        if self.p2pservice:
            if self.config_desc.send_pings:
                self.p2pservice.ping_peers(self.config_desc.pings_interval)

            self.p2pservice.sync_network()
            self.task_server.sync_network()
            self.resource_server.sync_network()
            self.ranking.sync_network()

            if time.time() - self.last_nss_time > self.config_desc.node_snapshot_interval:
                with self.snapshot_lock:
                    self.__make_node_state_snapshot()
                self.last_nss_time = time.time()
                for l in self.listeners:
                    l.check_network_state()

                    # self.manager_server.sendStateMessage(self.last_node_state_snapshot)

    ############################
    def __make_node_state_snapshot(self, is_running=True):

        peers_num = len(self.p2pservice.peers)
        last_network_messages = self.p2pservice.get_last_messages()

        if self.task_server:
            tasks_num = len(self.task_server.task_keeper.task_headers)
            remote_tasks_progresses = self.task_server.task_computer.get_progresses()
            local_tasks_progresses = self.task_server.task_manager.get_progresses()
            last_task_messages = self.task_server.get_last_messages()
            self.last_node_state_snapshot = NodeStateSnapshot(is_running
                                                           , self.config_desc.client_uid
                                                           , peers_num
                                                           , tasks_num
                                                           , self.p2pservice.node.pub_addr
                                                           , self.p2pservice.node.pub_port
                                                           , last_network_messages
                                                           , last_task_messages
                                                           , remote_tasks_progresses
                                                           , local_tasks_progresses)
        else:
            self.last_node_state_snapshot = NodeStateSnapshot(self.config_desc.client_uid, peers_num)

        if self.nodes_manager_client:
            self.nodes_manager_client.send_client_state_snapshot(self.last_node_state_snapshot)

    def get_status(self):
        progress = self.task_server.task_computer.get_progresses()
        if len(progress) > 0:
            msg = "Counting {} subtask(s):".format(len(progress))
            for k, v in progress.iteritems():
                msg = "{} \n {} ({}%)\n".format(msg, k, v.get_progress() * 100)
        else:
            msg = "Waiting for tasks...\n"

        peers = self.p2pservice.get_peers()

        msg += "Active peers in network: {}\n".format(len(peers))
        msg += "Budget: {}\n".format(self.transaction_system.budget)
        return msg

    def get_about_info(self):
        return self.config_desc.app_name, self.config_desc.app_version
