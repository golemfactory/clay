
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

    optNumPeers     = cfg.getOptimalPeerNum()
    managerPort     = cfg.getManagerListenPort()
    startPort       = cfg.getStartPort()
    endPort         = cfg.getEndPort()
    seedHost        = cfg.getSeedHost()
    seedHostPort    = cfg.getSeedHostPort()
    sendPings       = cfg.getSendPings()
    pingsInterval   = cfg.getPingsInterval()
    clientUid       = cfg.getClientUid()
    addTasks        = cfg.getAddTasks()

    gettingPeersInterval    = cfg.getGettingPeersInterval()
    gettingTasksInterval    = cfg.getGettingTasksInterval()
    taskRequestInterval     = cfg.getTaskRequestInterval()
    estimatedPerformance    = cfg.getEstimatedPerformance()
    nodeSnapshotInterval    = cfg.getNodeSnapshotInterval()

    configDesc = ClientConfigDescriptor()

    configDesc.clientUid      = clientUid
    configDesc.startPort      = startPort
    configDesc.endPort        = endPort
    configDesc.managerPort    = managerPort
    configDesc.optNumPeers    = optNumPeers
    configDesc.sendPings      = sendPings
    configDesc.pingsInterval  = pingsInterval
    configDesc.addTasks       = addTasks
    configDesc.clientVersion  = 1

    configDesc.seedHost               = seedHost
    configDesc.seedHostPort           = seedHostPort

    configDesc.gettingPeersInterval   = gettingPeersInterval
    configDesc.gettingTasksInterval   = gettingTasksInterval
    configDesc.taskRequestInterval    = taskRequestInterval 
    configDesc.estimatedPerformance   = estimatedPerformance
    configDesc.nodeSnapshotInterval   = nodeSnapshotInterval
    configDesc.maxResultsSendignDelay = cfg.getMaxResultsSendingDelay()

    print "Adding tasks {}".format(addTasks)
    print "Creating public client interface with uuid: {}".format(clientUid)
    c = Client(configDesc)

    print "Starting all asynchronous services"
    c.startNetwork()

    reactor.run()


main()
