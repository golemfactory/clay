import logging
import random
import os
import time

from golem.network.transport.Tcp import Network
from golem.network.GNRServer import GNRServer
from golem.resource.ResourceConnState import ResourceConnState
from golem.resource.DirManager import DirManager
from golem.resource.ResourcesManager import DistributedResourceManager
from golem.resource.ResourceSession import ResourceSession


logger = logging.getLogger( __name__ )

##########################################################
class ResourceServer( GNRServer ):
    ############################
    def __init__( self, configDesc, client ):
        self.client = client
        self.resourcesToSend = []
        self.resourcesToGet = []
        self.resSendIt = 0
        self.peersIt = 0
        self.dirManager = DirManager( configDesc.rootPath, configDesc.clientUid )
        self.resourceManager = DistributedResourceManager( self.dirManager.getResourceDir() )
        GNRServer.__init__( self, configDesc, ResourceServerFactory )

        self.resourcePeers = {}
        self.waitingTasks = {}
        self.waitingTasksToCompute = {}
        self.waitingResources = {}

        self.lastGetResourcePeersTime  = time.time()
        self.getResourcePeersInterval = 5.0

    def changeResourceDir( self, configDesc ):
        self.dirManager.rootPath = configDesc.rootPath
        self.dirManager.nodeId = configDesc.clientUid
        self.resourceManager.changeResourceDir( self.dirManager.getResourceDir() )

    def getDistributedResourceRoot( self ):
        return self.dirManager.getResourceDir()

    ############################
    def getPeers( self ):
        self.client.getResourcePeers()

    ############################
    def addFilesToSend( self, files, taskId, num ):
        resFiles = {}
        for file_ in files:
            resFiles[ file_ ] = self.resourceManager.splitFile( file_ )
            for res in resFiles[ file_ ]:
                self.addResourceToSend( res, num, taskId  )
        return resFiles

    ############################
    def addFilesToGet( self, files, taskId ):
        num = 0
        for file_ in files:
            if not self.resourceManager.checkResource( file_ ):
                num += 1
                self.addResourceToGet( file_, taskId )

        if (num > 0 ):
            self.waitingTasksToCompute[ taskId ] = num
        else:
            self.client.taskResourcesCollected( taskId )

    ############################
    def addResourceToSend( self, name, num, taskId = None  ):
        if taskId not in self.waitingTasks:
            self.waitingTasks[ taskId ] = 0
        self.resourcesToSend.append( [ name, taskId, num ] )
        self.waitingTasks[ taskId ] += 1

    ############################
    def addResourceToGet( self, name, taskId ):
        self.resourcesToGet.append( [ name, taskId ] )

    ############################
    def newConnection( self, session ):
        session.resourceServer = self

    ############################
    def addResourcePeer(self, clientId, addr, port ):
        if clientId in self.resourcePeers:
            if self.resourcePeers[ clientId ]['addr'] == addr and self.resourcePeers[clientId]['port'] == port:
                return

        self.resourcePeers[ clientId ] = { 'addr': addr, 'port': port, 'state': 'free' }

    ############################
    def setResourcePeers( self, resourcePeers ):

        if self.configDesc.clientUid in resourcePeers:
            del resourcePeers[ self.configDesc.clientUid ]

        for clientId, [addr, port] in resourcePeers.iteritems():
            self.addResourcePeer( clientId, addr, port )

    ############################
    def syncNetwork( self ):
        if len( self.resourcesToGet ) + len( self.resourcesToSend ) > 0:
            curTime = time.time()
            if curTime - self.lastGetResourcePeersTime > self.getResourcePeersInterval:
                self.client.getResourcePeers()
                self.lastGetResourcePeersTime = time.time()
        self.sendResources()
        self.getResources()

    ############################
    def getResources( self ):
        if len ( self.resourcesToGet ) == 0:
            return
        resourcePeers = [ peer for peer in self.resourcePeers.values() if peer['state'] == 'free' ]
        random.shuffle( resourcePeers )

        if len ( self.resourcePeers ) == 0:
            return

        for peer in resourcePeers:
            peer['state'] = 'waiting'
            self.pullResource( self.resourcesToGet[0][0], peer['addr'], peer['port'])


    ############################
    def sendResources( self ):
        if len( self.resourcesToSend ) == 0:
            return

        if self.resSendIt >= len( self.resourcesToSend ):
            self.resSendIt = len( self.resourcesToSend ) - 1

        resourcePeers = [ peer for peer in self.resourcePeers.values() if peer['state'] == 'free' ]

        for peer in resourcePeers:
            name = self.resourcesToSend[ self.resSendIt ][0]
            num = self.resourcesToSend[ self.resSendIt ][2]
            peer['state'] = 'waiting'
            self.pushResource( name , peer['addr'], peer['port'] , num )
            self.resSendIt = (self.resSendIt + 1) % len( self.resourcesToSend )

    ############################
    def pullResource( self, resource, addr, port ):
        Network.connect( addr, port, ResourceSession, self.__connectionPullResourceEstablished, self.__connectionPullResourceFailure, resource, addr, port )

    ############################
    def pullAnswer( self, resource, hasResource, session ):
        if not hasResource or resource not in [ res[0] for res in self.resourcesToGet]:
            self.__freePeer( session.address, session.port )
            session.conn.close()
        else:
            if resource not in self.waitingResources:
                self.waitingResources[resource] = []
            for res in self.resourcesToGet:
                if res[0] == resource:
                    self.waitingResources[resource].append( res[1])
            for taskId in self.waitingResources[resource]:
                    self.resourcesToGet.remove( [resource, taskId] )
            session.fileName = resource
            session.conn.fileMode = True
            session.conn.confirmation = False
            session.sendWantResource( resource )

    ############################
    def pushResource( self, resource, addr, port, copies ):
        Network.connect( addr, port, ResourceSession, self.__connectionPushResourceEstablished, self.__connectionPushResourceFailure, resource, copies, addr, port )

    ############################
    def checkResource( self, resource ):
        return self.resourceManager.checkResource( resource )

    ############################
    def prepareResource( self, resource ):
        return self.resourceManager.getResourcePath( resource )

    ############################
    def resourceDownloaded( self, resource, address, port ):
        self.__freePeer( address, port )
        for taskId in self.waitingResources[ resource ]:
            self.waitingTasksToCompute[taskId] -= 1
            if self.waitingTasksToCompute[ taskId ] == 0:
                self.client.taskResourcesCollected( taskId )
                del self.waitingTasksToCompute[ taskId ]
        del self.waitingResources[ resource ]

    ############################
    def hasResource( self, resource, addr, port ):
        removeRes = False
        for res in self.resourcesToSend:

            if resource == res[0]:
                res[2] -= 1
                if res[2] == 0:
                    removeRes = True
                    taskId = res[1]
                    self.waitingTasks[taskId] -= 1
                    if self.waitingTasks[ taskId ] == 0:
                        del self.waitingTasks[ taskId ]
                        if taskId is not None:
                            self.client.taskResourcesSend( taskId )
                    break

        if removeRes:
            self.resourcesToSend.remove( [resource, taskId, 0] )

        self.__freePeer( addr, port )

    ############################
    def unpackDelta( self, destDir, delta, taskId ):
        if not os.path.isdir( destDir ):
            os.mkdir( destDir )
        for dirHeader in delta.subDirHeaders:
            self.unpackDelta( os.path.join( destDir, dirHeader.dirName ), dirHeader, taskId )

        for filesData in delta.filesData:
            self.resourceManager.connectFile( filesData[2], os.path.join( destDir, filesData[0] ) )

    ############################
    def __freePeer( self, addr, port ):
        for clientId, value in self.resourcePeers.iteritems():
            if value['addr'] == addr and value['port'] == port:
                self.resourcePeers[ clientId ]['state'] = 'free'


    ############################
    def __connectionPushResourceEstablished( self, session, resource, copies, addr, port ):
        session.resourceServer = self
        session.sendPushResource( resource, copies )

    ############################
    def __connectionPushResourceFailure( self, resource, copies, addr, port ):
        self.__removeClient( addr, port )
        logger.error( "Connection to resource server failed" )

    ############################
    def __connectionPullResourceEstablished( self, session, resource, addr, port ):
        session.resourceServer = self
        session.sendPullResource( resource )

    ############################
    def __connectionPullResourceFailure( self, resource, addr, port ):
        self.__removeClient( addr, port )
        logger.error( "Connection to resource server failed" )

    ############################
    def __connectionForResourceEstablished( self, session, resource, addr, port ):
        session.sendWantResource( resource )

    ############################
    def __connectionForResourceFailure( self, resource, addr, port ):
        self.__removeClient( addr, port )
        logger.error( "Connection to resource server failed" )

    ############################
    def __removeClient( self, addr, port ):
        badClient = None
        for clientId, peer in self.resourcePeers.iteritems():
            if peer['addr'] == addr and peer['port'] == port:
                badClient = clientId
                break

        if badClient is not None:
            self.resourcePeers[ badClient ]

    ############################
    def _listeningEstablished( self, iListeningPort ):
        GNRServer._listeningEstablished( self, iListeningPort )
        self.client.setResourcePort( self.curPort )

    ############################
    def _getFactory( self ):
        return self.factory( self )

##########################################################
from twisted.internet.protocol import Factory

class ResourceServerFactory( Factory ):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol( self, addr ):
        return ResourceConnState( self.server )