
class ConfigDescriptor:

    def __init__( self ):

        self.clientUuid     = 0
        self.startPort      = 0
        self.endPort        = 0
        self.optNumPeers    = 0
        self.sendPings      = 0
        self.pingsInterval  = 0.0
        self.addTasks       = 0
        self.clientVersion  = 0

        self.seedHost               = u""
        self.seedHostPort           = 0

        self.gettingPeersInterval   = 0.0
        self.gettingTasksInterval   = 0.0
        self.taskRequestInterval    = 0.0
        self.estimatedPerformance   = 0.0
        self.nodeSnapshotInterval   = 0.0