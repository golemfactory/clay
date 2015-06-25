

class ClientConfigDescriptor:

    def __init__(self):

        self.clientUid      = 0
        self.startPort      = 0
        self.endPort        = 0
        self.managerAddress = ""
        self.managerPort    = 0
        self.optNumPeers    = 0
        self.sendPings      = 0
        self.pingsInterval  = 0.0
        self.addTasks       = 0
        self.distResNum = 0
        self.clientVersion  = 0
        self.useIp6 = 0

        self.seedHost               = u""
        self.seedHostPort           = 0

        self.pluginPort                 = 0

        self.gettingPeersInterval       = 0.0
        self.gettingTasksInterval       = 0.0
        self.taskRequestInterval        = 0.0
        self.useWaitingForTaskTimeout   = 0
        self.waitingForTaskTimeout      = 0.0
        self.p2pSessionTimeout          = 0
        self.taskSessionTimeout         = 0
        self.resourceSessionTimeout     = 0

        self.estimatedPerformance       = 0.0
        self.nodeSnapshotInterval       = 0.0
        self.maxResultsSendingDelay     = 0.0
        self.rootPath                   = u""
        self.numCores                   = 0
        self.maxResourceSize            = 0
        self.maxMemorySize              = 0

        self.useDistributedResourceManagement = True

        self.requestingTrust = 0.0
        self.computingTrust = 0.0

        self.ethAccount= ""

