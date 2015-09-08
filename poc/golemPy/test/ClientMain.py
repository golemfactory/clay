
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

    cfg = AppConfig.loadConfig()

    opt_num_peers     = cfg.getOptimalPeerNum()
    manager_port     = cfg.getManagerListenPort()
    start_port       = cfg.getStartPort()
    end_port         = cfg.getEndPort()
    seed_host        = cfg.getSeedHost()
    seed_host_port    = cfg.getSeedHostPort()
    send_pings       = cfg.getSendPings()
    pings_interval   = cfg.getPingsInterval()
    client_uid       = cfg.getClientUid()
    add_tasks        = cfg.getAddTasks()

    getting_peers_interval    = cfg.getGettingPeersInterval()
    getting_tasks_interval    = cfg.getGettingTasksInterval()
    task_request_interval     = cfg.get_taskRequestInterval()
    estimated_performance    = cfg.getEstimatedPerformance()
    node_snapshot_interval    = cfg.getNodeSnapshotInterval()

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
    config_desc.max_results_sending_delay = cfg.getMaxResultsSendingDelay()

    print "Adding tasks {}".format(add_tasks)
    print "Creating public client interface with uuid: {}".format(client_uid)
    c = Client(config_desc)

    print "Starting all asynchronous services"
    c.startNetwork()

    reactor.run()


main()
