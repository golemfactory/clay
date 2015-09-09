
import sys
sys.path.append('./../')
sys.path.append('../testtasks/minilight/src')
sys.path.append('../testtasks/pbrt')

from twisted.internet import reactor

from golem.AppConfig import AppConfig
from golem.Client import Client
from golem.network.transport.message import init_messages
from golem.ClientConfigDescriptor import ClientConfigDescriptor


def main():

    

    init_messages()

    cfg = AppConfig.load_config()

    opt_num_peers     = cfg.get_optimal_peer_num()
    manager_port     = cfg.get_manager_listen_port()
    start_port       = cfg.get_start_port()
    end_port         = cfg.get_end_port()
    seed_host        = cfg.get_seed_host()
    seed_host_port    = cfg.get_seed_host_port()
    send_pings       = cfg.get_send_pings()
    pings_interval   = cfg.get_pings_interval()
    client_uid       = cfg.get_client_uid()
    add_tasks        = cfg.get_add_tasks()

    getting_peers_interval    = cfg.get_getting_peers_interval()
    getting_tasks_interval    = cfg.get_getting_tasks_interval()
    task_request_interval     = cfg.get_task_request_interval()
    estimated_performance    = cfg.get_estimated_performance()
    node_snapshot_interval    = cfg.get_node_snapshot_interval()

    config_desc = ClientConfigDescriptor()

    config_desc.client_uid      = client_uid
    config_desc.start_port      = start_port
    config_desc.end_port        = end_port
    config_desc.manager_port    = manager_port
    config_desc.opt_num_peers    = opt_num_peers
    config_desc.send_pings      = send_pings
    config_desc.pings_interval  = pings_interval
    config_desc.add_tasks       = add_tasks
    config_desc.client_version = 1

    config_desc.seed_host               = seed_host
    config_desc.seed_host_port           = seed_host_port

    config_desc.getting_peers_interval   = getting_peers_interval
    config_desc.getting_tasks_interval   = getting_tasks_interval
    config_desc.task_request_interval    = task_request_interval
    config_desc.estimated_performance   = estimated_performance
    config_desc.node_snapshot_interval   = node_snapshot_interval
    config_desc.max_results_sending_delay = cfg.get_max_results_sending_delay()

    print "Adding tasks {}".format(add_tasks)
    print "Creating public client interface with uuid: {}".format(client_uid)
    c = Client(config_desc)

    print "Starting all asynchronous services"
    c.start_network()

    reactor.run()


main()
