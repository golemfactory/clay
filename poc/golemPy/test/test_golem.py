from golem import *


c = Client()

c.connect("127.0.0.1", 30302)

#hr1 = HelloResource()
#hr2 = HelloResource()
#reactor.callInThread(reactor.listenTCP, 8080, server.Site(hr1))
#reactor.callInThread(reactor.listenTCP, 8081, server.Site(hr2))
#reactor.listenTCP(8080, server.Site(hr1))
reactor.run()
