from PyQt4 import QtCore

#FIXME: REGISTER number of local and remote tasks processed by current node (and number of successes and failures as well) - and show it in this manager
class NodeStateSnapshot:

    def __init__( self, uid, remoteProgress, localProgress ):
        self.uid = uid
        self.timestamp = QtCore.QTime.currentTime()
        self.remoteProgress = remoteProgress
        self.localProgress = localProgress

    def getUID( self ):
        return self.uid

    def getFormattedTimestamp( self ):
        return self.timestamp.toString( "hh:mm:ss.zzz" )

    def getRemoteProgress( self ):
        return self.remoteProgress

    def getLocalProgress( self ):
        return self.localProgress

if __name__ == "__main__":

    ns = NodeStateSnapshot( "some uiid", 0.2, 0.7 )

    print ns.getUID()
    print ns.getFormattedTimestamp()
    print ns.getLocalProgress()
    print ns.getRemoteProgress()
