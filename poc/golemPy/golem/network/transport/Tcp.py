from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, TCP6ServerEndpoint, \
    TCP6ClientEndpoint, connectProtocol
import logging
import ipaddr

logger = logging.getLogger(__name__)


class HostData:
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port

    def __eq__(self, other):
        return self.addr == other.addr and self.port == other.port

def nodeInfoToHostInfos(nodeInfo, port):
    hostInfos = [HostData(i, port) for i in nodeInfo.prvAddresses]
    if nodeInfo.pubPort:
        hostInfos.append(HostData(nodeInfo.pubAddr, nodeInfo.pubPort))
    else:
        hostInfos.append(HostData(nodeInfo.pubAddr, port))
    return hostInfos


class Network:

    ######################
    @classmethod
    def connect(cls, address, port, SessionType, establishedCallback=None, failureCallback=None, *args):
        logger.debug("Connecting to host {} : {}".format(address, port))
        useIp6 = False

        from twisted.internet import reactor
        try:
            ip = ipaddr.IPAddress(address)
            useIp6 = ip.version == 6
        except ValueError:
            logger.warning("{} is invalid".format(address))

        if useIp6:
            endpoint = TCP6ClientEndpoint(reactor, address, port)
        else:
            endpoint = TCP4ClientEndpoint(reactor, address, port)
        connection = SessionType.ConnectionStateType()

        d = connectProtocol(endpoint, connection)

        d.addCallback(Network.__connectionEstablished, SessionType, establishedCallback, *args)
        d.addErrback(Network.__connectionFailure, failureCallback, *args)

    ######################
    @classmethod
    def connectToHost(cls, hostInfos, SessionType, establishedCallback, failureCallback, *args):
        Network.__connectToOneHost(hostInfos, SessionType, establishedCallback, failureCallback, *args)

    ######################
    @classmethod
    def __connectToHostFailure(cls, hostInfos, SessionType, establishedCallback, failureCallback, *args):
        if len(hostInfos) > 1:
            Network.__connectToOneHost(hostInfos[1:], SessionType, establishedCallback, failureCallback, *args)
        else:
            if failureCallback:
                failureCallback(*args)

    ######################
    @classmethod
    def __connectionToHostEstablished(cls, session, hostInfos, SessionType, establishedCallback,
                                      failureCallback, *args):

        establishedCallback(session, *args)

    ######################
    @classmethod
    def __connectToOneHost(cls, hostInfos, SessionType, establishedCallback, failureCallback, *args):
        address = hostInfos[0].addr
        port = hostInfos[0].port
        Network.connect(address, port, SessionType, Network.__connectionToHostEstablished,
                        Network.__connectToHostFailure, hostInfos, SessionType, establishedCallback,
                        failureCallback, *args)

    ######################
    @classmethod
    def listen(cls, portStart, portEnd, factory, ownReactor=None, establishedCallback=None, failureCallback=None,
               useIp6=True, *args):
        Network.__listenOnce(portStart, portEnd, factory, ownReactor, establishedCallback, failureCallback,
                             useIp6, *args)

    ######################
    @classmethod
    def __listenOnce(cls, port, portEnd, factory, ownReactor=None, establishedCallback=None, failureCallback=None, useIp6=False, *args):
        if ownReactor:
            if useIp6:
                ep = TCP6ServerEndpoint(ownReactor, port)
            else:
                ep = TCP4ServerEndpoint(ownReactor, port)
        else:
            from twisted.internet import reactor
            if useIp6:
                ep = TCP6ServerEndpoint(reactor, port)
            else:
                ep = TCP4ServerEndpoint(reactor, port)

        d = ep.listen(factory)

        d.addCallback(cls.__listeningEstablished, establishedCallback, *args)
        d.addErrback(cls.__listeningFailure, port, portEnd, factory, ownReactor, establishedCallback, failureCallback, useIp6, *args)

    ######################
    @classmethod
    def __connectionEstablished(cls, conn, SessionType, establishedCallback, *args):
        if conn:
            session = SessionType(conn)
            conn.setSession(session)

            pp = conn.transport.getPeer()
            logger.debug("ConnectionEstablished {} {}".format(pp.host, pp.port))

            if establishedCallback:
                if len(args) == 0:
                    establishedCallback(session)
                else:
                    establishedCallback(session, *args)

    ######################
    @classmethod
    def __connectionFailure(cls, conn, failureCallback, *args):
        logger.info("Connection failure. {}".format(conn))
        if failureCallback:
            if len(args) == 0:
                failureCallback()
            else:
                failureCallback(*args)

    ######################
    @classmethod
    def __listeningEstablished(cls, listeningPort, establishedCallback, *args):
        if establishedCallback is None:
            return

        if len(args) == 0:
            establishedCallback(listeningPort)
        else:
            establishedCallback(listeningPort, args)

    ######################
    @classmethod
    def __listeningFailure(cls, p, curPort, endPort, factory, ownReactor, establishedCallback, failureCallback, useIp6=False, *args):
        if curPort < endPort:
            curPort += 1
            Network.__listenOnce(curPort, endPort, factory, ownReactor, establishedCallback, failureCallback, useIp6, *args)
        else:
            if failureCallback:
                failureCallback(p, *args)
