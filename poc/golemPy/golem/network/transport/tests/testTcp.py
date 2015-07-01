import sys
import os
import unittest
import logging
from twisted.internet.protocol import Factory, Protocol
from threading import Thread
from time import sleep

sys.path.append(os.environ.get('GOLEM'))

from golem.network.transport.Tcp import Network


class QOTD(Protocol):

    def connectionMade(self):
        # self.factory was set by the factory's default buildProtocol:
        self.transport.write("An apple a day keeps the doctor away\r\n")
        self.transport.loseConnection()

    def setSession(self, session):
        self.session = session

class QOTDClientSession():
    ConnectionStateType = QOTD

    def __init__(self, conn):
        self.conn = conn

    def makeConnection(self):
        pass

    def dataReceived(self, data):
        pass

class QOTDFactory(Factory):
    def __init__(self, _):
        pass

    def buildProtocol(self, addr):
        return QOTD()

class HostData:
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port

class TestNetwork(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.listenSuccess = False
        self.connectSuccess = False

#    def test1(self):
#        Network.listen(8889, 8999, QOTDFactory(self), None, self.__listenSuccess, self.__listenFailure)
#        sleep(1)
 #       self.assertTrue(self.listenSuccess)

    def test2(self):
        from twisted.internet import reactor

        th = Thread(target=reactor.run, args=(False,))
        th.deamon = True
        th.start()
        sleep(5)
        Network.connect('127.0.0.1', 8007, QOTDClientSession, self.__connectSuccess, self.__connectFailure)
        sleep(5)
        reactor.stop()
        self.assertTrue(self.connectSuccess)

    # def test3(self):
    #     from twisted.internet import reactor
    #
    #     th = Thread(target=reactor.run, args=(False,))
    #     th.deamon = True
    #     th.start()
    #     sleep(5)
    #     hd = [HostData('127.0.0.1', 8009), HostData('109.31.31.32', 9999), HostData('127.0.0.1', 8007)]
    #     Network.connectToHost(hd, QOTDClientSession, self.__connectSuccess, self.__connectFailure)
    #     sleep(25)
    #     reactor.stop()
    #     self.assertTrue(self.connectSuccess)

#     def test3(self):
#         from twisted.internet import reactor

#         th = Thread(target=reactor.run, args=(False,))
# #        th.deamon = True
# #       th.start()
#         sleep(5)
#         hd = [HostData('127.0.0.1', 8007), HostData('127.0.0.1', 8009)]
#         Network.connectToHost(hd, QOTDClientSession, self.__connectSuccess, self.__connectFailure)
#         sleep(25)
#  #       reactor.stop()
#         self.assertTrue(self.connectSuccess)

    def __listenSuccess(self, _):
        print "success"
        self.listenSuccess = True

    def __listenFailure(self):
        print "failure"
        self.listenSuccess = False

    def __connectSuccess(self, *args):
        print "success"
        self.connectSuccess = True

    def __connectFailure(self, *args):
        print "failure"
        self.connectSuccess = False



if __name__ == '__main__':
    unittest.main()