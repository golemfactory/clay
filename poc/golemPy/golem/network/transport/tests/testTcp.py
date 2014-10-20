import sys
import unittest
import logging
from twisted.internet.protocol import Factory, Protocol
from threading import Thread
from time import sleep

sys.path.append('./../../../../')

from golem.network.transport.Tcp import Network


class QOTD(Protocol):

    def connectionMade(self):
        # self.factory was set by the factory's default buildProtocol:
        self.transport.write("An apple a day keeps the doctor away\r\n")
        self.transport.loseConnection()

    def setSession(self, session ):
        self.session = session

class QOTDClientSession():
    ConnectionStateType = QOTD

    def __init__( self, conn):
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

class TestNetwork(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.listenSuccess = False
        self.connectSuccess = False

    def testListen(self):
        Network.listen(8889, 8999, QOTDFactory(self), None, self.__listenSuccess, self.__listenFailure )
        sleep(1)
        self.assertTrue(self.listenSuccess)

    def testConnect( self ):

        from twisted.internet import reactor
        th = Thread(target=reactor.run, args=(False,))
        th.deamon = True
        th.start()
        Network.connect('127.0.0.1', 8889, QOTDClientSession, self.__connectSuccess, self.__connectFailure )
        sleep(5)
        reactor.stop()
        self.assertTrue(self.connectSuccess)

    def __listenSuccess( self, _ ):
        print "success"
        self.listenSuccess = True

    def __listenFailure( self ):
        print "failure"
        self.listenSuccess = False

    def __connectSuccess( self, _ ):
        print "success"
        self.connectSuccess = True

    def __connectFailure( self ):
        print "failure"
        self.connectSuccess = False



if __name__ == '__main__':
    unittest.main()