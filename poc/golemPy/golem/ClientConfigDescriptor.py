import logging

logger = logging.getLogger(__name__)

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

class ConfigApprover:

    def __init__(self, configDesc):
        self.configDesc = configDesc
        self.actions = {}
        self.optsToChange = []
        self.initActions()

    def change_config(self, newConfigDesc):
        ncdDict = newConfigDesc.__dict__
        changeDict = {k: ncdDict[k] for k in self.optsToChange if k in self.optsToChange}
        for key, val in changeDict.iteritems():
            changeDict[key] = self.actions[key](val, key)
        self.configDesc.__dict__.update(changeDict)
        return self.configDesc

    def initActions(self):

        dontChangeOpt = ['seedHost', 'rootPath', 'maxResourceSize', 'maxMemorySize', 'useDistributedResourceManagement',
                         'useWaitingForTaskTimeout', 'sendPings', 'useIp6', 'ethAccount', 'rootPath']
        toIntOpt = ['seedHostPort', 'managerPort', 'numCores', 'optNumPeers', 'distResNum', 'waitingForTaskTimeout',
                    'p2pSessionTimeout', 'taskSessionTimeout', 'resourceSessionTimeout', 'pingsInterval',
                    'maxResultsSendingDelay', ]
        toFloatOpt = ['estimatedPerformance', 'gettingPeersInterval', 'gettingTasksInterval', 'nodeSnapshotInterval',
                      'computingTrust', 'requestingTrust']
        self.optsToChange = dontChangeOpt + toIntOpt + toFloatOpt
        for opt in dontChangeOpt:
           self.actions[opt] = self._emptyAction
        for opt in toIntOpt:
            self.actions[opt] = self._toInt
        for opt in toFloatOpt:
            self.actions[opt] = self._toFloat

    def _emptyAction(self, val, name):
        return val

    def _toInt(self, val, name):
        try:
            nval = int(val)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, val))
            return val
        return nval

    def _toFloat(self, val, name):
        try:
            nval = float(val)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, val))
            return val
        return nval