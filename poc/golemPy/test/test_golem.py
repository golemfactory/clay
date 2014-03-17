from twisted.web import server
from twisted.internet import reactor
from golem import HelloResource

hr1 = HelloResource()
hr2 = HelloResource()
reactor.callInThread(reactor.listenTCP, 8080, server.Site(hr1))
reactor.callInThread(reactor.listenTCP, 8081, server.Site(hr2))
#reactor.listenTCP(8080, server.Site(hr1))
reactor.run()
