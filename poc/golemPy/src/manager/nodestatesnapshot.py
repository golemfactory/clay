from PyQt4 import QtCore

#FIXME: REGISTER number of local and remote tasks processed by current node (and number of successes and failures as well) - and show it in this manager
#FIXME: also add a boolean flag indicating whether there is any active local/rempote task being calculated
class NodeStateSnapshot:

    def __init__( self, uid = 0, peersNum = 0, tasksNum = 0, remoteProgress = {}, localProgress = {}, lastNetowrkMessages = [], lastTaskMessages = [] ):
        self.uid                    = uid
        self.timestamp              = QtCore.QTime.currentTime()
        self.peersNum               = peersNum
        self.tasksNum               = tasksNum
        self.remoteProgress         = remoteProgress
        self.localProgress          = localProgress

        self.lastNetowrkMessages    = lastNetowrkMessages
        self.lastTaskMessages       = lastTaskMessages

    def getUID( self ):
        return self.uid

    def getFormattedTimestamp( self ):
        return self.timestamp.toString( "hh:mm:ss.zzz" )

    def getRemoteProgress( self ):
        return self.remoteProgress

    def getLocalProgress( self ):
        return self.localProgress

    def getPeersNum( self ):
        return self.peersNum

    def getTasksNum( self ):
        return self.tasksNum

    def getLastNetworkMessages( self ):
        return self.lastNetowrkMessages

    def getLastTaskMessages( self ):
        return self.lastTaskMessages

    def __str__( self ):
        ret = str( self.getUID() )+ " ----- \n" + "peers count: " + str( self.getPeersNum() ) + "\n" + "tasks count: " + str( self.getTasksNum() ) + "\n"
        ret += "remote progress: " + str( self.getRemoteProgress() ) + "\n" + "lockal progress: " + str( self.getLocalProgress() ) + "\n"
        ret += "last net comunication: " + str( self.getLastNetworkMessages() ) + "\n"
        ret += "last task comunication: " + str( self.getLastTaskMessages() )
        return ret




if __name__ == "__main__":

    ns = NodeStateSnapshot( "some uiid", 0.2, 0.7 )

    print ns.getUID()
    print ns.getFormattedTimestamp()
    print ns.getLocalProgress()
    print ns.getRemoteProgress()
