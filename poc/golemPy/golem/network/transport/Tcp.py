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
    def __init__(self, protocolFactory, sessionFactory, useIp6=False, timeout=30):
        from twisted.internet import reactor
        self.protocolFactory = protocolFactory
        self.sessionFactory = sessionFactory
        self.timeout = timeout
        self.reactor = reactor
        self.useIp6 = useIp6

    def connect(self, address, port, establishedCallback=None, failureCallback=None, *args):
        logger.debug("Connecting to host {} : {}".format(address, port))
        useIp6 = False

        try:
            ip = ipaddr.IPAddress(address)
            useIp6 = ip.version == 6
        except ValueError:
            logger.warning("{} is invalid".format(address))

        if useIp6:
            endpoint = TCP6ClientEndpoint(self.reactor, address, port, self.timeout)
        else:
            endpoint = TCP4ClientEndpoint(self.reactor, address, port, self.timeout)

        defer = endpoint.connect(self.protocolFactory)

        defer.addCallback(self.__connectionEstablished, establishedCallback, *args)
        defer.addErrback(self.__connectionFailure, failureCallback, *args)

    ######################
    def connectToHost(self, hostInfos, establishedCallback, failureCallback, *args):
        self.__connectToOneHost(hostInfos, establishedCallback, failureCallback, *args)

    ######################
    def __connectToHostFailure(self, hostInfos, establishedCallback, failureCallback, *args):
        if len(hostInfos) > 1:
            self.__connectToOneHost(hostInfos[1:], establishedCallback, failureCallback, *args)
        else:
            if failureCallback:
                failureCallback(*args)

    ######################
    def __connectionToHostEstablished(self, session, hostInfos, establishedCallback, failureCallback, *args):
        establishedCallback(session, *args)

    ######################
    def __connectToOneHost(self, hostInfos, establishedCallback, failureCallback, *args):
        address = hostInfos[0].addr
        port = hostInfos[0].port
        self.connect(address, port, self.__connectionToHostEstablished, self.__connectToHostFailure, hostInfos,
                     establishedCallback, failureCallback, *args)

    ######################
    def listen(self, portStart, portEnd, establishedCallback=None, failureCallback=None, useIp6=True, *args):
        self.__listenOnce(portStart, portEnd, establishedCallback, failureCallback, useIp6, *args)

    ######################
    def __listenOnce(self, port, portEnd, establishedCallback=None, failureCallback=None, *args):
        if self.useIp6:
            ep = TCP6ServerEndpoint(self.reactor, port)
        else:
            ep = TCP4ServerEndpoint(self.reactor, port)

        defer = ep.listen(self.protocolFactory)

        defer.addCallback(self.__listeningEstablished, establishedCallback, *args)
        defer.addErrback(self.__listeningFailure, port, portEnd, establishedCallback, failureCallback, *args)

    ######################
    def __connectionEstablished(self, conn, establishedCallback, *args):
        pp = conn.transport.getPeer()
        logger.debug("ConnectionEstablished {} {}".format(pp.host, pp.port))

        if establishedCallback:
            if len(args) == 0:
                establishedCallback(conn.session)
            else:
                establishedCallback(conn.session, *args)

    ######################
    def __connectionFailure(self, conn, failureCallback, *args):
        logger.info("Connection failure. {}".format(conn))
        if failureCallback:
            if len(args) == 0:
                failureCallback()
            else:
                failureCallback(*args)

    ######################
    def __listeningEstablished(self, listeningPort, establishedCallback, *args):
        if establishedCallback is None:
            return

        if len(args) == 0:
            establishedCallback(listeningPort)
        else:
            establishedCallback(listeningPort, *args)

    ######################
    def __listeningFailure(self, err, curPort, endPort, establishedCallback, failureCallback, *args):
        if curPort < endPort:
            curPort += 1
            self.__listenOnce(curPort, endPort, establishedCallback, failureCallback, *args)
        else:
            if failureCallback:
                failureCallback(err, *args)
