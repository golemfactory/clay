import sys
sys.path.append('../src/')

from client import Client
from twisted.internet import reactor

args = sys.argv

c = Client(int(args[1]))

c.start()

if len(args) > 2:
    c.connect("10.30.10.69", int(args[2]))

#hr1 = HelloResource()
#hr2 = HelloResource()
#reactor.callInThread(reactor.listenTCP, 8080, server.Site(hr1))
#reactor.callInThread(reactor.listenTCP, 8081, server.Site(hr2))
#reactor.listenTCP(8080, server.Site(hr1))



reactor.run()
